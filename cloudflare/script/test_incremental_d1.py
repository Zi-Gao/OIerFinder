import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from cloudflare.script import incremental_d1 as sync
from cloudflare.script import sync_snapshot as snapshots
from cloudflare.script import upload_to_d1 as legacy


class LocalD1(sync.D1Client):
    """Executes the exact production batch SQL with SQLite transactions/triggers."""
    def __init__(self, path):
        self.db = sqlite3.connect(path, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.fail_at = None
        self.lose_response = False
        self.before_batch = None
        self.batch_count = 0

    def query(self, sql, params=()):
        return [dict(row) for row in self.db.execute(sql, params)]

    def identity(self):
        return {'account_id': 'test-account', 'database_id': 'test-database'}

    def release(self):
        row = self.db.execute('SELECT * FROM DataRelease WHERE id=1').fetchone()
        return dict(row) if row else None

    def batch(self, statements):
        self.batch_count += 1
        if self.before_batch:
            callback, self.before_batch = self.before_batch, None
            callback()
        self.db.execute('BEGIN')
        results = []
        try:
            for n, item in enumerate(statements):
                if n == self.fail_at:
                    raise RuntimeError('Injected batch failure')
                cursor = self.db.execute(item['sql'], item.get('params', []))
                rows = [dict(row) for row in cursor] if cursor.description else []
                results.append({'success': True, 'results': rows, 'meta': {}})
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        if self.lose_response:
            raise TimeoutError('Committed but response lost')
        return {'result': results}


OLD_ROWS = {
    'OIer': [
        {'uid': 1, 'name': 'Alice', 'initials': 'A', 'gender': 1, 'enroll_middle': 2020, 'oierdb_score': 10., 'ccf_score': 0., 'ccf_level': 3},
        {'uid': 2, 'name': 'Bob', 'initials': 'B', 'gender': 2, 'enroll_middle': 2021, 'oierdb_score': 5., 'ccf_score': 0., 'ccf_level': 1},
    ],
    'Contest': [
        {'id': 1, 'name': 'CSP2024', 'type': 'CSP入门', 'year': 2024, 'fall_semester': 1, 'full_score': 400},
        {'id': 2, 'name': 'NOIP2023', 'type': 'NOIP', 'year': 2023, 'fall_semester': 1, 'full_score': 400},
    ],
    'School': [
        {'id': 1, 'name': 'School A', 'province': '北京', 'city': '北京', 'score': 10.},
        {'id': 2, 'name': 'School B', 'province': '北京', 'city': '北京', 'score': 5.},
    ],
    'Record': [
        {'id': 10, 'oier_uid': 1, 'contest_id': 1, 'school_id': 1, 'score': 200., 'rank': 1, 'province': '北京', 'level': '一等奖'},
        {'id': 20, 'oier_uid': 2, 'contest_id': 2, 'school_id': 2, 'score': None, 'rank': 2, 'province': '北京', 'level': '二等奖'},
    ],
}


def target_rows():
    rows = json.loads(json.dumps(OLD_ROWS))
    rows['OIer'][0]['oierdb_score'] = 12.
    rows['OIer'][1].update(uid=3, name='Charlie', initials='C')
    rows['Contest'] = rows['Contest'][:1]
    rows['School'][0]['score'] = 12.
    rows['School'][1]['id'] = 3
    rows['Record'][0].update(id=999, school_id=3, score=210.)
    rows['Record'][1].update(id=888, oier_uid=3, contest_id=1, school_id=1)
    return rows


def archive_fixture(database, directory, sha='1' * 40, fingerprint='a' * 64, projection='test-projection'):
    stats = directory.parent / (directory.name + '-stats.json')
    stats.write_text(json.dumps(snapshots.statistics(snapshots.read_state(database))))
    return snapshots.create_archive(database, stats, directory, source_sha=sha,
                                    source_hash=fingerprint, projection=projection, worker_version='2' * 40)


class PublishingFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.old = self.root / 'old.db'
        self.new = self.root / 'new.db'
        snapshots.write_core_database(self.old, OLD_ROWS)
        snapshots.write_core_database(self.new, target_rows())
        self.old_state, self.new_state = snapshots.read_state(self.old), snapshots.read_state(self.new)
        self.old_manifest = archive_fixture(self.old, self.root / 'archive-old')
        self.new_manifest = archive_fixture(self.new, self.root / 'archive-new', '4' * 40, 'b' * 64)
        self.client = LocalD1(self.old)
        self.addCleanup(self.client.db.close)
        self.client.db.executescript(legacy.RELEASE_SCHEMA)
        self.client.db.execute('ALTER TABLE DataRelease ADD COLUMN source_data_hash TEXT')
        self.client.db.executescript(sync.MIGRATION.read_text())
        for table, names in sync.INDEX_NAMES.items():
            for name, columns in zip(names, sync.INDEXES[table]):
                self.client.db.execute(f'CREATE INDEX {name} ON {table}({", ".join(columns)})')
        self.base = sync.publication_values(self.old_manifest, '3' * 40, source_sha='1' * 40,
            source_hash='a' * 64, worker_version='2' * 40, run_url='https://example.invalid/old', revision=0)
        cols = list(self.base)
        self.client.db.execute(f'INSERT INTO DataRelease (id,{",".join(cols)}) VALUES(1,{",".join("?" for _ in cols)})', list(self.base.values()))
        self.base = self.client.current()[0]
        self.patch, self.summary = sync.diff_states(self.old_state, self.new_state)
        operations, _ = sync.estimate_writes(self.patch)
        self.target = sync.publication_values(self.new_manifest, '5' * 40, source_sha='4' * 40,
            source_hash='b' * 64, worker_version='2' * 40, run_url='https://example.invalid/new', revision=operations)

    def assert_old(self):
        self.assertEqual(snapshots.read_state(self.old), self.old_state)
        self.assertEqual(sync.release_identity(self.client.release()), sync.release_identity(self.base))
        self.assertEqual(self.client.revision(), 0)
        self.assertEqual(self.client.query('SELECT * FROM OierSyncBudget'), [])

    def publish(self, limits=None):
        return sync.publish(self.client, self.base, 0, self.patch, self.target, limits or sync.Limits())


class IncrementalPublishingTests(PublishingFixture):
    def test_delta_matches_complete_target_and_preserves_internal_record_ids(self):
        self.assertEqual(self.publish()['status'], 'committed')
        self.assertEqual(snapshots.read_state(self.old), self.new_state)
        self.assertEqual(self.client.query('SELECT id FROM Record WHERE oier_uid=1 AND contest_id=1')[0]['id'], 10)
        self.assertEqual(self.client.query('PRAGMA foreign_key_check'), [])
        self.assertEqual(self.publish()['status'], 'already_applied')
        self.assertEqual(self.client.batch_count, 1)

    def test_failure_at_every_statement_rolls_back_data_revision_budget_and_pointer(self):
        commands = sync.build_transaction(self.base, 0, self.patch, self.target, sync.Limits())
        for n in range(len(commands)):
            with self.subTest(statement=n):
                self.client.fail_at = n
                with self.assertRaises(sync.SyncError):
                    self.publish()
                self.assert_old()

    def test_unknown_network_response_is_resolved_without_resending(self):
        self.client.lose_response = True
        self.assertEqual(self.publish()['status'], 'committed_response_lost')
        self.assertEqual(snapshots.read_state(self.old), self.new_state)
        self.assertEqual(self.client.batch_count, 1)

    def test_manual_core_write_detected_even_when_release_identity_matches(self):
        self.client.db.execute('UPDATE OierSyncState SET writing=1 WHERE id=1')
        self.client.db.execute('UPDATE OIer SET oierdb_score=99 WHERE uid=1')
        self.client.db.execute('UPDATE OierSyncState SET writing=0 WHERE id=1')
        with self.assertRaisesRegex(sync.SyncError, 'outside'):
            self.publish()
        self.assertEqual(self.client.batch_count, 0)
        self.assertEqual(self.client.release()['snapshot_commit'], self.base['snapshot_commit'])

    def test_core_write_between_planning_and_transaction_rejected(self):
        def competing_write():
            self.client.db.execute('UPDATE OierSyncState SET writing=1 WHERE id=1')
            self.client.db.execute('UPDATE OIer SET oierdb_score=99 WHERE uid=1')
            self.client.db.execute('UPDATE OierSyncState SET writing=0 WHERE id=1')
        self.client.before_batch = competing_write
        with self.assertRaises(sync.SyncError):
            self.publish()
        self.assertEqual(self.client.release()['snapshot_commit'], self.base['snapshot_commit'])
        self.assertEqual(self.client.query('SELECT name FROM OIer WHERE uid=2')[0]['name'], 'Bob')

    def test_stale_release_rejected(self):
        self.client.db.execute("UPDATE DataRelease SET upstream_sha=? WHERE id=1", ['6' * 40])
        with self.assertRaisesRegex(sync.SyncError, 'stale'):
            self.publish()
        self.assertEqual(self.client.batch_count, 0)

    def test_incorrect_old_row_is_rejected_inside_transaction(self):
        self.patch['OIer']['update'][0]['old'] = dict(self.patch['OIer']['update'][0]['old'], oierdb_score=999.)
        with self.assertRaises(sync.SyncError):
            self.publish()
        self.assert_old()

    def test_unexpected_trigger_side_effect_rolls_back_entire_publish(self):
        self.client.db.execute('CREATE TRIGGER surprise AFTER UPDATE ON OIer BEGIN UPDATE School SET score=99 WHERE id=1; END')
        with self.assertRaises(sync.SyncError):
            self.publish()
        self.assert_old()

    def test_missing_revision_trigger_stops_publication(self):
        self.client.db.execute('DROP TRIGGER oier_sync_Record_update')
        with self.assertRaisesRegex(sync.SyncError, 'triggers'):
            self.publish()
        self.assertEqual(self.client.batch_count, 0)

    def test_replaced_assertion_table_is_rejected_before_any_write(self):
        self.client.db.execute('DROP TABLE OierSyncGuard')
        self.client.db.execute('CREATE TABLE OierSyncGuard(id INTEGER PRIMARY KEY,ok INTEGER)')
        with self.assertRaisesRegex(sync.SyncError, 'table definition'):
            self.publish()
        self.assertEqual(self.client.batch_count, 0)

    def test_unverifiable_lost_response_stops_without_resending(self):
        self.client.lose_response = True
        original = self.client.current
        calls = 0
        def unavailable_after_commit(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls > 1:
                raise TimeoutError('Read unavailable')
            return original(*args, **kwargs)
        with patch.object(self.client, 'current', side_effect=unavailable_after_commit):
            with self.assertRaisesRegex(sync.SyncError, 'outcome is unknown'):
                self.publish()
        self.assertEqual(self.client.batch_count, 1)
        self.assertEqual(self.client.release()['snapshot_commit'], self.target['snapshot_commit'])

    def test_missing_revision_row_aborts_core_writes(self):
        self.client.db.execute('DELETE FROM OierSyncState')
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'Missing OierSyncState'):
            self.client.db.execute('DELETE FROM Record')
        self.assertEqual(len(self.client.query('SELECT * FROM Record')), 2)

    def test_core_write_gate_blocks_legacy_or_accidental_direct_writes(self):
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'guarded publisher'):
            self.client.db.execute('UPDATE OIer SET oierdb_score=99 WHERE uid=1')
        self.assert_old()

    def test_left_open_write_gate_stops_publisher(self):
        self.client.db.execute('UPDATE OierSyncState SET writing=1 WHERE id=1')
        with self.assertRaisesRegex(sync.SyncError, 'left open'):
            self.publish()
        self.assertEqual(self.client.batch_count, 0)

    def test_budget_rejection_and_exhausted_daily_budget_leave_old_release(self):
        with self.assertRaisesRegex(sync.SyncError, 'budget'):
            self.publish(sync.Limits(max_operations=1))
        self.assert_old()
        self.client.db.execute("INSERT INTO OierSyncBudget VALUES(date('now'),75000)")
        with self.assertRaises(sync.SyncError):
            self.publish()
        self.assertEqual(snapshots.read_state(self.old), self.old_state)
        self.assertEqual(self.client.revision(), 0)
        self.assertEqual(self.client.release()['snapshot_commit'], self.base['snapshot_commit'])

    def test_empty_delta_only_advances_metadata(self):
        empty, _ = sync.diff_states(self.old_state, self.old_state)
        self.client.db.execute("UPDATE DataRelease SET activated_at='2000-01-01 00:00:00' WHERE id=1")
        target = {k: v for k, v in self.base.items() if k in sync.RELEASE_FIELDS or k == 'github_run_url'}
        target['upstream_sha'] = '6' * 40
        sync.publish(self.client, self.base, 0, empty, target, sync.Limits())
        self.assertEqual(self.client.revision(), 0)
        self.assertEqual(snapshots.read_state(self.old), self.old_state)
        self.assertEqual(self.client.release()['snapshot_commit'], self.base['snapshot_commit'])
        self.assertEqual(self.client.release()['activated_at'], '2000-01-01 00:00:00')

    def test_manifest_must_match_actual_published_identity(self):
        sync.assert_manifest_matches(self.base, self.old_manifest)
        with self.assertRaisesRegex(sync.SyncError, 'match'):
            sync.assert_manifest_matches(self.base, self.new_manifest)

    def test_bootstrap_reads_actual_live_data_and_does_not_rewrite_core(self):
        for field in sync.SNAPSHOT_FIELDS:
            self.client.db.execute(f'UPDATE DataRelease SET {field}=NULL WHERE id=1')
        def generate(db, output):
            output.write_text(json.dumps(snapshots.statistics(snapshots.read_state(db))))
        stored = []
        def store(directory):
            stored.append(directory)
            return '7' * 40
        release = sync.bootstrap(self.client, store, self.root, generate)
        self.assertEqual(release['snapshot_commit'], '7' * 40)
        self.assertEqual(self.client.revision(), 0)
        self.assertEqual(snapshots.read_state(self.old), self.old_state)
        self.assertEqual(len(stored), 1)

    def test_archive_failure_cannot_attach_bootstrap_pointer(self):
        for field in sync.SNAPSHOT_FIELDS:
            self.client.db.execute(f'UPDATE DataRelease SET {field}=NULL WHERE id=1')
        generate = lambda db, output: output.write_text(json.dumps(snapshots.statistics(snapshots.read_state(db))))
        with self.assertRaisesRegex(RuntimeError, 'Git unavailable'):
            sync.bootstrap(self.client, lambda _: (_ for _ in ()).throw(RuntimeError('Git unavailable')), self.root, generate)
        self.assertIsNone(self.client.release()['snapshot_commit'])
        self.assertEqual(self.client.revision(), 0)


class SnapshotValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / 'fixture.db'
        snapshots.write_core_database(self.db, OLD_ROWS)
        self.directory = self.root / 'archive'
        self.manifest = archive_fixture(self.db, self.directory)

    def test_archive_roundtrip_and_statistics_match(self):
        manifest, state = snapshots.open_archive(self.directory, self.root / 'restored.db')
        self.assertEqual(manifest, self.manifest)
        self.assertEqual(state, snapshots.read_state(self.db))

    def test_tampered_archive_stops_before_database_use(self):
        with (self.directory / 'oier_data.db.gz').open('ab') as target:
            target.write(b'corruption')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            snapshots.open_archive(self.directory, self.root / 'restored.db')
        self.assertFalse((self.root / 'restored.db').exists())

    def test_wrong_statistics_and_duplicate_business_keys_are_rejected(self):
        stats = self.root / 'wrong-stats.json'
        stats.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'Statistics'):
            snapshots.create_archive(self.db, stats, self.root / 'wrong', source_sha='1' * 40,
                source_hash='a' * 64, projection='test', worker_version='2' * 40)
        with sqlite3.connect(self.db) as db:
            db.execute('INSERT INTO Record(oier_uid,contest_id,school_id,score,rank,province,level) SELECT oier_uid,contest_id,school_id,score,rank,province,level FROM Record LIMIT 1')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            snapshots.read_state(self.db)

    def test_numeric_normalization_matches_sqlite_zero_and_rejects_imprecise_ids(self):
        self.assertEqual(snapshots.normalize('score', -0.0), 0.0)
        self.assertEqual(json.dumps(snapshots.normalize('score', -0.0)), '0.0')
        with self.assertRaises(ValueError):
            snapshots.normalize('uid', 9007199254740992)


if __name__ == '__main__':
    unittest.main()

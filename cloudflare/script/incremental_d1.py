"""Fail-closed D1 delta publishing and transaction assertions."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re

if __package__:
    from . import sync_snapshot as snapshots
    from . import upload_to_d1 as legacy
else:
    import sync_snapshot as snapshots
    import upload_to_d1 as legacy


RELEASE_FIELDS = (
    'upstream_sha', 'data_hash', 'source_data_hash', 'worker_version', 'status',
    'oier_count', 'contest_count', 'school_count', 'record_count',
    'snapshot_commit', 'snapshot_sha256', 'projection_version', 'logical_data_hash', 'core_revision',
)
SNAPSHOT_FIELDS = ('snapshot_commit', 'snapshot_sha256', 'projection_version', 'logical_data_hash', 'core_revision')
COUNT_FIELDS = {'OIer': 'oier_count', 'Contest': 'contest_count', 'School': 'school_count', 'Record': 'record_count'}
INDEXES = {
    'OIer': [('gender', 'enroll_middle', 'uid'), ('initials', 'uid')],
    'Contest': [('year', 'type', 'id')],
    'School': [],
    'Record': [('oier_uid', 'contest_id', 'level', 'score', 'rank', 'province', 'school_id'),
               ('contest_id', 'level', 'oier_uid'), ('school_id', 'province', 'level', 'oier_uid')],
}
INDEX_NAMES = {
    'OIer': ('idx_oier_gender_enroll', 'idx_oier_initials_uid'),
    'Contest': ('idx_contest_year_type',),
    'School': (),
    'Record': ('idx_record_oier_covering', 'idx_record_contest_level_uid', 'idx_record_school_province_level_uid'),
}
MAX_REQUEST_BYTES = 4 * 1024 * 1024
MIGRATION = snapshots.ROOT / 'cloudflare/migrations/0004_incremental_sync.sql'


class SyncError(RuntimeError):
    pass


@dataclass(frozen=True)
class Limits:
    max_operations: int = 1000
    max_estimated_writes: int = 15000
    daily_write_budget: int = 75000

    @classmethod
    def from_env(cls):
        values = {}
        for field, env in (('max_operations', 'D1_SYNC_MAX_OPERATIONS'),
                           ('max_estimated_writes', 'D1_SYNC_MAX_ESTIMATED_WRITES'),
                           ('daily_write_budget', 'D1_SYNC_DAILY_WRITE_BUDGET')):
            if env in os.environ:
                values[field] = int(os.environ[env])
        result = cls(**values)
        if any(value <= 0 or value > 9007199254740991 for value in vars(result).values()) or result.max_operations > 5000:
            raise ValueError('Invalid incremental publishing limits')
        return result


def expected_triggers():
    return dict(re.findall(r'CREATE TRIGGER (\w+) (.*?\bEND);', MIGRATION.read_text(), re.DOTALL))


def normalized_sql(sql):
    return ' '.join(sql.strip().rstrip(';').split())


class D1Client:
    def __init__(self, cfg):
        self.cfg = cfg

    def identity(self):
        return {key: self.cfg['cloudflare'][key] for key in ('account_id', 'database_id')}

    def query(self, sql, params=()):
        payload = {'sql': sql, 'params': list(params)}
        data = legacy._execute_d1_request(self.cfg, 'query', payload)
        if len(data['result']) != 1:
            raise SyncError('Unexpected D1 query response')
        return data['result'][0].get('results', [])

    def batch(self, statements):
        return legacy.execute_d1_batch(self.cfg, statements)

    def release(self):
        return legacy.get_release(self.cfg)

    def revision(self):
        rows = self.query('SELECT revision,writing FROM OierSyncState WHERE id=1')
        if len(rows) != 1 or type(rows[0]['revision']) is not int or not 0 <= rows[0]['revision'] <= 9007199254740991:
            raise SyncError('Invalid core-data revision; publishing stopped')
        if rows[0]['writing'] != 0:
            raise SyncError('Core write gate was left open outside a publishing transaction; audit required')
        return rows[0]['revision']

    def current(self, allow_legacy=False):
        release = self.release()
        validate_release(release)
        schema = self.query("SELECT name,type,sql FROM sqlite_master WHERE name IN ('OierSyncState','OierSyncGuard','OierSyncBudget') OR (type='trigger' AND tbl_name IN ('OIer','Contest','School','Record','DataRelease','OierSyncState','OierSyncGuard','OierSyncBudget'))")
        if not schema:
            if allow_legacy and not any(release.get(k) is not None for k in SNAPSHOT_FIELDS):
                return release, None
            raise SyncError('Incremental migrations are required')
        tables = {r['name'] for r in schema if r['type'] == 'table'}
        triggers = {r['name']: r['sql'] for r in schema if r['type'] == 'trigger'}
        expected = expected_triggers()
        if tables != {'OierSyncState', 'OierSyncGuard', 'OierSyncBudget'} or triggers.keys() != expected.keys():
            raise SyncError('Incomplete sync schema or revision triggers; publishing stopped')
        expected_tables = {name: f'CREATE TABLE {name} {body}' for name, body in
                           re.findall(r'CREATE TABLE (OierSync\w+) (\(.*?\));', MIGRATION.read_text(), re.DOTALL)}
        for row in schema:
            if row['type'] == 'table' and normalized_sql(row['sql']) != normalized_sql(expected_tables[row['name']]):
                raise SyncError(f'Unexpected sync table definition: {row["name"]}')
        for name, body in expected.items():
            if normalized_sql(triggers[name]) != normalized_sql(f'CREATE TRIGGER {name} {body}'):
                raise SyncError(f'Unexpected revision trigger: {name}')
        index_rows = self.query("SELECT name,tbl_name,sql FROM sqlite_master WHERE type='index' AND tbl_name IN ('OIer','Contest','School','Record')")
        expected_indexes = {name: (table, columns) for table, names in INDEX_NAMES.items()
                            for name, columns in zip(names, INDEXES[table])}
        if {row['name'] for row in index_rows} != expected_indexes.keys():
            raise SyncError('Core indexes differ from the reviewed write budget; do not rebuild indexes automatically')
        for row in index_rows:
            table, columns = expected_indexes[row['name']]
            match = re.search(r'\bON\s+["\[]?(\w+)["\]]?\s*\(([^)]+)\)', row['sql'] or '', re.IGNORECASE)
            actual = tuple(col.strip().strip('"[]`').lower() for col in match.group(2).split(',')) if match else ()
            if not match or match.group(1).lower() != table.lower() or actual != columns:
                raise SyncError(f'Unexpected index definition: {row["name"]}')
        revision = self.revision()
        if release.get('snapshot_commit'):
            if not all(release.get(k) is not None for k in SNAPSHOT_FIELDS):
                raise SyncError('Incomplete published snapshot identity')
            if release['core_revision'] != revision:
                raise SyncError('Core data changed outside its published snapshot; an explicit audit is required')
            if not snapshots.SHA.fullmatch(release['snapshot_commit']):
                raise SyncError('Invalid published snapshot commit')
            for field in ('snapshot_sha256', 'logical_data_hash'):
                if not snapshots.HASH.fullmatch(release[field]):
                    raise SyncError(f'Invalid published {field}')
        elif any(release.get(k) is not None for k in SNAPSHOT_FIELDS):
            raise SyncError('Partial snapshot identity; publishing stopped')
        return release, revision


def validate_release(release):
    if not release or release.get('status') != 'active':
        raise SyncError('An existing active production release is required; no automatic full upload is allowed')
    if not snapshots.SHA.fullmatch(release.get('upstream_sha', '')):
        raise SyncError('Invalid active source SHA')
    if not snapshots.HASH.fullmatch(release.get('source_data_hash') or ''):
        raise SyncError('An audited active source fingerprint is required')
    if any(type(release.get(field)) is not int or release[field] <= 0 for field in COUNT_FIELDS.values()):
        raise SyncError('Invalid published row counts')


def release_identity(release):
    return {field: release.get(field) for field in RELEASE_FIELDS}


def assert_manifest_matches(release, manifest):
    expected = {
        'data_hash': release['data_hash'],
        'archive_sha256': release['snapshot_sha256'],
        'logical_data_hash': release['logical_data_hash'],
        'projection_version': release['projection_version'],
        'source_data_hash': release['source_data_hash'],
        'row_counts': {table: release[field] for table, field in COUNT_FIELDS.items()},
    }
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise SyncError('Archived snapshot does not match the active D1 release')
    # upstream_sha can advance without changing data; the manifest retains origin.


def diff_states(old, new):
    patch, summary = {}, {}
    for table, _ in legacy.TABLES:
        a, b = old[table], new[table]
        inserts = [b[k] for k in sorted(b.keys() - a.keys())]
        deletes = [a[k] for k in sorted(a.keys() - b.keys())]
        updates = []
        for key in sorted(a.keys() & b.keys()):
            changed = [col for col in b[key] if a[key][col] != b[key][col]]
            if changed:
                updates.append({'old': a[key], 'new': b[key], 'changed': changed})
        patch[table] = {'insert': inserts, 'delete': deletes, 'update': updates}
        summary[table] = {name: len(rows) for name, rows in patch[table].items()}
    return patch, summary


def estimate_writes(patch):
    # Table + revision trigger + two assertion writes, plus conservative index
    # delete/insert costs. This is a budget estimate, not D1 billing telemetry.
    estimate, operations = 20, 0
    for table, changes in patch.items():
        for kind, rows in changes.items():
            for row in rows:
                operations += 1
                if kind == 'update':
                    affected = sum(bool(set(index) & set(row['changed'])) for index in INDEXES[table])
                    estimate += 4 + 2 * affected
                else:
                    estimate += 4 + len(INDEXES[table]) + int(table == 'Record' and kind == 'insert')
    return operations, estimate


def statement(sql, params=()):
    return {'sql': sql, 'params': list(params)}


def assertion(predicate, params=()):
    return statement(
        'INSERT INTO OierSyncGuard(id,ok) VALUES(1,CASE WHEN (' + predicate +
        ') THEN 1 ELSE 0 END) ON CONFLICT(id) DO UPDATE SET ok=excluded.ok', params,
    )


def release_assertion(base, revision):
    conditions = ['id=1'] + [f'{field} IS ?' for field in RELEASE_FIELDS]
    return assertion(
        f'EXISTS(SELECT 1 FROM DataRelease WHERE {" AND ".join(conditions)}) '
        'AND (SELECT revision FROM OierSyncState WHERE id=1) IS ? '
        'AND (SELECT writing FROM OierSyncState WHERE id=1)=0',
        [base.get(field) for field in RELEASE_FIELDS] + [revision],
    )


def row_predicate(row):
    return ' AND '.join(f'{col} IS ?' for col in row), list(row.values())


def mutation_statements(table, kind, row):
    statements = []
    if kind == 'update':
        old, new = row['old'], row['new']
    elif kind == 'delete':
        old, new = row, None
    else:
        old, new = None, row
    key_row = {col: (old or new)[col] for col in snapshots.KEYS[table]}
    key_where, key_params = row_predicate(key_row)
    if old is not None:
        where, params = row_predicate(old)
        statements.append(assertion(f'(SELECT COUNT(*) FROM {table} WHERE {key_where})=1 AND EXISTS(SELECT 1 FROM {table} WHERE {where})', key_params + params))
    else:
        statements.append(assertion(f'NOT EXISTS(SELECT 1 FROM {table} WHERE {key_where})', key_params))
    if kind == 'delete':
        statements.append(statement(f'DELETE FROM {table} WHERE {key_where}', key_params))
        statements.append(assertion(f'changes()=1 AND NOT EXISTS(SELECT 1 FROM {table} WHERE {key_where})', key_params))
    elif kind == 'insert':
        columns = list(new)
        statements.append(statement(f'INSERT INTO {table} ({", ".join(columns)}) VALUES ({", ".join("?" for _ in columns)})', list(new.values())))
    else:
        columns = row['changed']
        statements.append(statement(f'UPDATE {table} SET {", ".join(col + "=?" for col in columns)} WHERE {key_where}', [new[col] for col in columns] + key_params))
    if new is not None:
        where, params = row_predicate(new)
        statements.append(assertion(f'changes()=1 AND (SELECT COUNT(*) FROM {table} WHERE {key_where})=1 AND EXISTS(SELECT 1 FROM {table} WHERE {where})', key_params + params))
    return statements


def publication_values(manifest, commit, *, source_sha, source_hash, worker_version, run_url, revision):
    if not snapshots.SHA.fullmatch(commit or '') or not snapshots.SHA.fullmatch(source_sha or ''):
        raise SyncError('Invalid publication commit identity')
    if source_hash != manifest['source_data_hash'] or not snapshots.HASH.fullmatch(source_hash or ''):
        raise SyncError('Publication source fingerprint differs from its archive')
    if type(revision) is not int or revision < 0:
        raise SyncError('Invalid publication core revision')
    return {
        'upstream_sha': source_sha,
        'data_hash': manifest['data_hash'],
        'source_data_hash': source_hash,
        'worker_version': worker_version,
        'status': 'active',
        **{field: manifest['row_counts'][table] for table, field in COUNT_FIELDS.items()},
        'snapshot_commit': commit,
        'snapshot_sha256': manifest['archive_sha256'],
        'projection_version': manifest['projection_version'],
        'logical_data_hash': manifest['logical_data_hash'],
        'core_revision': revision,
        'github_run_url': run_url,
    }


def release_update(values, activate):
    keys = list(values)
    return statement('UPDATE DataRelease SET ' + ', '.join(key + '=?' for key in keys) +
                     ', updated_at=CURRENT_TIMESTAMP' +
                     (', activated_at=CURRENT_TIMESTAMP' if activate else '') + ' WHERE id=1', list(values.values()))


def validate_packet(statements):
    for item in statements:
        if len(item['sql'].encode('utf-8')) > 100000 or len(item['params']) > 100:
            raise SyncError('Delta exceeds a D1 statement limit; publishing stopped')
    if len(json.dumps({'batch': statements}, ensure_ascii=False, allow_nan=False).encode()) > MAX_REQUEST_BYTES:
        raise SyncError('Delta exceeds the atomic request size budget; publishing stopped')


def build_transaction(base, base_revision, patch, target, limits):
    if set(target) != set(RELEASE_FIELDS) | {'github_run_url'}:
        raise SyncError('Unexpected publication metadata fields')
    operations, estimate = estimate_writes(patch)
    if operations > limits.max_operations or estimate > limits.max_estimated_writes:
        raise SyncError(f'Delta exceeds the atomic publishing budget ({operations} row operations, {estimate} estimated writes); no full-upload fallback')
    if target['core_revision'] != base_revision + operations:
        raise SyncError('Incorrect target core revision')
    commands = [release_assertion(base, base_revision), assertion(
        "COALESCE((SELECT estimated_writes FROM OierSyncBudget WHERE day=date('now')),0)+?<=?",
        [estimate, limits.daily_write_budget],
    ), statement('UPDATE OierSyncState SET writing=1 WHERE id=1 AND writing=0'),
        assertion('changes()=1 AND (SELECT writing FROM OierSyncState WHERE id=1)=1')]
    for table in ('School', 'Contest', 'OIer'):
        for kind in ('insert', 'update'):
            for row in patch[table][kind]:
                commands.extend(mutation_statements(table, kind, row))
    for kind in ('delete', 'update', 'insert'):
        for row in patch['Record'][kind]:
            commands.extend(mutation_statements('Record', kind, row))
    for table in ('OIer', 'Contest', 'School'):
        for row in patch[table]['delete']:
            commands.extend(mutation_statements(table, 'delete', row))
    commands += [
        assertion('(SELECT revision FROM OierSyncState WHERE id=1) IS ?', [target['core_revision']]),
        statement('UPDATE OierSyncState SET writing=0 WHERE id=1 AND writing=1'),
        assertion('changes()=1 AND (SELECT writing FROM OierSyncState WHERE id=1)=0'),
        statement("INSERT INTO OierSyncBudget(day,estimated_writes) VALUES(date('now'),?) ON CONFLICT(day) DO UPDATE SET estimated_writes=estimated_writes+excluded.estimated_writes", [estimate]),
        assertion("(SELECT estimated_writes FROM OierSyncBudget WHERE day=date('now'))<=?", [limits.daily_write_budget]),
        release_update(target, activate=operations > 0),
        release_assertion(target, target['core_revision']),
    ]
    validate_packet(commands)
    return commands


def publish(client, base, base_revision, patch, target, limits):
    if target.get('snapshot_commit') == '0' * 40:
        raise SyncError('Unarchived candidate cannot be published')
    current, revision = client.current()
    if release_identity(current) == release_identity(target):
        return {'status': 'already_applied', 'core_revision': revision}
    if release_identity(current) != release_identity(base) or revision != base_revision:
        raise SyncError('Active release changed after planning; refusing a stale delta')
    commands = build_transaction(base, base_revision, patch, target, limits)
    try:
        response = client.batch(commands)
    except Exception as error:
        # Never blindly retry a write after a network timeout or uncertain response.
        try:
            actual, revision = client.current()
        except Exception:
            raise SyncError('Publish outcome is unknown. Re-read DataRelease before any retry; no further writes were attempted.') from error
        if release_identity(actual) == release_identity(target):
            return {'status': 'committed_response_lost', 'core_revision': revision}
        if release_identity(actual) == release_identity(base) and revision == base_revision:
            raise SyncError('Publish did not commit; the previous release and snapshot remain active') from error
        raise SyncError('Unexpected release after an uncertain publish; operator audit required') from error
    actual, revision = client.current()
    if release_identity(actual) != release_identity(target):
        raise SyncError('Publish response did not match the active release; stop and audit before retrying')
    results = response.get('result', [])
    if len(results) != len(commands) or any(not r.get('success') for r in results):
        # The committed marker is authoritative even if response telemetry is absent.
        return {'status': 'committed_telemetry_incomplete', 'core_revision': revision}
    return {
        'status': 'committed', 'core_revision': revision,
        'rows_read': sum(r.get('meta', {}).get('rows_read', 0) for r in results),
        'rows_written': sum(r.get('meta', {}).get('rows_written', 0) for r in results),
    }


def bootstrap(client, archive_store, workspace, stats_generator):
    """Read the existing live data once, archive it, and atomically attach its identity."""
    base, revision = client.current()
    if base.get('snapshot_commit'):
        return base
    rows = {}
    for table, columns in legacy.TABLES:
        primary_key = 'uid' if table == 'OIer' else 'id'
        cursor = None
        rows[table] = []
        while True:
            where = f'WHERE {primary_key}>?' if cursor is not None else ''
            params = [cursor, 5000] if cursor is not None else [5000]
            page = client.query(f'SELECT {", ".join(columns)} FROM {table} {where} ORDER BY {primary_key} LIMIT ?', params)
            if not page:
                break
            if cursor is not None and page[-1][primary_key] <= cursor:
                raise SyncError('Non-progressing bootstrap pagination')
            rows[table].extend(page)
            cursor = page[-1][primary_key]
            if len(rows[table]) > base[COUNT_FIELDS[table]]:
                raise SyncError('Production row count changed during bootstrap')
    actual, after_revision = client.current()
    if release_identity(actual) != release_identity(base) or after_revision != revision:
        raise SyncError('Production changed while reading the bootstrap snapshot')
    workspace = Path(workspace)
    database = workspace / 'bootstrap.db'
    database.unlink(missing_ok=True)
    state = snapshots.write_core_database(database, rows)
    if snapshots.row_counts(state) != {table: base[field] for table, field in COUNT_FIELDS.items()}:
        raise SyncError('Bootstrap row counts differ from the published release')
    stats = workspace / 'bootstrap-stats.json'
    stats_generator(database, stats)
    directory = workspace / 'bootstrap-archive'
    manifest = snapshots.create_archive(database, stats, directory, source_sha=base['upstream_sha'],
        source_hash=base['source_data_hash'], projection='legacy-audited-v1', worker_version=base.get('worker_version'))
    commit = archive_store(directory)
    target = publication_values(manifest, commit, source_sha=base['upstream_sha'], source_hash=base['source_data_hash'],
        worker_version=base.get('worker_version'), run_url=base.get('github_run_url'), revision=revision)
    empty_patch = {table: {'insert': [], 'update': [], 'delete': []} for table, _ in legacy.TABLES}
    publish(client, base, revision, empty_patch, target, Limits())
    return client.current()[0]

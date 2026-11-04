import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from cloudflare.script import sync_snapshot as snapshots
from cloudflare.script.test_incremental_d1 import OLD_ROWS, archive_fixture


def git_repository(root):
    remote, repo = root / 'remote.git', root / 'code'
    repo.mkdir()
    snapshots.git(root, 'init', '--bare', str(remote))
    snapshots.git(repo, 'init', '--initial-branch=main')
    snapshots.git(repo, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                  'commit', '--allow-empty', '-m', 'Code checkout')
    snapshots.git(repo, 'remote', 'add', 'origin', str(remote))
    snapshots.git(repo, 'push', 'origin', 'main')
    return repo


class SnapshotGitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = git_repository(self.root)
        self.database = self.root / 'data.db'
        snapshots.write_core_database(self.database, OLD_ROWS)
        self.directory = self.root / 'archive'
        self.manifest = archive_fixture(self.database, self.directory)

    def test_orphan_snapshot_commit_does_not_change_code_checkout_and_is_reused(self):
        code_head = snapshots.git(self.repo, 'rev-parse', 'HEAD')
        commit = snapshots.store_archive(self.repo, self.directory)
        self.assertEqual(snapshots.git(self.repo, 'rev-parse', 'HEAD'), code_head)
        self.assertEqual(snapshots.git(self.repo, 'status', '--porcelain'), b'')
        self.assertEqual(snapshots.git(self.repo, 'rev-list', '--parents', '-1', commit).decode().split(), [commit])
        self.assertEqual(snapshots.store_archive(self.repo, self.directory), commit)
        snapshots.fetch_archive(self.repo, commit, self.root / 'download')
        manifest, state = snapshots.open_archive(self.root / 'download', self.root / 'restored.db')
        self.assertEqual(manifest, self.manifest)
        self.assertEqual(state, snapshots.read_state(self.database))

    def test_older_immutable_commit_can_be_fetched_after_branch_advances(self):
        old_commit = snapshots.store_archive(self.repo, self.directory)
        archive_fixture(self.database, self.directory, sha='4' * 40, fingerprint='b' * 64)
        new_commit = snapshots.store_archive(self.repo, self.directory)
        self.assertNotEqual(old_commit, new_commit)
        self.assertEqual(snapshots.git(self.repo, 'rev-parse', new_commit + '^').decode().strip(), old_commit)
        snapshots.fetch_archive(self.repo, old_commit, self.root / 'old-download')
        manifest, _ = snapshots.open_archive(self.root / 'old-download', self.root / 'restored.db')
        self.assertEqual(manifest, self.manifest)

    def test_archive_strips_extra_tables_and_ignores_record_id_churn(self):
        original = (self.directory / 'oier_data.db.gz').read_bytes()
        with sqlite3.connect(self.database) as db:
            db.execute('CREATE TABLE private_credentials(token TEXT)')
            db.execute("INSERT INTO private_credentials VALUES('never-archive-this')")
            db.execute('UPDATE Record SET id=id+1000')
        manifest = archive_fixture(self.database, self.directory)
        self.assertEqual((self.directory / 'oier_data.db.gz').read_bytes(), original)
        self.assertEqual(manifest, self.manifest)
        snapshots.open_archive(self.directory, self.root / 'restored.db')
        with sqlite3.connect(self.root / 'restored.db') as db:
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='private_credentials'").fetchone())

    def test_corrupt_candidate_at_branch_head_is_not_reused(self):
        good = snapshots.store_archive(self.repo, self.directory)
        blob = snapshots.git(self.repo, 'hash-object', '-w', '--stdin', data=b'corrupt').decode().strip()
        entries = []
        for name in snapshots.SNAPSHOT_FILES:
            object_id = blob if name.endswith('.gz') else snapshots.git(self.repo, 'rev-parse', f'{good}:{name}').decode().strip()
            entries.append(f'100644 blob {object_id}\t{name}\n')
        tree = snapshots.git(self.repo, 'mktree', data=''.join(entries).encode()).decode().strip()
        corrupt = snapshots.git(self.repo, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
            'commit-tree', tree, '-p', good, data=b'Corrupt candidate\n').decode().strip()
        snapshots.git(self.repo, 'push', 'origin', f'{corrupt}:refs/heads/data-state')
        with self.assertRaisesRegex(RuntimeError, 'does not match'):
            snapshots.store_archive(self.repo, self.directory)

    def test_competing_push_rejected_without_force_overwrite(self):
        first = snapshots.store_archive(self.repo, self.directory)
        archive_fixture(self.database, self.directory, sha='4' * 40, fingerprint='b' * 64)
        real_git = snapshots.git
        injected = False
        def competing(repo, *args, data=None):
            nonlocal injected
            if args[0] == 'push' and not injected:
                injected = True
                tree = real_git(repo, 'rev-parse', first + '^{tree}').decode().strip()
                other = real_git(repo, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                    'commit-tree', tree, '-p', first, data=b'Other writer\n').decode().strip()
                real_git(repo, 'push', 'origin', f'{other}:refs/heads/data-state')
            return real_git(repo, *args, data=data)
        from unittest.mock import patch
        with patch.object(snapshots, 'git', side_effect=competing):
            with self.assertRaisesRegex(RuntimeError, 'push'):
                snapshots.store_archive(self.repo, self.directory)


if __name__ == '__main__':
    unittest.main()

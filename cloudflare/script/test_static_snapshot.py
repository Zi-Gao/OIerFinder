import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from .build_static_snapshot import build
from . import sync_snapshot as snapshots
from .test_incremental_d1 import OLD_ROWS


class StaticSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'input.db'
        self.state = snapshots.write_core_database(self.source, OLD_ROWS)

    def package(self, output='data', **kwargs):
        return build(self.source, self.root / output, upstream_sha='1' * 40, worker_version='2' * 40, **kwargs)

    def test_complete_core_only_indexed_package(self):
        with sqlite3.connect(self.source) as db:
            db.execute('CREATE TABLE LuoguPrizes(private_value TEXT)')
            db.execute("INSERT INTO LuoguPrizes VALUES('never publish dynamic tables')")
        manifest = self.package(part_bytes=1024)
        compressed = b''
        for file in manifest['database']['parts']:
            data = (self.root / file['path'].lstrip('/')).read_bytes()
            self.assertEqual(len(data), file['bytes'])
            self.assertEqual(hashlib.sha256(data).hexdigest(), file['sha256'])
            compressed += data
        self.assertGreater(len(manifest['database']['parts']), 1)
        self.assertEqual(hashlib.sha256(compressed).hexdigest(), manifest['database']['compressed_sha256'])
        database = gzip.decompress(compressed)
        self.assertEqual(hashlib.sha256(database).hexdigest(), manifest['database']['sha256'])
        unpacked = self.root / 'unpacked.db'
        unpacked.write_bytes(database)
        self.assertEqual(snapshots.read_state(unpacked), self.state)
        with sqlite3.connect(unpacked) as db:
            self.assertEqual(db.execute("SELECT name FROM sqlite_master WHERE name='LuoguPrizes'").fetchall(), [])
            self.assertTrue(db.execute("SELECT name FROM sqlite_master WHERE name='idx_record_contest_level_uid'").fetchall())
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])
        stats_path = self.root / manifest['stats']['path'].lstrip('/')
        self.assertEqual(json.loads(stats_path.read_text()), snapshots.statistics(self.state))

    def test_repeated_builds_have_the_same_content_identity(self):
        self.assertEqual(self.package('first'), self.package('second'))

    def test_invalid_source_version_is_rejected(self):
        with self.assertRaises(ValueError):
            build(self.source, self.root / 'data', upstream_sha='main', worker_version='2' * 40)

    def test_broken_references_cannot_be_published(self):
        with sqlite3.connect(self.source) as db:
            db.execute('UPDATE Record SET oier_uid=9999')
        with self.assertRaisesRegex(ValueError, 'Broken snapshot reference'):
            self.package()

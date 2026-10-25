import contextlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import create_db
from calculate_stats import generate_stats_json


class UpstreamImportTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.generator = self.root / 'generator'
        self.dist = self.generator / 'dist'
        self.dist.mkdir(parents=True)
        # Deliberately use different numbering from the real upstream. The importer
        # must read this checkout's tables instead of copying fixed indices.
        (self.generator / 'util.py').write_text(
            "provinces = ['四川', '台湾']\n"
            "award_levels = ['一等奖', '金牌']\n"
            "contest_types = ['NGOI', 'CSP提高']\n"
            "raise RuntimeError('The importer must not execute this module')\n",
            encoding='utf-8',
        )
        self.static = {
            'schools': [
                ['测试学校', 0, '成都', 1.0],
                ['', -1, '', 0.0],
                ['另一学校', 1, '台北', 0.0],
            ],
            'contests': [
                {'name': 'NGOI 2026', 'type': 0, 'year': 2026,
                 'fall_semester': False, 'full_score': 400},
                {'name': 'CSP-S 2026', 'type': 1, 'year': 2026,
                 'fall_semester': True, 'full_score': 400},
            ],
        }
        self.result = '1,CS,测试选手,1,2020,10,0,0,0:0:350:1:0:0/1:2::2:1:1;2020\n'
        self.db_path = self.root / 'oier_data.db'
        self.patch = mock.patch.multiple(
            create_db,
            GENERATOR_DIR=self.generator,
            STATIC_FILE=self.dist / 'static.json',
            RESULT_FILE=self.dist / 'result.txt',
            DB_FILE=str(self.db_path),
        )
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def build(self):
        (self.dist / 'static.json').write_text(
            json.dumps(self.static, ensure_ascii=False), encoding='utf-8'
        )
        (self.dist / 'result.txt').write_text(self.result, encoding='utf-8')
        with contextlib.redirect_stdout(io.StringIO()):
            create_db.main()

    def test_decodes_numeric_fields_and_preserves_school_ids(self):
        self.build()
        with sqlite3.connect(self.db_path) as connection:
            self.assertEqual(connection.execute(
                'SELECT id, province FROM School ORDER BY id'
            ).fetchall(), [(0, '四川'), (1, ''), (2, '台湾')])
            self.assertEqual(connection.execute(
                'SELECT c.type, s.name, r.province, r.level, r.score '
                'FROM Record r JOIN Contest c ON c.id = r.contest_id '
                'JOIN School s ON s.id = r.school_id ORDER BY r.id'
            ).fetchall(), [
                ('NGOI', '测试学校', '四川', '一等奖', 350.0),
                ('CSP提高', '另一学校', '台湾', '金牌', None),
            ])
            self.assertEqual(connection.execute('PRAGMA foreign_key_check').fetchall(), [])

        stats_path = self.root / 'stats.json'
        with contextlib.redirect_stdout(io.StringIO()):
            generate_stats_json(str(self.db_path), str(stats_path))
        stats = json.loads(stats_path.read_text(encoding='utf-8'))['stats']
        self.assertEqual(stats['2026']['NGOI']['四川']['一等奖'], 1)

    def test_accepts_readable_static_fields(self):
        self.static['schools'][0][1] = '四川'
        self.static['contests'][0]['type'] = 'NGOI'
        self.build()
        with sqlite3.connect(self.db_path) as connection:
            self.assertEqual(connection.execute(
                'SELECT type FROM Contest WHERE id = 0'
            ).fetchone(), ('NGOI',))

    def test_missing_encoding_tables_keep_the_existing_database(self):
        self.db_path.write_bytes(b'existing database')
        (self.generator / 'util.py').write_text(
            "provinces = ['四川']\naward_levels = ['一等奖']\n", encoding='utf-8'
        )
        with self.assertRaisesRegex(ValueError, 'Missing upstream encoding tables'):
            self.build()
        self.assertEqual(self.db_path.read_bytes(), b'existing database')

    def test_unknown_indices_keep_the_existing_database(self):
        original = b'existing database must remain intact'
        cases = (
            ('contest type', lambda: self.static['contests'][0].update(type=-1)),
            ('school province', lambda: self.static['schools'][0].__setitem__(1, 99)),
            ('record province', lambda: setattr(self, 'result', self.result.replace(':0:0/', ':99:0/'))),
            ('award level', lambda: setattr(self, 'result', self.result.replace(':0:0/', ':0:99/'))),
        )
        for field, change in cases:
            with self.subTest(field=field):
                saved_static = json.loads(json.dumps(self.static))
                saved_result = self.result
                self.db_path.write_bytes(original)
                change()
                with self.assertRaisesRegex(ValueError, field):
                    self.build()
                self.assertEqual(self.db_path.read_bytes(), original)
                self.assertEqual(list(self.root.glob('.oier_data.db.*.tmp')), [])
                self.static, self.result = saved_static, saved_result


if __name__ == '__main__':
    unittest.main()

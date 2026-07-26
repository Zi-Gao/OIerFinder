import json
import tempfile
import unittest
from pathlib import Path

from cloudflare.script.data_fingerprint import calculate_source_data_hash


class SourceDataFingerprintTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.static_path = self.root / "static.json"
        self.result_path = self.root / "result.txt"
        self.result_path.write_text("1,Alice\\n", encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_static(self, data, **dump_options):
        self.static_path.write_text(
            json.dumps(data, ensure_ascii=False, **dump_options),
            encoding="utf-8",
        )

    def test_ignores_json_formatting_and_object_key_order(self):
        self.write_static(
            {
                "contests": [{"year": 2025, "name": "NOI"}],
                "schools": [["学校", "北京", "北京", 1.0]],
            },
            indent=2,
        )
        first_hash = calculate_source_data_hash(
            self.static_path,
            self.result_path,
        )

        self.write_static(
            {
                "schools": [["学校", "北京", "北京", 1.0]],
                "contests": [{"name": "NOI", "year": 2025}],
            },
            separators=(",", ":"),
        )
        second_hash = calculate_source_data_hash(
            self.static_path,
            self.result_path,
        )

        self.assertEqual(first_hash, second_hash)

    def test_detects_array_order_and_result_changes(self):
        self.write_static({"schools": [["A"], ["B"]], "contests": []})
        original_hash = calculate_source_data_hash(
            self.static_path,
            self.result_path,
        )

        self.write_static({"schools": [["B"], ["A"]], "contests": []})
        reordered_hash = calculate_source_data_hash(
            self.static_path,
            self.result_path,
        )
        self.assertNotEqual(original_hash, reordered_hash)

        self.write_static({"schools": [["A"], ["B"]], "contests": []})
        self.result_path.write_text("2,Bob\\n", encoding="utf-8")
        changed_result_hash = calculate_source_data_hash(
            self.static_path,
            self.result_path,
        )
        self.assertNotEqual(original_hash, changed_result_hash)


if __name__ == "__main__":
    unittest.main()

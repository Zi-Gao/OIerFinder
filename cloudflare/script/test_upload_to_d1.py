import unittest
from unittest.mock import patch

from cloudflare.script import upload_to_d1


class ReleaseMetadataTests(unittest.TestCase):
    @patch.object(upload_to_d1, "_execute_d1_request")
    @patch.object(upload_to_d1, "execute_d1_sql")
    def test_get_release_tolerates_schema_before_source_hash_migration(
        self,
        _execute_d1_sql,
        execute_d1_request,
    ):
        execute_d1_request.side_effect = [
            {
                "result": [
                    {
                        "results": [
                            {"name": "id"},
                            {"name": "upstream_sha"},
                            {"name": "data_hash"},
                        ]
                    }
                ]
            },
            {
                "result": [
                    {
                        "results": [
                            {
                                "upstream_sha": "1" * 40,
                                "data_hash": "a" * 64,
                                "source_data_hash": None,
                                "status": "active",
                            }
                        ]
                    }
                ]
            },
        ]

        release = upload_to_d1.get_release({})

        select_payload = execute_d1_request.call_args_list[1].args[2]
        self.assertIn(
            "NULL AS source_data_hash",
            select_payload["sql"],
        )
        self.assertIsNone(release["source_data_hash"])

    @patch.object(upload_to_d1, "get_release")
    @patch.object(upload_to_d1, "execute_d1_batch")
    def test_advance_release_source_sha_is_guarded_by_active_hash(
        self,
        execute_d1_batch,
        get_release,
    ):
        source_sha = "1" * 40
        source_data_hash = "a" * 64
        get_release.return_value = {
            "upstream_sha": source_sha,
            "source_data_hash": source_data_hash,
            "status": "active",
        }

        upload_to_d1.advance_release_source_sha(
            {},
            source_sha,
            source_data_hash,
        )

        statement = execute_d1_batch.call_args.args[1][0]
        self.assertIn("status = 'active'", statement["sql"])
        self.assertIn("source_data_hash = ?2", statement["sql"])
        self.assertEqual(statement["params"], [source_sha, source_data_hash])

    @patch.object(upload_to_d1, "get_release")
    @patch.object(upload_to_d1, "execute_d1_batch")
    def test_advance_release_source_sha_rejects_races(
        self,
        _execute_d1_batch,
        get_release,
    ):
        get_release.return_value = {
            "upstream_sha": "2" * 40,
            "source_data_hash": "b" * 64,
            "status": "active",
        }

        with self.assertRaisesRegex(RuntimeError, "无法推进"):
            upload_to_d1.advance_release_source_sha(
                {},
                "1" * 40,
                "a" * 64,
            )

    @patch.object(upload_to_d1, "get_release")
    @patch.object(upload_to_d1, "execute_d1_batch")
    def test_initialize_source_hash_only_updates_matching_active_release(
        self,
        execute_d1_batch,
        get_release,
    ):
        source_sha = "1" * 40
        source_data_hash = "a" * 64
        get_release.return_value = {
            "upstream_sha": source_sha,
            "source_data_hash": source_data_hash,
            "status": "active",
        }

        upload_to_d1.initialize_release_source_data_hash(
            {},
            source_sha,
            source_data_hash,
        )

        statement = execute_d1_batch.call_args.args[1][0]
        self.assertIn("upstream_sha = ?1", statement["sql"])
        self.assertIn("source_data_hash IS NULL", statement["sql"])
        self.assertEqual(statement["params"], [source_sha, source_data_hash])

    @patch.object(upload_to_d1, "execute_d1_batch")
    def test_promote_persists_both_artifact_and_source_hashes(
        self,
        execute_d1_batch,
    ):
        counts = {
            "OIer": 1,
            "Contest": 2,
            "School": 3,
            "Record": 4,
        }
        metadata = {
            "source_sha": "1" * 40,
            "data_hash": "a" * 64,
            "source_data_hash": "b" * 64,
            "worker_version": "2" * 40,
            "run_url": "https://example.invalid/run",
        }

        upload_to_d1.promote_staging_tables({}, counts, metadata)

        statements = execute_d1_batch.call_args.args[1]
        release_statement = next(
            statement for statement in statements
            if isinstance(statement, dict)
        )
        self.assertIn("source_data_hash", release_statement["sql"])
        self.assertEqual(
            release_statement["params"],
            [
                metadata["source_sha"],
                metadata["data_hash"],
                metadata["source_data_hash"],
                metadata["worker_version"],
                1,
                2,
                3,
                4,
                metadata["run_url"],
            ],
        )


if __name__ == "__main__":
    unittest.main()

import json
import unittest
from unittest.mock import patch

from cloudflare.script import upload_to_d1


class ReleaseMetadataTests(unittest.TestCase):
    @patch.object(upload_to_d1.requests, 'post')
    def test_json_payload_is_sent_as_compact_utf8_without_changing_values(self, post):
        post.return_value.ok = True
        post.return_value.json.return_value = {'success': True, 'result': [{'success': True}]}
        payload = {'sql': 'SELECT ?', 'params': ['中文😀\n\\"']}
        cfg = {'cloudflare': {'account_id': 'test-account', 'database_id': 'test-database', 'api_token': 'test-token'}}
        upload_to_d1._execute_d1_request(cfg, 'query', payload)
        body = post.call_args.kwargs['data']
        self.assertEqual(json.loads(body), payload)
        self.assertIn('中文😀'.encode(), body)
        self.assertNotIn('json', post.call_args.kwargs)

    @patch.object(upload_to_d1.requests, 'post')
    def test_internal_errors_keep_retry_classification_without_resending_http_requests(self, post):
        post.return_value.ok = False
        post.return_value.status_code = 500
        post.return_value.json.return_value = {'errors': [{'code': 7500, 'message': 'internal error'}]}
        cfg = {'cloudflare': {'account_id': 'test-account', 'database_id': 'test-database', 'api_token': 'test-token'}}
        with self.assertRaises(upload_to_d1.D1RequestError) as error:
            upload_to_d1._execute_d1_request(cfg, 'query', {'sql': 'SELECT 1'})
        self.assertTrue(upload_to_d1.is_retryable_d1_error(error.exception))
        post.assert_called_once()

    @patch.object(upload_to_d1, 'execute_d1_batch')
    @patch.object(upload_to_d1, '_execute_d1_request')
    @patch.object(upload_to_d1, 'get_release')
    def test_full_upload_cannot_run_after_incremental_migration_even_before_bootstrap(
        self, get_release, request, write_batch,
    ):
        get_release.return_value = {'snapshot_commit': None}
        request.return_value = {'result': [{'results': [{'name': 'OierSyncState'}]}]}
        with self.assertRaisesRegex(RuntimeError, 'before any staging writes'):
            upload_to_d1.upload_database({})
        write_batch.assert_not_called()

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

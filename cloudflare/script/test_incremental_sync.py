import json
from pathlib import Path
from unittest.mock import patch
import unittest

from cloudflare.script import incremental_d1 as sync
from cloudflare.script import incremental_sync as workflow
from cloudflare.script import sync_snapshot as snapshots
from cloudflare.script.test_incremental_d1 import PublishingFixture, archive_fixture
from cloudflare.script.test_sync_snapshot import git_repository


class WorkflowPublishingTests(PublishingFixture):
    def setUp(self):
        super().setUp()
        self.repo = git_repository(self.root)
        self.old_commit = snapshots.store_archive(self.repo, self.root / 'archive-old')
        self.client.db.execute('UPDATE DataRelease SET snapshot_commit=? WHERE id=1', [self.old_commit])
        self.base = self.client.current()[0]
        self.workspace = self.root / 'workspace'
        self.workspace.mkdir()
        self.projection = patch.object(snapshots, 'projection_version', return_value='test-projection')
        self.projection.start()
        self.addCleanup(self.projection.stop)

    def prepare(self, sha='4' * 40, fingerprint='b' * 64, database=None, stats=None, event='schedule'):
        workflow.inspect_run(self.client, self.workspace, sha, event)
        return workflow.prepare_run(self.client, self.repo, self.workspace,
            database=database or self.new, stats=stats or self.root / 'archive-new-stats.json',
            source_hash=fingerprint, worker_version='2' * 40, run_url='https://example.invalid/new',
            stats_output=self.root / 'worker-stats.json')

    def test_candidate_archival_does_not_advance_d1_until_successful_transaction(self):
        self.prepare()
        candidate = workflow.archive_run(self.repo, self.workspace)
        self.assertNotEqual(candidate, self.old_commit)
        self.assertEqual(self.client.release()['snapshot_commit'], self.old_commit)
        result = workflow.publish_run(self.client, self.repo, self.workspace)
        self.assertEqual(result['status'], 'committed')
        self.assertEqual(self.client.release()['snapshot_commit'], candidate)
        self.assertEqual(snapshots.read_state(self.old), self.new_state)

    def test_rejected_validation_keeps_auditable_delta_and_cannot_be_archived_or_published(self):
        workflow.inspect_run(self.client, self.workspace, '4' * 40, 'schedule')
        with patch.object(sync, 'validate_packet', side_effect=sync.SyncError('D1 statement limit')):
            with self.assertRaisesRegex(sync.SyncError, 'D1 statement limit'):
                workflow.prepare_run(self.client, self.repo, self.workspace,
                    database=self.new, stats=self.root / 'archive-new-stats.json',
                    source_hash='b' * 64, worker_version='2' * 40,
                    stats_output=self.root / 'worker-stats.json')
        plan = json.loads((self.workspace / 'plan.json').read_text())
        self.assertEqual(plan['status'], 'blocked')
        self.assertEqual(plan['summary'], self.summary)
        self.assertEqual(plan['row_operations'], sync.estimate_writes(self.patch)[0])
        self.assertIn('D1 statement limit', plan['validation_error'])
        with self.assertRaisesRegex(sync.SyncError, 'Blocked publication plan'):
            workflow.archive_run(self.repo, self.workspace)
        with self.assertRaisesRegex(sync.SyncError, 'Blocked publication plan'):
            workflow.publish_run(self.client, self.repo, self.workspace)
        self.assertEqual(self.client.batch_count, 0)
        self.assertEqual(self.client.release()['snapshot_commit'], self.old_commit)

    def test_publish_failure_is_audited_and_retry_plans_from_the_old_snapshot(self):
        self.prepare()
        workflow.archive_run(self.repo, self.workspace)
        self.client.fail_at = 7
        self.client.fail_error = RuntimeError('Cloudflare quota exhausted')
        with self.assertRaises(sync.SyncError):
            workflow.publish_run(self.client, self.repo, self.workspace)
        result = json.loads((self.workspace / 'publish-result.json').read_text())
        self.assertEqual(result['status'], 'not_committed')
        self.assertTrue(result['publication_attempted'])
        self.assertIn('quota exhausted', result['error'])
        self.assertEqual(result['active_snapshot_commit'], self.old_commit)
        self.client.fail_at = None
        self.prepare()
        workflow.archive_run(self.repo, self.workspace)
        self.assertEqual(workflow.publish_run(self.client, self.repo, self.workspace)['status'], 'committed')
        self.assertEqual(snapshots.read_state(self.old), self.new_state)

    def test_unknown_publish_outcome_is_audited_without_another_write(self):
        self.prepare()
        workflow.archive_run(self.repo, self.workspace)
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
            with self.assertRaises(sync.SyncError):
                workflow.publish_run(self.client, self.repo, self.workspace)
        result = json.loads((self.workspace / 'publish-result.json').read_text())
        self.assertEqual(result['status'], 'outcome_unknown')
        self.assertEqual(self.client.batch_count, 1)

    def test_failure_keeps_old_pointer_and_retry_reuses_unpublished_candidate(self):
        self.prepare()
        candidate = workflow.archive_run(self.repo, self.workspace)
        self.client.fail_at = 5
        with self.assertRaises(sync.SyncError):
            workflow.publish_run(self.client, self.repo, self.workspace)
        self.assertEqual(self.client.release()['snapshot_commit'], self.old_commit)
        self.assertEqual(snapshots.read_state(self.old), self.old_state)
        self.client.fail_at = None
        self.prepare()
        self.assertEqual(workflow.archive_run(self.repo, self.workspace), candidate)
        workflow.publish_run(self.client, self.repo, self.workspace)
        self.assertEqual(snapshots.read_state(self.old), self.new_state)

    def test_publisher_uses_exact_commit_even_if_branch_head_moves(self):
        self.prepare()
        candidate = workflow.archive_run(self.repo, self.workspace)
        directory = self.root / 'another-candidate'
        archive_fixture(self.new, directory, sha='6' * 40, fingerprint='c' * 64)
        newer = snapshots.store_archive(self.repo, directory)
        self.assertNotEqual(candidate, newer)
        workflow.publish_run(self.client, self.repo, self.workspace)
        self.assertEqual(self.client.release()['snapshot_commit'], candidate)

    def test_publication_forbidden_before_archival(self):
        self.prepare()
        with self.assertRaisesRegex(sync.SyncError, 'archived'):
            workflow.publish_run(self.client, self.repo, self.workspace)
        self.assertEqual(self.client.batch_count, 0)
        result = json.loads((self.workspace / 'publish-result.json').read_text())
        self.assertEqual(result['status'], 'blocked')
        self.assertFalse(result['publication_attempted'])

    def test_failed_git_push_keeps_d1_unchanged(self):
        self.prepare()
        real_git = snapshots.git
        def fail_push(repo, *args, data=None):
            if args[0] == 'push':
                raise RuntimeError('Push refused')
            return real_git(repo, *args, data=data)
        with patch.object(snapshots, 'git', side_effect=fail_push):
            with self.assertRaisesRegex(RuntimeError, 'Push refused'):
                workflow.archive_run(self.repo, self.workspace)
        self.assertEqual(self.client.batch_count, 0)
        self.assertEqual(self.client.release()['snapshot_commit'], self.old_commit)

    def test_non_data_upstream_change_only_advances_metadata_and_keeps_snapshot(self):
        plan = self.prepare(sha='6' * 40, fingerprint='a' * 64,
            database=self.old, stats=self.root / 'archive-old-stats.json')
        self.assertEqual(plan['row_operations'], 0)
        self.assertFalse(plan['needs_snapshot'])
        self.assertFalse(plan['should_deploy_worker'])
        self.assertEqual(workflow.archive_run(self.repo, self.workspace), self.old_commit)
        workflow.publish_run(self.client, self.repo, self.workspace)
        self.assertEqual(self.client.revision(), 0)
        self.assertEqual(self.client.release()['upstream_sha'], '6' * 40)
        self.assertEqual(self.client.release()['snapshot_commit'], self.old_commit)

    def test_same_upstream_and_projection_skip_scheduled_build(self):
        control = workflow.inspect_run(self.client, self.workspace, self.base['upstream_sha'], 'schedule')
        self.assertFalse(control['should_generate'])
        self.assertFalse(control['should_run'])

    def test_missing_payload_migration_requests_schema_setup_without_data_rebuild(self):
        self.client.db.execute('DROP TABLE OierSyncPayload')
        control = workflow.inspect_run(self.client, self.workspace, self.base['upstream_sha'], 'schedule')
        self.assertTrue(control['needs_schema'])
        self.assertTrue(control['should_run'])
        self.assertFalse(control['should_generate'])

    def test_importer_change_forces_inspection_at_same_upstream_version(self):
        with patch.object(snapshots, 'projection_version', return_value='new-projection'):
            control = workflow.inspect_run(self.client, self.workspace, self.base['upstream_sha'], 'schedule')
        self.assertTrue(control['should_generate'])

    def test_worker_only_push_restores_statistics_from_published_snapshot(self):
        workflow.inspect_run(self.client, self.workspace, self.base['upstream_sha'], 'push')
        plan = workflow.prepare_run(self.client, self.repo, self.workspace, worker_version='2' * 40,
            stats_output=self.root / 'worker-stats.json')
        self.assertFalse(plan['requires_publish'])
        self.assertTrue(plan['should_deploy_worker'])
        self.assertEqual(json.loads((self.root / 'worker-stats.json').read_text()), snapshots.statistics(self.old_state))
        self.assertEqual(self.client.batch_count, 0)

    def test_modified_candidate_plan_cannot_publish_wrong_snapshot(self):
        self.prepare()
        workflow.archive_run(self.repo, self.workspace)
        path = self.workspace / 'plan.json'
        plan = json.loads(path.read_text())
        plan['target']['logical_data_hash'] = '0' * 64
        path.write_text(json.dumps(plan))
        with self.assertRaises(sync.SyncError):
            workflow.publish_run(self.client, self.repo, self.workspace)
        self.assertEqual(self.client.batch_count, 0)

    def test_source_version_cannot_be_changed_after_candidate_is_archived(self):
        self.prepare()
        workflow.archive_run(self.repo, self.workspace)
        path = self.workspace / 'plan.json'
        plan = json.loads(path.read_text())
        plan['target']['upstream_sha'] = '9' * 40
        path.write_text(json.dumps(plan))
        with self.assertRaisesRegex(sync.SyncError, 'inspected source'):
            workflow.publish_run(self.client, self.repo, self.workspace)
        self.assertEqual(self.client.batch_count, 0)

    def test_changed_target_database_cannot_receive_an_existing_plan(self):
        self.prepare()
        workflow.archive_run(self.repo, self.workspace)
        with patch.object(self.client, 'identity', return_value={'account_id': 'test-account', 'database_id': 'other-database'}):
            with self.assertRaisesRegex(sync.SyncError, 'D1 target changed'):
                workflow.publish_run(self.client, self.repo, self.workspace)
        self.assertEqual(self.client.batch_count, 0)

    def test_cli_target_must_match_the_worker_binding(self):
        with self.assertRaisesRegex(sync.SyncError, 'Worker DB binding'):
            workflow.validate_target_config({'cloudflare': {'database_id': 'not-the-worker-database'}})


if __name__ == '__main__':
    unittest.main()

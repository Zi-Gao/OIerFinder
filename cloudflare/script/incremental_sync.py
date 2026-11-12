"""GitHub Actions entry points: inspect -> prepare -> archive -> publish.

Only publish writes core data. Archive creates immutable candidates first; D1's
snapshot_commit is the sole authority for which candidate was actually released.
"""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

if __package__:
    from . import incremental_d1 as sync
    from . import sync_snapshot as snapshots
    from .upload_to_d1 import load_config
else:
    import incremental_d1 as sync
    import sync_snapshot as snapshots
    from upload_to_d1 import load_config


def save_json(path, data):
    path = Path(path)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    os.replace(temp, path)


def output(name, value):
    value = str(value).lower() if isinstance(value, bool) else str(value)
    if '\n' in value or '\r' in value:
        raise ValueError('Invalid workflow output')
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as target:
            target.write(f'{name}={value}\n')


def stats_generator(database, path):
    subprocess.run([sys.executable, str(snapshots.ROOT / 'calculate_stats.py'), '--db', str(database), '--output', str(path)], check=True)


def validate_target_config(cfg):
    """The CLI must never migrate one binding while publishing to another DB."""
    text = (snapshots.ROOT / 'cloudflare/worker/wrangler.toml').read_text()
    matches = []
    for part in re.split(r'(?m)^\s*\[\[d1_databases\]\]\s*$', text)[1:]:
        block = re.split(r'(?m)^\s*\[', part, maxsplit=1)[0]
        if re.search(r'(?m)^\s*binding\s*=\s*"DB"\s*(?:#.*)?$', block):
            ids = re.findall(r'(?m)^\s*database_id\s*=\s*"([0-9a-f-]+)"\s*(?:#.*)?$', block)
            matches.extend(ids)
    if len(matches) != 1 or cfg['cloudflare']['database_id'] != matches[0]:
        raise sync.SyncError('Configured D1 database does not match the Worker DB binding; no publication is allowed')


def inspect_run(client, workspace, upstream_sha, event_name, force=False):
    if not snapshots.SHA.fullmatch(upstream_sha):
        raise ValueError('A full upstream SHA is required')
    current, revision = client.current(allow_legacy=True)
    projection = snapshots.projection_version()
    needs_bootstrap = not current.get('snapshot_commit')
    should_generate = force or upstream_sha != current['upstream_sha'] or projection != current.get('projection_version')
    control = {
        'upstream_sha': upstream_sha, 'projection_version': projection,
        'needs_schema': revision is None, 'needs_bootstrap': needs_bootstrap,
        'should_generate': should_generate,
        'should_run': should_generate or needs_bootstrap or event_name == 'push',
        'event_name': event_name,
        'database': client.identity(),
        'observed_release': sync.release_identity(current),
    }
    save_json(Path(workspace) / 'inspection.json', control)
    for key in ('upstream_sha', 'needs_schema', 'needs_bootstrap', 'should_generate', 'should_run'):
        output(key, control[key])
    print(json.dumps({k: v for k, v in control.items() if k != 'observed_release'}, ensure_ascii=False))
    return control


def prepare_run(client, repo, workspace, *, database=None, stats=None, source_hash=None, worker_version=None, run_url=None, branch='data-state', limits=None, stats_output=None):
    workspace = Path(workspace)
    control = json.loads((workspace / 'inspection.json').read_text())
    if client.identity() != control['database']:
        raise sync.SyncError('D1 target changed since inspection')
    limits = limits or sync.Limits.from_env()
    current, _ = client.current()
    if sync.release_identity(current) != control['observed_release']:
        raise sync.SyncError('Production release changed since inspection; rerun from inspection')
    if not current.get('snapshot_commit'):
        current = sync.bootstrap(client, lambda directory: snapshots.store_archive(repo, directory, branch), workspace, stats_generator)
    current, revision = client.current()
    baseline_dir = workspace / 'baseline-archive'
    snapshots.fetch_archive(repo, current['snapshot_commit'], baseline_dir)
    baseline_manifest, old = snapshots.open_archive(baseline_dir, workspace / 'baseline.db')
    sync.assert_manifest_matches(current, baseline_manifest)
    new = old
    manifest = baseline_manifest
    needs_snapshot = False
    if control['should_generate']:
        if not database or not stats or not snapshots.HASH.fullmatch(source_hash or ''):
            raise ValueError('Generated database, statistics and source fingerprint are required')
        manifest = snapshots.create_archive(database, stats, workspace / 'candidate-archive',
            source_sha=control['upstream_sha'], source_hash=source_hash,
            projection=control['projection_version'], worker_version=worker_version)
        # Re-open the exact bytes that will be committed, not a mutable input file.
        manifest, new = snapshots.open_archive(workspace / 'candidate-archive', workspace / 'candidate-verified.db')
        needs_snapshot = any(manifest[k] != baseline_manifest[k] for k in (
            'logical_data_hash', 'source_data_hash', 'projection_version', 'stats_sha256',
        ))
    else:
        source_hash = current['source_data_hash']
    patch, summary = sync.diff_states(old, new)
    operations, estimate = sync.estimate_writes(patch)
    if not needs_snapshot and operations:
        raise sync.SyncError('Nonempty delta with no target snapshot')
    if not needs_snapshot:
        manifest = baseline_manifest
    target_commit = '0' * 40 if needs_snapshot else current['snapshot_commit']
    requires_publish = needs_snapshot or control['upstream_sha'] != current['upstream_sha']
    target = sync.publication_values(manifest, target_commit,
        source_sha=control['upstream_sha'], source_hash=source_hash,
        worker_version=worker_version if needs_snapshot else current.get('worker_version'),
        run_url=run_url, revision=revision + operations)
    plan = {
        'format_version': 1, 'base': sync.release_identity(current), 'base_revision': revision,
        'target': target, 'needs_snapshot': needs_snapshot, 'requires_publish': requires_publish,
        'summary': summary, 'row_operations': operations, 'estimated_writes': estimate,
        'snapshot_commit': None if needs_snapshot else target_commit,
        'limits': vars(limits),
        'database': control['database'],
        'should_deploy_worker': control['event_name'] == 'push' or needs_snapshot,
    }
    if requires_publish:
        try:
            sync.build_transaction(current, revision, patch, target, limits)
        except sync.SyncError as error:
            # Keep the reviewed delta visible even when safeguards reject it.
            plan.update(status='blocked', validation_error=str(error))
            save_json(workspace / 'plan.json', plan)
            raise
    save_json(workspace / 'plan.json', plan)
    stats_source = workspace / ('candidate-archive' if needs_snapshot else 'baseline-archive') / 'contest_stats.json'
    shutil.copyfile(stats_source, stats_output or snapshots.ROOT / 'cloudflare/worker/api/contest_stats.json')
    for key in ('requires_publish', 'needs_snapshot', 'should_deploy_worker'):
        output(key, plan[key])
    print(json.dumps({'summary': summary, 'row_operations': operations, 'estimated_writes': estimate,
                      'requires_publish': requires_publish, 'needs_snapshot': needs_snapshot}, ensure_ascii=False))
    return plan


def load_plan(workspace):
    plan = json.loads((Path(workspace) / 'plan.json').read_text())
    if plan.get('format_version') != 1:
        raise sync.SyncError('Unsupported publication plan')
    if plan.get('status') == 'blocked':
        raise sync.SyncError('Blocked publication plan; rerun preparation after reviewing its validation error')
    return plan


def archive_run(repo, workspace, branch='data-state'):
    workspace = Path(workspace)
    plan = load_plan(workspace)
    if plan['needs_snapshot']:
        manifest, _ = snapshots.open_archive(workspace / 'candidate-archive', workspace / 'candidate-verified.db')
        expected = plan['target']
        if manifest['upstream_sha'] != expected['upstream_sha'] or manifest['worker_version'] != expected['worker_version']:
            raise sync.SyncError('Candidate source/build identity changed after planning')
        for manifest_key, target_key in (
            ('archive_sha256', 'snapshot_sha256'), ('logical_data_hash', 'logical_data_hash'),
            ('source_data_hash', 'source_data_hash'), ('projection_version', 'projection_version'), ('data_hash', 'data_hash'),
        ):
            if manifest[manifest_key] != expected[target_key]:
                raise sync.SyncError('Candidate archive changed after planning')
        commit = snapshots.store_archive(repo, workspace / 'candidate-archive', branch)
        plan['target']['snapshot_commit'] = commit
        plan['snapshot_commit'] = commit
        save_json(workspace / 'plan.json', plan)
    if not snapshots.SHA.fullmatch(plan.get('snapshot_commit') or ''):
        raise sync.SyncError('No archived candidate commit; D1 publication is forbidden')
    output('snapshot_commit', plan['snapshot_commit'])
    print(f"Validated snapshot commit: {plan['snapshot_commit']}")
    return plan['snapshot_commit']


def publish_run(client, repo, workspace):
    workspace = Path(workspace)
    plan = load_plan(workspace)
    if not plan['requires_publish']:
        return {'status': 'unchanged'}
    control = json.loads((workspace / 'inspection.json').read_text())
    if client.identity() != plan['database'] or plan['database'] != control['database']:
        raise sync.SyncError('D1 target changed after planning')
    commit = plan.get('snapshot_commit')
    if not snapshots.SHA.fullmatch(commit or '') or commit != plan['target']['snapshot_commit']:
        raise sync.SyncError('Candidate must be archived before publication')
    # Re-fetch the immutable candidate and baseline: local artifacts and branch HEAD
    # are not authorities for what was actually stored or previously published.
    snapshots.fetch_archive(repo, plan['base']['snapshot_commit'], workspace / 'publish-base')
    manifest_old, old = snapshots.open_archive(workspace / 'publish-base', workspace / 'publish-base.db')
    sync.assert_manifest_matches(plan['base'], manifest_old)
    snapshots.fetch_archive(repo, commit, workspace / 'publish-target')
    manifest_new, new = snapshots.open_archive(workspace / 'publish-target', workspace / 'publish-target.db')
    sync.assert_manifest_matches(plan['target'], manifest_new)
    if manifest_new['data_hash'] != plan['target']['data_hash']:
        raise sync.SyncError('Candidate build identity changed')
    patch, summary = sync.diff_states(old, new)
    if summary != plan['summary'] or sync.estimate_writes(patch)[0] != plan['row_operations']:
        raise sync.SyncError('Archived delta differs from the reviewed plan')
    expected_target = sync.publication_values(manifest_new, commit,
        source_sha=control['upstream_sha'], source_hash=manifest_new['source_data_hash'],
        worker_version=manifest_new['worker_version'] if plan['needs_snapshot'] else plan['base']['worker_version'],
        run_url=plan['target']['github_run_url'], revision=plan['base_revision'] + plan['row_operations'])
    if expected_target != plan['target']:
        raise sync.SyncError('Publication identity differs from inspected source and archived data')
    limits = sync.Limits.from_env()
    if vars(limits) != plan['limits']:
        raise sync.SyncError('Publishing limits changed after planning')
    result = sync.publish(client, plan['base'], plan['base_revision'], patch, plan['target'], limits)
    save_json(workspace / 'publish-result.json', result)
    print(json.dumps(result, ensure_ascii=False))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('inspect', 'prepare', 'archive', 'publish'))
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--repo', default=str(snapshots.ROOT))
    parser.add_argument('--branch', default='data-state')
    parser.add_argument('--upstream-sha')
    parser.add_argument('--event-name', default='schedule')
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--database')
    parser.add_argument('--stats')
    parser.add_argument('--source-data-hash')
    parser.add_argument('--worker-version')
    parser.add_argument('--run-url')
    args = parser.parse_args()
    workspace = Path(args.workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    if args.mode == 'archive':
        archive_run(args.repo, workspace, args.branch)
        return
    cfg = load_config()
    validate_target_config(cfg)
    client = sync.D1Client(cfg)
    if args.mode == 'inspect':
        inspect_run(client, workspace, args.upstream_sha or '', args.event_name, args.force)
    elif args.mode == 'prepare':
        prepare_run(client, args.repo, workspace, database=args.database, stats=args.stats,
                    source_hash=args.source_data_hash, worker_version=args.worker_version,
                    run_url=args.run_url, branch=args.branch)
    else:
        publish_run(client, args.repo, workspace)


if __name__ == '__main__':
    main()

"""Validated, immutable core-data snapshots. No Cloudflare credentials are used here."""

import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile

if __package__:
    from .upload_to_d1 import CORE_SCHEMA, TABLES
else:
    from upload_to_d1 import CORE_SCHEMA, TABLES


ROOT = Path(__file__).resolve().parents[2]
FORMAT_VERSION = 1
MAX_DATABASE_BYTES = 512 * 1024 * 1024
MAX_ARCHIVE_BYTES = 90 * 1024 * 1024
SNAPSHOT_FILES = ('oier_data.db.gz', 'contest_stats.json', 'manifest.json')
SHA = re.compile(r'^[0-9a-f]{40}$')
HASH = re.compile(r'^[0-9a-f]{64}$')
KEYS = {'OIer': ('uid',), 'Contest': ('id',), 'School': ('id',), 'Record': ('oier_uid', 'contest_id')}
FLOAT_COLUMNS = {'oierdb_score', 'ccf_score', 'score'}
TEXT_COLUMNS = {'name', 'initials', 'province', 'city', 'type', 'level'}


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def projection_version():
    """Changes in import rules/dependencies force inspection even at the same SHA."""
    digest = hashlib.sha256(b'oierfinder-projection-v1\0')
    for name in ('create_db.py', 'cloudflare/script/upstream_data.py',
                 'cloudflare/script/data_fingerprint.py', 'pyproject.toml', 'uv.lock'):
        digest.update(name.encode() + b'\0' + (ROOT / name).read_bytes() + b'\0')
    return digest.hexdigest()


def normalize(column, value):
    if value is None:
        return None
    if column in TEXT_COLUMNS:
        if not isinstance(value, str):
            raise ValueError(f'Invalid text column: {column}')
        return value
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'Invalid numeric column: {column}')
    if column in FLOAT_COLUMNS:
        return 0.0 if value == 0 else float(value)
    if int(value) != value or abs(value) > 9007199254740991:
        raise ValueError(f'Invalid integer column: {column}')
    return int(value)


def read_state(path):
    path = Path(path).resolve()
    if not path.is_file() or path.stat().st_size > MAX_DATABASE_BYTES:
        raise ValueError('Missing or oversized snapshot database')
    state = {}
    with sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True) as db:
        db.execute('PRAGMA query_only=ON')
        db.execute('PRAGMA trusted_schema=OFF')
        if db.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
            raise ValueError('Snapshot SQLite integrity check failed')
        for table, columns in TABLES:
            if db.execute("SELECT type FROM sqlite_master WHERE name=?", (table,)).fetchone() != ('table',):
                raise ValueError(f'Missing snapshot table: {table}')
            rows = {}
            for values in db.execute(f'SELECT {", ".join(columns)} FROM {table}'):
                row = {col: normalize(col, value) for col, value in zip(columns, values)}
                key = tuple(row[col] for col in KEYS[table])
                if None in key or key in rows:
                    raise ValueError(f'Missing or duplicate business key in {table}')
                if table == 'Record':
                    row.pop('id')
                rows[key] = row
            if not rows:
                raise ValueError(f'Empty snapshot table: {table}')
            state[table] = rows
    validate_references(state)
    return state


def validate_references(state):
    for row in state['Record'].values():
        for column, table in (('oier_uid', 'OIer'), ('contest_id', 'Contest'), ('school_id', 'School')):
            if (row[column],) not in state[table]:
                raise ValueError(f'Broken snapshot reference: Record.{column}')


def state_hash(state):
    digest = hashlib.sha256(b'oierfinder-logical-data-v1\0')
    for table, _ in TABLES:
        for key, row in sorted(state[table].items()):
            digest.update(json.dumps([table, key, row], ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':'), allow_nan=False).encode('utf-8'))
            digest.update(b'\n')
    return digest.hexdigest()


def row_counts(state):
    return {table: len(rows) for table, rows in state.items()}


def statistics(state):
    years = [row['year'] for row in state['Contest'].values() if row['year'] is not None]
    if not years:
        raise ValueError('No contest years for snapshot statistics')
    groups = {}
    for row in state['Record'].values():
        if row['province'] is None or row['province'] == '' or row['level'] is None:
            continue
        contest = state['Contest'][(row['contest_id'],)]
        key = (str(contest['year']), contest['type'], row['province'], row['level'])
        groups.setdefault(key, set()).add(row['oier_uid'])
    if not groups:
        raise ValueError('No record groups for snapshot statistics')
    data = {}
    for (year, kind, province, level), uids in groups.items():
        data.setdefault(year, {}).setdefault(kind, {}).setdefault(province, {})[level] = len(uids)
    return {'min_year': min(years), 'max_year': max(years), 'stats': data}


def write_core_database(path, rows_by_table):
    """Used for one-time read-only bootstrap; includes no release/secrets tables."""
    path = Path(path)
    if path.exists():
        raise ValueError('Refusing to overwrite a bootstrap database')
    with sqlite3.connect(path) as db:
        db.execute('PRAGMA foreign_keys=ON')
        for table, _ in TABLES:
            db.execute(CORE_SCHEMA[table])
        for table in ('OIer', 'Contest', 'School', 'Record'):
            columns = dict(TABLES)[table]
            for row in rows_by_table[table]:
                db.execute(f'INSERT INTO {table} ({", ".join(columns)}) VALUES ({", ".join("?" for _ in columns)})',
                           [row[col] for col in columns])
    return read_state(path)


def create_archive(database, stats, directory, *, source_sha, source_hash, projection, worker_version):
    if not SHA.fullmatch(source_sha) or not HASH.fullmatch(source_hash):
        raise ValueError('Invalid snapshot source identity')
    if not projection or (worker_version and not SHA.fullmatch(worker_version)):
        raise ValueError('Invalid snapshot build identity')
    state = read_state(database)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    archive = directory / 'oier_data.db.gz'
    # Archive a canonical core-only database, never extra tables in an input file.
    # Sorting by business key also avoids score-order churn in stored snapshots.
    with tempfile.TemporaryDirectory(dir=directory) as tmp:
        canonical = Path(tmp) / 'core.db'
        rows = {
            table: [dict(row, id=n) if table == 'Record' else row
                    for n, (_, row) in enumerate(sorted(data.items()), 1)]
            for table, data in state.items()
        }
        write_core_database(canonical, rows)
        database_sha256 = file_hash(canonical)
        database_bytes = canonical.stat().st_size
        with canonical.open('rb') as source, archive.open('wb') as raw:
            with gzip.GzipFile(filename='', fileobj=raw, mode='wb', compresslevel=6, mtime=0) as target:
                for block in iter(lambda: source.read(1024 * 1024), b''):
                    target.write(block)
    if archive.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError('Snapshot exceeds the repository archive size budget')
    stats_data = json.loads(Path(stats).read_text(encoding='utf-8'))
    if stats_data != statistics(state):
        raise ValueError('Statistics do not describe the snapshot database')
    stats_path = directory / 'contest_stats.json'
    stats_path.write_text(json.dumps(stats_data, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':'), allow_nan=False) + '\n', encoding='utf-8')
    manifest = {
        'format_version': FORMAT_VERSION,
        'upstream_sha': source_sha,
        'source_data_hash': source_hash,
        'projection_version': projection,
        'worker_version': worker_version,
        'logical_data_hash': state_hash(state),
        'row_counts': row_counts(state),
        'database_sha256': database_sha256,
        'archive_sha256': file_hash(archive),
        'database_bytes': database_bytes,
        'archive_bytes': archive.stat().st_size,
        'stats_sha256': file_hash(stats_path),
    }
    manifest['data_hash'] = hashlib.sha256(
        (manifest['logical_data_hash'] + ':' + manifest['stats_sha256']).encode()
    ).hexdigest()
    (directory / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    return manifest


def open_archive(directory, database_path):
    directory, database_path = Path(directory), Path(database_path)
    manifest_path = directory / 'manifest.json'
    if manifest_path.stat().st_size > 1024 * 1024:
        raise ValueError('Oversized snapshot manifest')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('format_version') != FORMAT_VERSION:
        raise ValueError('Unsupported snapshot format; explicit migration required')
    for name in ('source_data_hash', 'database_sha256', 'archive_sha256', 'stats_sha256', 'logical_data_hash', 'data_hash'):
        if not isinstance(manifest.get(name), str) or not HASH.fullmatch(manifest[name]):
            raise ValueError(f'Invalid snapshot hash: {name}')
    if not SHA.fullmatch(manifest.get('upstream_sha', '')) or not manifest.get('projection_version'):
        raise ValueError('Invalid snapshot identity')
    archive = directory / 'oier_data.db.gz'
    if archive.stat().st_size > MAX_ARCHIVE_BYTES or file_hash(archive) != manifest['archive_sha256']:
        raise ValueError('Snapshot archive checksum mismatch')
    if file_hash(directory / 'contest_stats.json') != manifest['stats_sha256']:
        raise ValueError('Snapshot statistics checksum mismatch')
    expected_data_hash = hashlib.sha256((manifest['logical_data_hash'] + ':' + manifest['stats_sha256']).encode()).hexdigest()
    if manifest['data_hash'] != expected_data_hash:
        raise ValueError('Snapshot build checksum mismatch')
    written = 0
    fd, temp = tempfile.mkstemp(prefix='.snapshot-', dir=database_path.parent)
    try:
        with os.fdopen(fd, 'wb') as target, gzip.open(archive, 'rb') as source:
            for block in iter(lambda: source.read(1024 * 1024), b''):
                written += len(block)
                if written > MAX_DATABASE_BYTES:
                    raise ValueError('Decompressed snapshot exceeds size budget')
                target.write(block)
        if written != manifest.get('database_bytes') or file_hash(temp) != manifest['database_sha256']:
            raise ValueError('Snapshot database checksum mismatch')
        state = read_state(temp)
        if state_hash(state) != manifest['logical_data_hash'] or row_counts(state) != manifest['row_counts']:
            raise ValueError('Snapshot business-data checksum mismatch')
        if json.loads((directory / 'contest_stats.json').read_text(encoding='utf-8')) != statistics(state):
            raise ValueError('Archived statistics do not describe the database')
        os.replace(temp, database_path)
    finally:
        Path(temp).unlink(missing_ok=True)
    return manifest, state


def git(repo, *args, data=None):
    result = subprocess.run(['git', '-C', str(repo), *args], input=data,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode:
        # Do not print remote credential headers, archive contents, or personal data.
        raise RuntimeError(f'Git snapshot operation failed: {args[0]} (exit {result.returncode})')
    return result.stdout


def fetch_archive(repo, commit, directory):
    if not SHA.fullmatch(commit):
        raise ValueError('A full immutable snapshot commit is required')
    git(repo, 'fetch', '--no-tags', '--depth=1', 'origin', commit)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name in SNAPSHOT_FILES:
        size = int(git(repo, 'cat-file', '-s', f'{commit}:{name}'))
        limit = MAX_ARCHIVE_BYTES if name.endswith('.gz') else 2 * 1024 * 1024
        if size > limit:
            raise ValueError('Oversized file in snapshot commit')
        (directory / name).write_bytes(git(repo, 'show', f'{commit}:{name}'))


def store_archive(repo, directory, branch='data-state'):
    """Append one immutable commit without switching/altering the code worktree."""
    git(repo, 'check-ref-format', '--branch', branch)
    if branch in ('main', 'master'):
        raise ValueError('Snapshots must use a dedicated data branch')
    directory = Path(directory)
    with tempfile.TemporaryDirectory() as tmp:
        open_archive(directory, Path(tmp) / 'verified.db')
    refs = git(repo, 'ls-remote', '--heads', 'origin', f'refs/heads/{branch}').decode().strip().splitlines()
    if len(refs) > 1:
        raise RuntimeError('Ambiguous snapshot branch')
    parent = refs[0].split()[0] if refs else None
    if parent:
        git(repo, 'fetch', '--no-tags', '--depth=1', 'origin', parent)
        files = set(git(repo, 'ls-tree', '-r', '--name-only', parent).decode().splitlines())
        if files != set(SNAPSHOT_FILES):
            raise RuntimeError('Existing data branch is not a dedicated snapshot archive')
        try:
            previous = git(repo, 'show', f'{parent}:manifest.json')
            previous_manifest = json.loads(previous)
            if previous_manifest.get('format_version') != FORMAT_VERSION:
                raise ValueError('Unsupported archive format')
        except (RuntimeError, ValueError):
            raise RuntimeError('Existing snapshot branch has no valid manifest') from None
        if previous == (directory / 'manifest.json').read_bytes():
            for name in SNAPSHOT_FILES:
                local_blob = git(repo, 'hash-object', '--stdin', data=(directory / name).read_bytes()).decode().strip()
                remote_blob = git(repo, 'rev-parse', f'{parent}:{name}').decode().strip()
                if local_blob != remote_blob:
                    raise RuntimeError('Existing candidate archive does not match its manifest')
            return parent
    entries = []
    for name in SNAPSHOT_FILES:
        blob = git(repo, 'hash-object', '-w', '--stdin', data=(directory / name).read_bytes()).decode().strip()
        entries.append(f'100644 blob {blob}\t{name}\n')
    tree = git(repo, 'mktree', data=''.join(entries).encode()).decode().strip()
    args = ['-c', 'user.name=github-actions[bot]', '-c', 'user.email=41898282+github-actions[bot]@users.noreply.github.com', 'commit-tree', tree]
    if parent:
        args += ['-p', parent]
    commit = git(repo, *args, data=b'Archive validated OIer core-data snapshot\n').decode().strip()
    # An ordinary fast-forward push rejects competing updates. Never force-push.
    git(repo, 'push', 'origin', f'{commit}:refs/heads/{branch}')
    return commit

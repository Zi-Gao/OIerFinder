"""Build a core-only, indexed SQLite download. Never connects to Cloudflare D1."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile

if __package__:
    from . import sync_snapshot as snapshots
else:
    import sync_snapshot as snapshots


PART_BYTES = 8_000_000
QUERY_INDEXES = {
    'idx_oier_gender_enroll': ('OIer', 'gender,enroll_middle,uid'),
    'idx_oier_initials_uid': ('OIer', 'initials,uid'),
    'idx_contest_year_type': ('Contest', 'year,type,id'),
    'idx_record_oier_contest': ('Record', 'oier_uid,contest_id'),
    'idx_record_contest_level_uid': ('Record', 'contest_id,level,oier_uid'),
    'idx_record_school_province_level_uid': ('Record', 'school_id,province,level,oier_uid'),
}


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(',', ':'), allow_nan=False) + '\n').encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def build(database, output, *, upstream_sha, worker_version, source_hash=None, part_bytes=PART_BYTES):
    if not snapshots.SHA.fullmatch(upstream_sha) or not snapshots.SHA.fullmatch(worker_version):
        raise ValueError('Both source and application versions must be full Git SHAs')
    if source_hash is not None and not snapshots.HASH.fullmatch(source_hash):
        raise ValueError('Invalid source fingerprint')
    if not 1 <= part_bytes <= PART_BYTES:
        raise ValueError('Invalid static asset part size')
    state = snapshots.read_state(database)
    stats_bytes = encoded(snapshots.statistics(state))
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output) as directory:
        temporary = Path(directory)
        canonical = temporary / 'query.sqlite'
        rows = {
            table: [dict(row, id=n) if table == 'Record' else row
                    for n, (_, row) in enumerate(sorted(data.items()), 1)]
            for table, data in state.items()
        }
        snapshots.write_core_database(canonical, rows)
        with sqlite3.connect(canonical) as db:
            for name, (table, columns) in QUERY_INDEXES.items():
                db.execute(f'CREATE INDEX {name} ON {table}({columns})')
            db.execute('ANALYZE')
            if db.execute('PRAGMA foreign_key_check').fetchall():
                raise ValueError('Snapshot has invalid foreign keys')
            db.commit()
            db.execute('VACUUM')
        if canonical.stat().st_size > 128 * 1024 * 1024:
            raise ValueError('Snapshot exceeds the browser database size budget')
        database_bytes = canonical.read_bytes()
        compressed = gzip.compress(database_bytes, compresslevel=6, mtime=0)
        identity = {
            'format_version': 1,
            'schema_version': 1,
            'upstream_sha': upstream_sha,
            'source_data_hash': source_hash or snapshots.state_hash(state),
            'projection_version': snapshots.projection_version(),
            'logical_data_hash': snapshots.state_hash(state),
            'database_sha256': digest(database_bytes),
            'stats_sha256': digest(stats_bytes),
        }
        snapshot_id = digest(encoded(identity))
        destination = output / snapshot_id
        destination.mkdir(exist_ok=True)
        parts = []
        for index, start in enumerate(range(0, len(compressed), part_bytes)):
            body = compressed[start:start + part_bytes]
            name = f'database-{index:03d}.bin'
            (destination / name).write_bytes(body)
            parts.append({'path': f'/data/{snapshot_id}/{name}', 'bytes': len(body), 'sha256': digest(body)})
        (destination / 'stats.json').write_bytes(stats_bytes)
        manifest = {
            **identity,
            'snapshot_id': snapshot_id,
            'worker_version': worker_version,
            'row_counts': snapshots.row_counts(state),
            'database': {
                'compression': 'gzip', 'bytes': len(database_bytes),
                'sha256': digest(database_bytes), 'compressed_bytes': len(compressed),
                'compressed_sha256': digest(compressed), 'parts': parts,
            },
            'stats': {'path': f'/data/{snapshot_id}/stats.json',
                      'bytes': len(stats_bytes), 'sha256': digest(stats_bytes)},
        }
        # Publish the small pointer last; every path it names already exists.
        pointer = temporary / 'manifest.json'
        pointer.write_bytes(encoded(manifest))
        shutil.move(str(pointer), output / 'manifest.json')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    parser.add_argument('--output', default=str(snapshots.ROOT / 'cloudflare/worker/public/data'))
    parser.add_argument('--upstream-sha', required=True)
    parser.add_argument('--worker-version', required=True)
    parser.add_argument('--source-data-hash')
    args = parser.parse_args()
    manifest = build(args.database, args.output, upstream_sha=args.upstream_sha,
                     worker_version=args.worker_version, source_hash=args.source_data_hash)
    print(json.dumps({key: manifest[key] for key in ('snapshot_id', 'upstream_sha', 'row_counts')}))


if __name__ == '__main__':
    main()

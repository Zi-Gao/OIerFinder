import { execFileSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export async function createSnapshotFixture() {
    const root = await mkdtemp(path.join(os.tmpdir(), 'oier-static-test-'));
    const repo = fileURLToPath(new URL('../../../', import.meta.url));
    const python = existsSync(path.join(repo, '.venv/bin/python')) ? path.join(repo, '.venv/bin/python') : 'python3';
    execFileSync(python, ['-c', `
from pathlib import Path
import sys
from cloudflare.script import sync_snapshot as snapshots
from cloudflare.script.build_static_snapshot import build
from cloudflare.script.test_incremental_d1 import OLD_ROWS
root=Path(sys.argv[1])
snapshots.write_core_database(root/'input.db', OLD_ROWS)
build(root/'input.db',root/'data',upstream_sha='1'*40,worker_version='2'*40,part_bytes=1024)
`, root], { cwd: repo });
    const manifestPath = path.join(root, 'data/manifest.json');
    const manifest = JSON.parse(await readFile(manifestPath, 'utf8'));
    return {
        root, manifestPath, manifest,
        readAsset: async file => new Uint8Array(await readFile(path.join(root, file.path.slice(1)))),
        async rebuild() {
            execFileSync(python, ['-c', `
from pathlib import Path
import sqlite3
import sys
from cloudflare.script.build_static_snapshot import build
root=Path(sys.argv[1])
with sqlite3.connect(root/'input.db') as db:
    db.execute("UPDATE OIer SET name='Updated Alice' WHERE uid=1")
build(root/'input.db',root/'data',upstream_sha='3'*40,worker_version='2'*40,part_bytes=1024)
`, root], { cwd: repo });
            return JSON.parse(await readFile(manifestPath, 'utf8'));
        },
        close: () => rm(root, { recursive: true, force: true }),
    };
}

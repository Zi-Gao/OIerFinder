import { parentPort, workerData } from 'node:worker_threads';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import initSqlJs from 'sql.js';
import { loadSnapshot, validateManifest, readResponseBytes, verifyDatabase } from '../shared/snapshot.js';
import { querySnapshot } from '../shared/query-engine.js';
import { sqliteAdapter } from '../shared/sqlite-adapter.js';

const location = workerData.manifestLocation;
const remote = /^https?:\/\//.test(location);
const SQL = await initSqlJs();
let active;
let checkedAt = 0;
let sequence = Promise.resolve();

async function readResource(file, maximum) {
    if (remote) {
        const url = file ? new URL(file.path, location) : location;
        return readResponseBytes(await fetch(url, { signal: AbortSignal.timeout(30_000), cache: 'no-cache' }), maximum);
    }
    const filename = file ? path.join(path.dirname(location), file.path.slice('/data/'.length)) : location;
    const data = await readFile(filename);
    if (data.length > maximum) throw new Error('Snapshot file exceeds its size budget');
    return new Uint8Array(data);
}

async function snapshot(expected) {
    if (active && (!expected || expected === active.manifest.snapshot_id) && Date.now() - checkedAt < 60_000) return active;
    const manifest = validateManifest(JSON.parse(new TextDecoder().decode(await readResource(null, 64 * 1024))));
    if (expected && expected !== manifest.snapshot_id) throw new Error('The query service is waiting for the requested data version. Please retry shortly.');
    if (active?.manifest.snapshot_id !== manifest.snapshot_id) {
        const loaded = await loadSnapshot(manifest, { readAsset: file => readResource(file, file.bytes) });
        const db = new SQL.Database(loaded.bytes);
        try { verifyDatabase(db, manifest); } catch (error) { db.close(); throw error; }
        active?.db.close();
        active = { db, stats: loaded.stats, manifest };
    }
    checkedAt = Date.now();
    return active;
}

try {
    const { manifest } = await snapshot();
    parentPort.postMessage({ type: 'ready', manifest });
} catch (error) {
    parentPort.postMessage({ type: 'startup-error', error: error.message });
}

parentPort.on('message', task => {
    sequence = sequence.then(async () => {
        try {
            const current = await snapshot(task.expectedSnapshot);
            const result = await querySnapshot(sqliteAdapter(current.db), current.stats, task.payload, { isAdmin: task.isAdmin });
            parentPort.postMessage({ id: task.id, ...result, manifest: current.manifest });
        } catch (error) {
            console.error('Snapshot query preparation failed:', error.message);
            parentPort.postMessage({ id: task.id, status: 503, body: { error: 'The query service could not prepare the requested data version. Please retry shortly.' } });
        }
    });
});

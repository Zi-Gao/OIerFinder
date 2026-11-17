import initSqlJs from 'sql.js';
import wasmUrl from 'sql.js/dist/sql-wasm-browser.wasm?url';
import { loadSnapshot, resolveSnapshotManifest, readResponseBytes, verifyDatabase } from '../../shared/snapshot.js';
import { querySnapshot } from '../../shared/query-engine.js';
import { sqliteAdapter } from '../../shared/sqlite-adapter.js';

let active;
let sqlPromise;
let sequence = Promise.resolve();
const manifestUrl = new URL('/data/manifest.json', self.location.origin).href;

async function openSnapshot(progress) {
    let cache;
    try { cache = await caches.open('oier-snapshots-v1'); } catch { /* Private browsing can disable storage. */ }
    const { manifest, offline } = await resolveSnapshotManifest({
        fetchResponse: () => fetch(manifestUrl, { cache: 'no-cache' }),
        readSavedResponse: async () => cache?.match(manifestUrl),
        activeManifest: active?.manifest,
    });
    if (active?.manifest.snapshot_id === manifest.snapshot_id) return { ...active, offline };
    const loaded = await loadSnapshot(manifest, {
        onProgress: progress,
        readAsset: async (file, update) => readResponseBytes(await fetch(file.path), file.bytes, update),
        readCache: async file => {
            const response = await cache?.match(file.path);
            return response ? readResponseBytes(response, file.bytes) : null;
        },
        writeCache: async (file, bytes) => cache?.put(file.path, new Response(bytes)),
    });
    sqlPromise ??= initSqlJs({ locateFile: () => wasmUrl }).catch(error => {
        sqlPromise = undefined;
        throw error;
    });
    const SQL = await sqlPromise;
    const db = new SQL.Database(loaded.bytes);
    try { verifyDatabase(db, manifest); } catch (error) { db.close(); throw error; }
    try {
        await cache?.put(manifestUrl, new Response(JSON.stringify(manifest), { headers: { 'Content-Type': 'application/json' } }));
        const keys = await cache?.keys();
        for (const key of keys ?? []) {
            const pathname = new URL(key.url).pathname;
            if (/^\/data\/[a-f0-9]{64}\//.test(pathname) && !pathname.startsWith(`/data/${manifest.snapshot_id}/`)) {
                await cache.delete(key);
            }
        }
    } catch { /* Cached data is optional. */ }
    active?.db.close();
    active = { db, stats: loaded.stats, manifest, offline };
    return active;
}

self.onmessage = ({ data: { id, payload } }) => {
    sequence = sequence.then(async () => {
        const progress = value => self.postMessage({ id, type: 'progress', ...value });
        try {
            progress({ phase: 'checking' });
            const snapshot = await openSnapshot(progress);
            progress({ phase: 'querying', manifest: snapshot.manifest, offline: snapshot.offline });
            const result = await querySnapshot(sqliteAdapter(snapshot.db), snapshot.stats, payload, {
                // Local computation does not consume a public query service's resources.
                isAdmin: true, includeUsage: false,
            });
            self.postMessage({ id, type: 'result', ...result, snapshot_id: snapshot.manifest.snapshot_id, offline: snapshot.offline });
        } catch (error) {
            self.postMessage({ id, type: 'error', error: error.message || 'Could not prepare the search data. Please retry.' });
        }
    });
};

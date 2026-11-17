const HASH = /^[a-f0-9]{64}$/;
const SHA = /^[a-f0-9]{40}$/;
const MAX_DATABASE_BYTES = 128 * 1024 * 1024;

export function validateManifest(manifest) {
    if (!manifest || manifest.format_version !== 1 || manifest.schema_version !== 1 ||
        !HASH.test(manifest.snapshot_id) || !SHA.test(manifest.upstream_sha) ||
        !SHA.test(manifest.worker_version)) {
        throw new Error('This data version is not supported. Reload the page to update.');
    }
    const db = manifest.database;
    if (!db || !Array.isArray(db.parts)) throw new Error('The data download manifest is invalid.');
    const files = [...(db?.parts ?? []), manifest.stats];
    if (!db || db.compression !== 'gzip' || !HASH.test(db.sha256) ||
        !HASH.test(db.compressed_sha256) || !Number.isSafeInteger(db.bytes) ||
        db.bytes < 1 || db.bytes > MAX_DATABASE_BYTES ||
        !Number.isSafeInteger(db.compressed_bytes) || db.compressed_bytes < 1 ||
        db.compressed_bytes > MAX_DATABASE_BYTES || !db.parts.length || db.parts.length > 32) {
        throw new Error('The data download manifest is invalid. Please try again later.');
    }
    for (const [index, file] of files.entries()) {
        const name = index < db.parts.length ? `database-${String(index).padStart(3, '0')}.bin` : 'stats.json';
        const maximum = index < db.parts.length ? 8_000_000 : 2_000_000;
        if (!file || file.path !== `/data/${manifest.snapshot_id}/${name}` ||
            !HASH.test(file.sha256) || !Number.isSafeInteger(file.bytes) ||
            file.bytes < 1 || file.bytes > maximum) {
            throw new Error('The data download manifest contains an invalid file.');
        }
    }
    if (db.parts.reduce((sum, part) => sum + part.bytes, 0) !== db.compressed_bytes ||
        !['OIer', 'Contest', 'School', 'Record'].every(table =>
            Number.isSafeInteger(manifest.row_counts?.[table]) && manifest.row_counts[table] > 0)) {
        throw new Error('The data download manifest has inconsistent counts.');
    }
    return manifest;
}

export async function hashBytes(bytes) {
    const hash = await crypto.subtle.digest('SHA-256', bytes);
    return Array.from(new Uint8Array(hash), value => value.toString(16).padStart(2, '0')).join('');
}

export async function readResponseBytes(response, maximum, onProgress = () => {}) {
    if (!response.ok) throw new Error(`Data download failed (${response.status}). Please retry.`);
    if (!response.body) throw new Error('The data download is empty. Please retry.');
    const reader = response.body.getReader();
    const chunks = [];
    let length = 0;
    try {
        for (;;) {
            const { done, value } = await reader.read();
            if (done) break;
            length += value.byteLength;
            if (length > maximum) throw new Error('The data download is larger than expected.');
            chunks.push(value);
            onProgress(length);
        }
    } catch (error) {
        await reader.cancel().catch(() => {});
        throw error;
    } finally {
        reader.releaseLock();
    }
    const result = new Uint8Array(length);
    let offset = 0;
    for (const chunk of chunks) {
        result.set(chunk, offset);
        offset += chunk.byteLength;
    }
    return result;
}

export async function parseManifest(response) {
    const bytes = await readResponseBytes(response, 64 * 1024);
    return validateManifest(JSON.parse(new TextDecoder().decode(bytes)));
}

/** Only transport failures may use a saved version; invalid current manifests must surface. */
export async function resolveSnapshotManifest({ fetchResponse, readSavedResponse, activeManifest }) {
    let response;
    try {
        response = await fetchResponse();
        if (!response.ok) throw new Error('Could not check the latest data version. Please retry.');
    } catch (error) {
        if (activeManifest) return { manifest: activeManifest, offline: true };
        let saved;
        try { saved = await readSavedResponse(); } catch { /* Storage can be unavailable. */ }
        if (!saved) throw error;
        return { manifest: await parseManifest(saved), offline: true };
    }
    return { manifest: await parseManifest(response), offline: false };
}

/** Load only content-addressed, verified bytes; persistent caching is optional. */
export async function loadSnapshot(manifest, {
    readAsset, readCache = async () => null, writeCache = async () => {}, onProgress = () => {},
}) {
    validateManifest(manifest);
    let downloaded = 0;
    const total = manifest.database.compressed_bytes + manifest.stats.bytes;
    async function fileBytes(file) {
        let bytes;
        try { bytes = await readCache(file); } catch { /* Storage may be disabled. */ }
        if (bytes && (bytes.byteLength !== file.bytes || await hashBytes(bytes) !== file.sha256)) bytes = null;
        if (!bytes) {
            bytes = await readAsset(file, loaded => onProgress({ phase: 'downloading', loaded: downloaded + loaded, total }));
            if (bytes.byteLength !== file.bytes || await hashBytes(bytes) !== file.sha256) {
                throw new Error('The data download is incomplete or damaged. Please retry.');
            }
            try { await writeCache(file, bytes); } catch { /* Continue without a disk cache. */ }
        }
        downloaded += bytes.byteLength;
        onProgress({ phase: 'downloading', loaded: downloaded, total });
        return bytes;
    }
    const statsBytes = await fileBytes(manifest.stats);
    const stats = JSON.parse(new TextDecoder().decode(statsBytes));
    if (!Number.isInteger(stats.min_year) || !Number.isInteger(stats.max_year) ||
        stats.min_year > stats.max_year || !stats.stats || typeof stats.stats !== 'object') {
        throw new Error('The data statistics are invalid.');
    }
    const compressed = new Uint8Array(manifest.database.compressed_bytes);
    let offset = 0;
    for (const file of manifest.database.parts) {
        const bytes = await fileBytes(file);
        compressed.set(bytes, offset);
        offset += bytes.length;
    }
    if (await hashBytes(compressed) !== manifest.database.compressed_sha256) {
        throw new Error('The data download checksum does not match. Please retry.');
    }
    onProgress({ phase: 'preparing' });
    if (typeof DecompressionStream === 'undefined') {
        throw new Error('This browser cannot open the downloaded data. Use a current browser or the HTTP API.');
    }
    const stream = new Blob([compressed]).stream().pipeThrough(new DecompressionStream('gzip'));
    const bytes = await readResponseBytes(new Response(stream), manifest.database.bytes);
    if (bytes.length !== manifest.database.bytes || await hashBytes(bytes) !== manifest.database.sha256 ||
        new TextDecoder().decode(bytes.subarray(0, 16)) !== 'SQLite format 3\0') {
        throw new Error('The downloaded database failed verification. Please retry.');
    }
    return { bytes, stats, manifest };
}

export function verifyDatabase(database, manifest) {
    database.run('PRAGMA query_only=ON; PRAGMA trusted_schema=OFF');
    if (database.exec('PRAGMA quick_check')[0]?.values[0]?.[0] !== 'ok') {
        throw new Error('The downloaded database failed its integrity check.');
    }
    for (const table of ['OIer', 'Contest', 'School', 'Record']) {
        if (database.exec(`SELECT COUNT(*) FROM ${table}`)[0]?.values[0]?.[0] !== manifest.row_counts[table]) {
            throw new Error('The downloaded database has inconsistent row counts.');
        }
    }
}

import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';
import initSqlJs from 'sql.js';
import { loadSnapshot, resolveSnapshotManifest, validateManifest, verifyDatabase } from './snapshot.js';
import { querySnapshot } from './query-engine.js';
import { sqliteAdapter } from './sqlite-adapter.js';
import { createSnapshotFixture } from './test-fixture.js';

let fixture;
let loaded;
let database;
before(async () => {
    fixture = await createSnapshotFixture();
    loaded = await loadSnapshot(fixture.manifest, { readAsset: fixture.readAsset });
    const SQL = await initSqlJs();
    database = new SQL.Database(loaded.bytes);
    verifyDatabase(database, loaded.manifest);
});
after(async () => { database?.close(); await fixture?.close(); });

test('SQLite WASM queries the exact validated snapshot with existing filter semantics', async () => {
    const payload = { record_filters: [{ contest_id: 1, school_id: 1, year: 2024 }], limit: 10 };
    const result = await querySnapshot(sqliteAdapter(database), loaded.stats, payload);
    assert.equal(result.status, 200);
    assert.deepEqual(result.body.data.map(row => row.uid), [1]);
    assert.throws(() => database.run('DELETE FROM OIer'), /readonly/);
});

test('record predicates match the same student and null scores do not match bounds', async () => {
    const db = sqliteAdapter(database);
    const result = await querySnapshot(db, loaded.stats, { record_filters: [{ contest_id: 1 }, { contest_id: 2 }] });
    assert.equal(result.status, 200);
    assert.deepEqual(result.body.data, []);
    const nullScore = await querySnapshot(db, loaded.stats, { record_filters: [{ contest_id: 2, min_score: 1 }] }, { isAdmin: true });
    assert.deepEqual(nullScore.body.data, []);
    const invalid = await querySnapshot(db, loaded.stats, { record_filters: [{ contest_id: 1, contest_ids: [2] }] });
    assert.equal(invalid.status, 400);
});

test('corrupt cached parts are replaced with verified network bytes', async () => {
    let fetched = 0;
    let stored = 0;
    const result = await loadSnapshot(fixture.manifest, {
        readCache: async file => new Uint8Array(file.bytes),
        readAsset: async file => { fetched++; return fixture.readAsset(file); },
        writeCache: async () => { stored++; },
    });
    assert.deepEqual(result.bytes, loaded.bytes);
    assert.equal(fetched, fixture.manifest.database.parts.length + 1);
    assert.equal(stored, fetched);
});

test('fully cached snapshots need no network and cache failures do not block loading', async () => {
    const cached = await loadSnapshot(fixture.manifest, {
        readCache: fixture.readAsset,
        readAsset: () => { throw new Error('offline'); },
    });
    assert.deepEqual(cached.bytes, loaded.bytes);
    const noStorage = await loadSnapshot(fixture.manifest, {
        readCache: () => { throw new Error('storage denied'); },
        writeCache: () => { throw new Error('storage full'); },
        readAsset: fixture.readAsset,
    });
    assert.deepEqual(noStorage.bytes, loaded.bytes);
});

test('missing, damaged, and foreign version files fail without partial query results', async () => {
    await assert.rejects(loadSnapshot(fixture.manifest, { readAsset: async () => new Uint8Array(0) }), /incomplete|damaged/);
    await assert.rejects(loadSnapshot(fixture.manifest, { readAsset: async () => { throw new Error('not found'); } }), /not found/);
    const invalid = structuredClone(fixture.manifest);
    invalid.database.parts[0].path = '/data/../../private.db';
    assert.throws(() => validateManifest(invalid), /invalid file/);
});

test('a cold page can recover its saved manifest after HTTP or network failure', async () => {
    for (const fetchResponse of [async () => new Response(null, { status: 503 }), async () => { throw new Error('offline'); }]) {
        const result = await resolveSnapshotManifest({
            fetchResponse,
            readSavedResponse: async () => Response.json(fixture.manifest),
        });
        assert.equal(result.offline, true);
        assert.equal(result.manifest.snapshot_id, fixture.manifest.snapshot_id);
    }
    const active = await resolveSnapshotManifest({
        fetchResponse: async () => { throw new Error('offline'); },
        readSavedResponse: () => { throw new Error('Should not read storage for an open database'); },
        activeManifest: fixture.manifest,
    });
    assert.equal(active.manifest, fixture.manifest);
    assert.equal(active.offline, true);
});

test('invalid current manifests are reported instead of silently selecting saved data', async () => {
    await assert.rejects(resolveSnapshotManifest({
        fetchResponse: async () => Response.json({ format_version: 999 }),
        readSavedResponse: async () => Response.json(fixture.manifest),
        activeManifest: fixture.manifest,
    }), /not supported/);
    await assert.rejects(resolveSnapshotManifest({
        fetchResponse: async () => new Response(null, { status: 503 }),
        readSavedResponse: async () => null,
    }), /Could not check/);
});

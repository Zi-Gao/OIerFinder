import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';
import { startQueryServer } from './query-server.js';
import { createSnapshotFixture } from '../shared/test-fixture.js';

let fixture;
let service;
before(async () => {
    fixture = await createSnapshotFixture();
    service = await startQueryServer({ manifestLocation: fixture.manifestPath, port: 0, backendSecret: 'backend-test' });
});
after(async () => { await service?.close(); await fixture?.close(); });
const headers = { 'Content-Type': 'application/json', 'X-Query-Backend-Key': 'backend-test' };

test('standalone API returns the existing response shape from the static snapshot', async () => {
    const response = await fetch(`${service.url}/query-oier`, {
        method: 'POST', headers: { ...headers, 'X-OIer-Snapshot': fixture.manifest.snapshot_id },
        body: JSON.stringify({ record_filters: [{ contest_id: 1, school_id: 1, year: 2024 }] }),
    });
    assert.equal(response.status, 200);
    assert.equal(response.headers.get('X-OIer-Snapshot'), fixture.manifest.snapshot_id);
    assert.deepEqual((await response.json()).data.map(row => row.uid), [1]);
});

test('API reports a version mismatch instead of returning old data', async () => {
    const response = await fetch(`${service.url}/query-oier`, {
        method: 'POST', headers: { ...headers, 'X-OIer-Snapshot': 'f'.repeat(64) },
        body: JSON.stringify({ record_filters: [{ contest_id: 1, school_id: 1 }] }),
    });
    assert.equal(response.status, 503);
});

test('backend authentication, invalid JSON and excessive request bodies are handled', async () => {
    assert.equal((await fetch(`${service.url}/health`)).status, 401);
    assert.equal((await fetch(`${service.url}/health`, { headers })).status, 200);
    assert.equal((await fetch(`${service.url}/query-oier`, { method: 'POST', headers, body: '{' })).status, 400);
    assert.equal((await fetch(`${service.url}/query-oier`, { method: 'POST', headers, body: ' '.repeat(65537) })).status, 413);
});

test('a new snapshot is fully prepared before the API serves its version', async () => {
    const next = await fixture.rebuild();
    const response = await fetch(`${service.url}/query-oier`, {
        method: 'POST', headers: { ...headers, 'X-OIer-Snapshot': next.snapshot_id },
        body: JSON.stringify({ record_filters: [{ contest_id: 1, school_id: 1, year: 2024 }] }),
    });
    assert.equal(response.status, 200);
    assert.equal(response.headers.get('X-OIer-Snapshot'), next.snapshot_id);
    assert.equal((await response.json()).data[0].name, 'Updated Alice');
});

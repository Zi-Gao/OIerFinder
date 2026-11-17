import assert from 'node:assert/strict';
import { after, before, mock, test } from 'node:test';
import app from './index.js';
import { createSnapshotFixture } from '../shared/test-fixture.js';

let fixture;
before(async () => { fixture = await createSnapshotFixture(); });
after(async () => { await fixture?.close(); });
const request = body => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
function env() {
    return {
        ENABLE_QUERY_API: 'true',
        QUERY_API_ORIGIN: 'https://query.example.com',
        ASSETS: { fetch: async () => Response.json(fixture.manifest) },
        DB: { prepare() { throw new Error('Core queries must never access D1'); } },
    };
}

test('explicitly enabled query endpoint forwards to the snapshot API without touching D1', async () => {
    let forwarded;
    mock.method(globalThis, 'fetch', async (url, options) => {
        forwarded = { url, options };
        return Response.json({ data: [{ uid: 1 }] }, { headers: { 'X-OIer-Snapshot': fixture.manifest.snapshot_id } });
    });
    try {
        const response = await app.request('/query-oier', request({ record_filters: [{ contest_id: 1 }] }), env());
        assert.equal(response.status, 200);
        assert.deepEqual(await response.json(), { data: [{ uid: 1 }] });
        assert.equal(String(forwarded.url), 'https://query.example.com/query-oier');
        assert.equal(forwarded.options.headers.get('X-OIer-Snapshot'), fixture.manifest.snapshot_id);
    } finally { mock.restoreAll(); }
});

test('unconfigured and stale backends return 503 instead of using old D1 data', async () => {
    assert.equal((await app.request('/query-oier', request({}), { ENABLE_QUERY_API: 'true' })).status, 503);
    mock.method(globalThis, 'fetch', async () => Response.json({ data: [] }, { headers: { 'X-OIer-Snapshot': 'f'.repeat(64) } }));
    try {
        assert.equal((await app.request('/query-oier', request({}), env())).status, 503);
    } finally { mock.restoreAll(); }
});

test('query API is hidden by default even when a backend origin is retained', async () => {
    const fetchMock = mock.method(globalThis, 'fetch', async () => { throw new Error('Hidden API must not reach the backend'); });
    try {
        const environment = env();
        delete environment.ENABLE_QUERY_API;
        assert.equal((await app.request('/query-oier', request({}), environment)).status, 404);
        assert.equal((await app.request('/query-oier', request({}), { ...environment, ENABLE_QUERY_API: 'false' })).status, 404);
        assert.equal(fetchMock.mock.callCount(), 0);
    } finally { mock.restoreAll(); }
});

test('the public endpoint rejects malformed and oversized requests before forwarding', async () => {
    mock.method(globalThis, 'fetch', async () => { throw new Error('Should not reach backend'); });
    try {
        assert.equal((await app.request('/query-oier', { method: 'POST', body: '{' }, env())).status, 400);
        assert.equal((await app.request('/query-oier', request({ text: 'x'.repeat(65537) }), env())).status, 413);
    } finally { mock.restoreAll(); }
});

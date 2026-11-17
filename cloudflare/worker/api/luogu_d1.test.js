import assert from 'node:assert/strict';
import { mock, test } from 'node:test';
import { getPrizes } from './luogu_to_query.js';

test('Luogu synchronization continues writing new prizes to D1', async () => {
    const writes = [];
    const tasks = [];
    const DB = {
        prepare(sql) {
            return { bind: (...params) => ({ sql, params, all: async () => ({ results: [] }) }) };
        },
        batch: async statements => { writes.push(...statements); },
    };
    const html = '<script id="lentille-context" type="application/json">' + JSON.stringify({ data: { prizes: [{ prize: { contest: 'CSP-S', prize: '一等奖', year: 2026 } }] } }) + '</script>';
    mock.method(globalThis, 'fetch', async () => new Response(html));
    try {
        const result = await getPrizes('123', true, { DB }, { waitUntil: task => tasks.push(task) });
        await Promise.all(tasks);
        assert.equal(result.synced, true);
        assert.equal(writes.length, 1);
        assert.match(writes[0].sql, /^INSERT INTO LuoguPrizes/);
        assert.equal(writes[0].params[0], '123');
    } finally { mock.restoreAll(); }
});

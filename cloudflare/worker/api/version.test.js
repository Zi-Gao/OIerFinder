import assert from 'node:assert/strict';
import test from 'node:test';

import { getVersionInfo } from './version.js';

const OIERFINDER_SHA = '0123456789abcdef0123456789abcdef01234567';
const OIERDB_DATA_SHA = '89abcdef0123456789abcdef0123456789abcdef';

test('getVersionInfo reads the static data SHA without accessing D1', async () => {
    let executedQuery = '';
    const env = {
        OIERFINDER_SHA: OIERFINDER_SHA.toUpperCase(),
        DB: { prepare() { throw new Error('Core version lookup must not use D1'); } },
        ASSETS: { fetch: async request => { executedQuery = request.url; return Response.json({ upstream_sha: OIERDB_DATA_SHA }); } },
    };

    assert.deepEqual(await getVersionInfo(env), {
        oierfinder_sha: OIERFINDER_SHA,
        oierdb_data_sha: OIERDB_DATA_SHA,
    });
    assert.match(executedQuery, /\/data\/manifest.json$/);
});

test('getVersionInfo does not expose invalid or inactive version values', async () => {
    const env = {
        OIERFINDER_SHA: 'development',
        ASSETS: { fetch: async () => Response.json({ upstream_sha: 'invalid' }) },
    };

    assert.deepEqual(await getVersionInfo(env), {
        oierfinder_sha: null,
        oierdb_data_sha: null,
    });
});

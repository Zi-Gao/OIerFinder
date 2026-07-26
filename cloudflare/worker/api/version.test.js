import assert from 'node:assert/strict';
import test from 'node:test';

import { getVersionInfo } from './version.js';

const OIERFINDER_SHA = '0123456789abcdef0123456789abcdef01234567';
const OIERDB_DATA_SHA = '89abcdef0123456789abcdef0123456789abcdef';

test('getVersionInfo returns the deployed application and active data SHAs', async () => {
    let executedQuery = '';
    const env = {
        OIERFINDER_SHA: OIERFINDER_SHA.toUpperCase(),
        DB: {
            prepare(query) {
                executedQuery = query;
                return {
                    first: async () => ({ upstream_sha: OIERDB_DATA_SHA }),
                };
            },
        },
    };

    assert.deepEqual(await getVersionInfo(env), {
        oierfinder_sha: OIERFINDER_SHA,
        oierdb_data_sha: OIERDB_DATA_SHA,
    });
    assert.match(executedQuery, /status = 'active'/);
});

test('getVersionInfo does not expose invalid or inactive version values', async () => {
    const env = {
        OIERFINDER_SHA: 'development',
        DB: {
            prepare() {
                return {
                    first: async () => null,
                };
            },
        },
    };

    assert.deepEqual(await getVersionInfo(env), {
        oierfinder_sha: null,
        oierdb_data_sha: null,
    });
});

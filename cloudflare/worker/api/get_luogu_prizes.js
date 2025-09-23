// cloudflare/worker/functions/get_luogu_prizes.js

import { getPrizes } from './luogu_to_query.js';

export default async function getLuoguPrizesHandler(c) {
    try {
        const uid = c.req.query("uid");
        const sync = c.req.query("sync") === 'true' || c.req.query("sync") === '1';
        const noi_only = c.req.query("noi_only") === 'true' || c.req.query("noi_only") === '1';

        if (!uid) {
            return c.json({ error: "Missing 'uid' query parameter" }, 400);
        }

        let prizeList = await getPrizes(uid, sync, c.env, c.executionCtx);

        if (noi_only) {
            prizeList = prizeList.filter(p => p.is_noi_series);
        }

        prizeList.sort((a, b) => (b.year ?? 0) - (a.year ?? 0) || a.contest_name.localeCompare(b.contest_name));

        return c.json(prizeList);

    } catch (err) {
        console.error('Error in getLuoguPrizesHandler:', err);
        return c.json({ error: `An internal error occurred: ${err.message}` }, 500);
    }
}
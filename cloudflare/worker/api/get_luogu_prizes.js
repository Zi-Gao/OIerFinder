// cloudflare/worker/functions/get_luogu_prizes.js

import { getPrizes } from './luogu_to_query.js';

export default async function getLuoguPrizesHandler(c) {
    const ADMIN_SECRET = c.env.ADMIN_SECRET;
    const clientSecret = c.req.header('X-Admin-Secret');
    const isAdmin = ADMIN_SECRET && clientSecret === ADMIN_SECRET;
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
        console.error('Error in queryOierHandler:', err);

        // 默认返回通用的、不含细节的错误信息
        const errorResponse = { error: 'An internal server error occurred.' };

        // 如果是管理员，则添加详细的调试信息
        if (isAdmin) {
            errorResponse.details = err.message;
            errorResponse.stack = err.stack; // 堆栈信息对调试非常有用
        }

        return c.json(errorResponse, 500);
    }
}
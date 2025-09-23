// oier-finder/api/index.js

import { Hono } from 'hono';
import { serveStatic } from 'hono/cloudflare-workers';
import queryOierHandler from './query_oier.js';
import luoguToQueryHandler from './luogu_to_query.js';
import getLuoguPrizesHandler from './get_luogu_prizes.js';

const app = new Hono();

// --- API 路由 ---
app.post('/query-oier', queryOierHandler);
app.get('/luogu/to_query', luoguToQueryHandler);
app.get('/luogu/prizes', getLuoguPrizesHandler);

// --- 静态文件服务 ---
// 这是让 Hono 将所有未匹配 API 路由的请求都交给静态资源处理器
app.get('*', serveStatic({ root: './' }));

export default app;
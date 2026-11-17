import { parseManifest, readResponseBytes } from '../shared/snapshot.js';

/** Keep the public endpoint, forwarding to the configured snapshot service. */
export default async function queryOierHandler(c) {
    if (!c.env.QUERY_API_ORIGIN) {
        return c.json({ error: 'The HTTP query service is not configured. Website search remains available.' }, 503);
    }
    try {
        const origin = new URL(c.env.QUERY_API_ORIGIN);
        const local = ['localhost', '127.0.0.1', '[::1]'].includes(origin.hostname);
        if ((origin.protocol !== 'https:' && !(origin.protocol === 'http:' && local)) || origin.username || origin.password) {
            throw new Error('Invalid query backend origin');
        }
        if (!c.req.raw.body) return c.json({ error: 'Invalid JSON' }, 400);
        let body;
        try { body = new TextDecoder().decode(await readResponseBytes(new Response(c.req.raw.body), 64 * 1024)); }
        catch { return c.json({ error: 'The query request is too large or incomplete.' }, 413); }
        try { JSON.parse(body); } catch { return c.json({ error: 'Invalid JSON' }, 400); }
        const manifest = await parseManifest(await c.env.ASSETS.fetch(new Request(new URL('/data/manifest.json', c.req.url))));
        const headers = new Headers({ 'Content-Type': 'application/json', 'X-OIer-Snapshot': manifest.snapshot_id });
        const adminSecret = c.req.header('X-Admin-Secret');
        if (adminSecret) headers.set('X-Admin-Secret', adminSecret);
        if (c.env.QUERY_BACKEND_SECRET) headers.set('X-Query-Backend-Key', c.env.QUERY_BACKEND_SECRET);
        const upstream = await fetch(new URL('/query-oier', origin), {
            method: 'POST', headers, body, redirect: 'error', signal: AbortSignal.timeout(30_000),
        });
        if (upstream.ok && upstream.headers.get('X-OIer-Snapshot') !== manifest.snapshot_id) {
            return c.json({ error: 'The query service is preparing the current data version. Please retry shortly.' }, 503);
        }
        const data = await upstream.json();
        return c.json(data, upstream.status, { 'Cache-Control': 'no-store', 'X-OIer-Snapshot': manifest.snapshot_id });
    } catch (error) {
        console.error('Snapshot query backend failed:', error.message);
        return c.json({ error: 'The HTTP query service is temporarily unavailable. Please retry or use website search.' }, 503);
    }
}

import http from 'node:http';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { Worker } from 'node:worker_threads';

export async function startQueryServer({
    manifestLocation, host = '127.0.0.1', port = 8788, adminSecret = '', backendSecret = '', timeout = 20_000,
}) {
    if (!manifestLocation) throw new Error('Set SNAPSHOT_MANIFEST to the static manifest URL or local file');
    if (!/^https?:\/\//.test(manifestLocation)) manifestLocation = path.resolve(manifestLocation);
    let worker;
    let manifest;
    let counter = 0;
    let closed = false;
    let restarting;
    const pending = new Map();
    function failPending(message) {
        for (const item of pending.values()) {
            clearTimeout(item.timer);
            item.resolve({ status: 503, body: { error: message } });
        }
        pending.clear();
    }
    async function startWorker() {
        const instance = new Worker(new URL('./query-worker.js', import.meta.url), { workerData: { manifestLocation } });
        worker = instance;
        await new Promise((resolve, reject) => {
            let settled = false;
            const timer = setTimeout(() => {
                settled = true;
                closed = true;
                instance.terminate();
                reject(new Error('Snapshot preparation timed out'));
            }, 90_000);
            instance.on('message', data => {
                if (data.type === 'ready') {
                    clearTimeout(timer);
                    settled = true;
                    manifest = data.manifest;
                    resolve();
                } else if (data.type === 'startup-error') {
                    clearTimeout(timer);
                    settled = true;
                    closed = true;
                    instance.terminate();
                    reject(new Error(data.error));
                } else {
                    const item = pending.get(data.id);
                    if (item) {
                        clearTimeout(item.timer);
                        pending.delete(data.id);
                        if (data.manifest) manifest = data.manifest;
                        item.resolve(data);
                    }
                }
            });
            instance.on('error', error => {
                clearTimeout(timer);
                failPending('The query service is restarting. Please retry.');
                if (!settled) { settled = true; closed = true; reject(error); }
            });
            instance.on('exit', () => {
                clearTimeout(timer);
                if (!settled) { settled = true; closed = true; reject(new Error('The query worker stopped during startup')); }
                if (!closed && worker === instance && !restarting) {
                    failPending('The query service restarted. Please retry.');
                    restarting = startWorker().finally(() => { restarting = undefined; });
                    restarting.catch(() => {});
                }
            });
        });
    }
    await startWorker();
    function runQuery(payload, isAdmin, expectedSnapshot) {
        if (closed || restarting) return Promise.resolve({ status: 503, body: { error: 'The query service is preparing data. Please retry shortly.' } });
        if (pending.size >= 8) return Promise.resolve({ status: 429, body: { error: 'The query service is busy. Please retry shortly.' } });
        return new Promise(resolve => {
            const id = ++counter;
            const timer = setTimeout(() => {
                failPending('This search took too long. Add a more specific filter and retry.');
                const previous = worker;
                restarting = previous.terminate().then(() => startWorker()).finally(() => { restarting = undefined; });
                restarting.catch(() => {});
            }, timeout);
            pending.set(id, { resolve, timer });
            worker.postMessage({ id, payload, isAdmin, expectedSnapshot });
        });
    }
    function send(response, status, body, version) {
        response.writeHead(status, {
            'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store',
            ...(version ? { 'X-OIer-Snapshot': version.snapshot_id, 'X-OIer-Upstream-SHA': version.upstream_sha } : {}),
        });
        response.end(JSON.stringify(body));
    }
    const server = http.createServer(async (request, response) => {
        try {
            if (backendSecret && request.headers['x-query-backend-key'] !== backendSecret) {
                send(response, 401, { error: 'Unauthorized query backend request.' });
                return;
            }
            const pathname = new URL(request.url, 'http://localhost').pathname;
            if (request.method === 'GET' && pathname === '/health') {
                send(response, restarting || closed ? 503 : 200, { status: restarting || closed ? 'preparing' : 'ready', snapshot_id: manifest.snapshot_id });
                return;
            }
            if (request.method === 'GET' && pathname === '/version') {
                send(response, 200, { oierfinder_sha: manifest.worker_version, oierdb_data_sha: manifest.upstream_sha }, manifest);
                return;
            }
            if (request.method !== 'POST' || pathname !== '/query-oier') {
                send(response, 404, { error: 'Not found' });
                return;
            }
            const chunks = [];
            let bytes = 0;
            for await (const chunk of request) {
                bytes += chunk.length;
                if (bytes > 64 * 1024) { send(response, 413, { error: 'The query request is too large.' }); return; }
                chunks.push(chunk);
            }
            let payload;
            try { payload = JSON.parse(Buffer.concat(chunks).toString('utf8')); }
            catch { send(response, 400, { error: 'Invalid JSON' }); return; }
            const isAdmin = Boolean(adminSecret && request.headers['x-admin-secret'] === adminSecret);
            const result = await runQuery(payload, isAdmin, request.headers['x-oier-snapshot']);
            send(response, result.status, result.body, result.manifest);
        } catch {
            if (!response.headersSent) send(response, 503, { error: 'The query service is unavailable. Please retry.' });
        }
    });
    server.requestTimeout = 10_000;
    server.headersTimeout = 10_000;
    try {
        await new Promise((resolve, reject) => { server.once('error', reject); server.listen(port, host, resolve); });
    } catch (error) {
        closed = true;
        await worker.terminate();
        throw error;
    }
    return {
        server,
        url: `http://${host}:${server.address().port}`,
        async close() {
            closed = true;
            failPending('The query service is stopping.');
            await worker.terminate();
            await new Promise(resolve => server.close(resolve));
        },
    };
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
    const service = await startQueryServer({
        manifestLocation: process.env.SNAPSHOT_MANIFEST,
        host: process.env.QUERY_API_HOST || '127.0.0.1',
        port: Number(process.env.QUERY_API_PORT || 8788),
        adminSecret: process.env.ADMIN_SECRET, backendSecret: process.env.QUERY_BACKEND_SECRET,
    });
    console.log(`OIer snapshot query API listening at ${service.url}`);
    for (const signal of ['SIGINT', 'SIGTERM']) process.once(signal, () => { service.close().finally(() => process.exit(0)); });
}

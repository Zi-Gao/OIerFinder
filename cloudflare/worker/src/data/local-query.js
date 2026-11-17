let worker;
let nextId = 0;
const pending = new Map();

function resetWorker(message) {
    worker?.terminate();
    worker = undefined;
    for (const request of pending.values()) {
        clearTimeout(request.timer);
        request.reject(new Error(message));
    }
    pending.clear();
}

function getWorker() {
    if (worker) return worker;
    if (typeof Worker === 'undefined' || typeof WebAssembly === 'undefined') {
        throw new Error('Your browser does not support local search. Use a current browser or the HTTP API.');
    }
    worker = new Worker(new URL('./query.worker.js', import.meta.url), { type: 'module' });
    worker.onerror = () => resetWorker('Local search could not start. Reload the page and try again.');
    worker.onmessageerror = () => resetWorker('Could not read the local search response. Please retry.');
    worker.onmessage = ({ data }) => {
        const request = pending.get(data.id);
        if (!request) return;
        if (data.type === 'progress') {
            if (data.phase === 'querying') {
                clearTimeout(request.timer);
                request.timer = setTimeout(() => resetWorker('This search took too long. Add a more specific filter and retry.'), 15_000);
            }
            request.onProgress(data);
            return;
        }
        clearTimeout(request.timer);
        pending.delete(data.id);
        if (data.type === 'error') request.reject(new Error(data.error));
        else if (data.status !== 200) request.reject(new Error(data.body?.error || 'Search failed. Please check your filters.'));
        else request.resolve({ ...data.body, snapshot_id: data.snapshot_id, offline: data.offline });
    };
    return worker;
}

export function searchLocalSnapshot(payload, onProgress = () => {}) {
    if (pending.size) return Promise.reject(new Error('A search is already running. Please wait for it to finish.'));
    return new Promise((resolve, reject) => {
        const instance = getWorker();
        const id = ++nextId;
        const timer = setTimeout(() => resetWorker('The data download took too long. Check your connection and retry.'), 120_000);
        pending.set(id, { resolve, reject, timer, onProgress });
        try { instance.postMessage({ id, payload }); }
        catch (error) { clearTimeout(timer); pending.delete(id); reject(error); }
    });
}

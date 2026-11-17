import { searchLocalSnapshot } from '../data/local-query.js';
import { parseManifest } from '../../shared/snapshot.js';

// Helper to construct headers
const getHeaders = (adminSecret) => {
  const headers = {};
  if (adminSecret) {
    // 更正：使用 X-Admin-Secret
    headers['X-Admin-Secret'] = adminSecret;
  }
  return headers;
};

export const searchOiers = (payload, _adminSecret, onProgress) => searchLocalSnapshot(payload, onProgress);

export const getVersionInfo = async () => {
  const manifest = await parseManifest(await fetch('/data/manifest.json', { cache: 'no-cache' }));
  return { oierfinder_sha: manifest.worker_version, oierdb_data_sha: manifest.upstream_sha };
};

export const getLuoguPrizes = async (uid, adminSecret) => {
  const response = await fetch(`/luogu/prizes?uid=${uid}&sync=1`, {
    headers: getHeaders(adminSecret),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ message: response.statusText }));
    throw new Error(`Luogu API Error (${response.status}): ${errorData.error || errorData.message}`);
  }
  return response.json();
};

export const getQueryFromJson = async (uid, adminSecret) => {
  const response = await fetch(`/luogu/to_query?uid=${uid}`, {
    headers: getHeaders(adminSecret),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ message: response.statusText }));
    throw new Error(`Luogu API Error (${response.status}): ${errorData.error || errorData.message}`);
  }
  return response.json();
};

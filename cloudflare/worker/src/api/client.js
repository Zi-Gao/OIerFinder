// src/api/client.js

// Helper to construct headers
const getHeaders = (adminSecret) => {
  const headers = {};
  if (adminSecret) {
    // 更正：使用 X-Admin-Secret
    headers['X-Admin-Secret'] = adminSecret;
  }
  return headers;
};

export const searchOiers = async (payload, adminSecret) => {
  const headers = getHeaders(adminSecret);
  headers['Content-Type'] = 'application/json';

  const response = await fetch('/query-oier', {
    method: 'POST',
    headers: headers,
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ message: response.statusText }));
    throw new Error(`API Error (${response.status}): ${errorData.error || errorData.message}`);
  }
  return response.json();
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
// src/api/client.js
export const searchOiers = async (payload) => {
  const response = await fetch('/query-oier', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ message: response.statusText }));
    throw new Error(`API Error (${response.status}): ${errorData.error || errorData.message}`);
  }
  return response.json();
};

export const getLuoguPrizes = async (uid) => {
  const response = await fetch(`/luogu/prizes?uid=${uid}&sync=1`);
   if (!response.ok) {
    const errorData = await response.json().catch(() => ({ message: response.statusText }));
    throw new Error(`Luogu API Error (${response.status}): ${errorData.error || errorData.message}`);
  }
  return response.json();
};

export const getQueryFromJson = async (uid) => {
    const response = await fetch(`/luogu/to_query?uid=${uid}`);
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({ message: response.statusText }));
        throw new Error(`Luogu API Error (${response.status}): ${errorData.error || errorData.message}`);
    }
    return response.json();
};
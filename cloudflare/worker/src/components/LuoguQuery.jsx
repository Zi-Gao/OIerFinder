// src/components/LuoguQuery.jsx
import React, { useState } from 'react';
import { getLuoguPrizes, getQueryFromJson, searchOiers } from '../api/client';
import ResultsDisplay from './ResultsDisplay';

function LuoguQuery() {
  const [uid, setUid] = useState('');
  const [prizes, setPrizes] = useState(null);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState({ prizes: false, search: false });
  const [error, setError] = useState('');

  const handleFetchPrizes = async () => {
    if (!uid) {
      setError('Please enter a Luogu UID.');
      return;
    }
    setLoading({ ...loading, prizes: true });
    setError('');
    setPrizes(null);
    try {
      const data = await getLuoguPrizes(uid);
      setPrizes(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading({ ...loading, prizes: false });
    }
  };

  const handleSearch = async () => {
    setLoading({ ...loading, search: true });
    setError('');
    setResults(null);
    try {
      const queryPayload = await getQueryFromJson(uid);
      const data = await searchOiers(queryPayload);
      setResults(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading({ ...loading, search: false });
    }
  };

  return (
    <div className="bg-gray-800 rounded-lg shadow-xl p-6 space-y-6">
      <div>
        <label htmlFor="luogu-uid" className="block text-gray-300 mb-2">Enter Luogu User ID:</label>
        <div className="flex gap-4">
          <input
            id="luogu-uid"
            type="text"
            value={uid}
            onChange={(e) => setUid(e.target.value)}
            placeholder="e.g., 2"
            className="flex-grow bg-gray-700 text-white p-2 border border-gray-600 rounded-md"
          />
          <button onClick={handleFetchPrizes} disabled={loading.prizes} className="bg-purple-600 hover:bg-purple-700 text-white font-bold py-2 px-4 rounded-md transition-colors disabled:bg-gray-500">
            {loading.prizes ? 'Fetching...' : 'Fetch Awards'}
          </button>
        </div>
      </div>
      
      {prizes && (
        <div className="bg-gray-700 p-4 rounded-lg">
          <h3 className="text-lg font-semibold mb-2">Awards Found ({prizes.length})</h3>
          <div className="max-h-60 overflow-y-auto text-sm border border-gray-600 rounded-md">
            <table className="w-full text-left">
                <thead className="sticky top-0 bg-gray-800">
                    <tr>
                        <th className="p-2">Year</th>
                        <th className="p-2">Contest</th>
                        <th className="p-2">Prize</th>
                    </tr>
                </thead>
                <tbody>
                    {prizes.map((p, i) => (
                        <tr key={i} className="border-t border-gray-600">
                            <td className="p-2">{p.year || 'N/A'}</td>
                            <td className="p-2">{p.contest_name}</td>
                            <td className="p-2">{p.prize_level}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
          </div>
          <button onClick={handleSearch} disabled={loading.search} className="mt-4 w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded-md transition-colors disabled:bg-gray-500">
            {loading.search ? 'Searching...' : 'Search OIerDB with these awards'}
          </button>
        </div>
      )}

      <ResultsDisplay results={results} error={error} loading={loading.search || loading.prizes} />
    </div>
  );
}

export default LuoguQuery;
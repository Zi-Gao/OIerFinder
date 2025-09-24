// src/components/JsonQuery.jsx
import React, { useState } from 'react';
import ResultsDisplay from './ResultsDisplay';
import { searchOiers } from '../api/client';

// Default query no longer needs a limit, it will be added from global settings
const defaultQuery = { record_filters: [{ contest_type: "NOI", level: "金牌" }] };

function JsonQuery({ adminSecret, limit }) { // Accept global props
  const [query, setQuery] = useState(JSON.stringify(defaultQuery, null, 2));
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setResults(null);
    try {
      const parsedQuery = JSON.parse(query);
      
      // Add the global limit if it's not already defined in the user's JSON
      if (!('limit' in parsedQuery)) {
        parsedQuery.limit = limit;
      }

      const data = await searchOiers(parsedQuery, adminSecret); // Pass adminSecret
      setResults(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-gray-800 rounded-lg shadow-xl p-6">
      <form onSubmit={handleSubmit}>
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          rows={15}
          className="w-full p-3 bg-gray-900 text-gray-200 font-mono border border-gray-600 rounded-md focus:ring-2 focus:ring-blue-500 focus:outline-none"
        />
        <button type="submit" disabled={loading} className="mt-4 w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded-md transition-colors disabled:bg-gray-500">
          {loading ? 'Searching...' : 'Search with JSON'}
        </button>
      </form>
      <ResultsDisplay results={results} error={error} loading={loading} />
    </div>
  );
}

export default JsonQuery;
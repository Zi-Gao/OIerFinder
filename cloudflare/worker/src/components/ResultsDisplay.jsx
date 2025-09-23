// src/components/ResultsDisplay.jsx
import React from 'react';

function ResultsDisplay({ results, error, loading }) {
  if (loading) {
    return (
      <div className="mt-6 text-center text-gray-400">
        <p>Loading...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mt-6 p-4 bg-red-900 border border-red-700 text-red-200 rounded-lg">
        <p className="font-bold">An Error Occurred</p>
        <p className="text-sm">{error}</p>
      </div>
    );
  }

  if (!results) return null;

  return (
    <div className="mt-6 space-y-4">
        <h2 className="text-2xl font-semibold border-b border-gray-600 pb-2">Results</h2>
        <details className="bg-gray-700 p-3 rounded-lg">
            <summary className="cursor-pointer font-semibold">Usage Statistics</summary>
            <pre className="mt-2 text-sm bg-gray-900 p-3 rounded-md overflow-x-auto">
                <code>{JSON.stringify(results.usage, null, 2)}</code>
            </pre>
        </details>
        <details open className="bg-gray-700 p-3 rounded-lg">
            <summary className="cursor-pointer font-semibold">Found OIers ({results.data.length})</summary>
             <div className="mt-2 text-sm bg-gray-900 p-3 rounded-md overflow-x-auto">
                <pre>
                    <code>{JSON.stringify(results.data, null, 2)}</code>
                </pre>
            </div>
        </details>
    </div>
  );
}
export default ResultsDisplay;
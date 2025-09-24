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

  // Helper function to format gender from number to string
  // *** 更正了这里的逻辑 ***
  const formatGender = (gender) => {
    switch (gender) {
      case 1:
        return 'Male';
      case -1:
        return 'Female'; // 0 是女性
      default:
        return 'N/A';
    }
  };

  return (
    <div className="mt-6 space-y-4">
        <h2 className="text-2xl font-semibold border-b border-gray-600 pb-2">Results</h2>
        
        {results.usage && (
          <details className="bg-gray-700 p-3 rounded-lg">
              <summary className="cursor-pointer font-semibold">Usage Statistics</summary>
              <pre className="mt-2 text-sm bg-gray-900 p-3 rounded-md overflow-x-auto">
                  <code>{JSON.stringify(results.usage, null, 2)}</code>
              </pre>
          </details>
        )}

        <details open className="bg-gray-700 p-3 rounded-lg">
            <summary className="cursor-pointer font-semibold">Found OIers ({results.data.length})</summary>
             <div className="mt-2 overflow-x-auto">
                <table className="w-full text-left text-sm whitespace-nowrap">
                    <thead className="bg-gray-800/50">
                        <tr>
                            <th className="p-3">UID</th>
                            <th className="p-3">Name</th>
                            <th className="p-3">Gender</th>
                            <th className="p-3">Enrollment Year</th>
                            <th className="p-3">OIerDB Score</th>
                            <th className="p-3">CCF Score</th>
                            <th className="p-3">CCF Level</th>
                        </tr>
                    </thead>
                    <tbody>
                        {results.data.map((oier) => (
                            <tr key={oier.uid} className="border-t border-gray-600 hover:bg-gray-600/30 transition-colors">
                                <td className="p-3 font-mono">{oier.uid}</td>
                                <td className="p-3">
                                    <a 
                                        href={`https://oier.baoshuo.dev/oier/${oier.uid}`} 
                                        target="_blank" 
                                        rel="noopener noreferrer"
                                        className="text-blue-400 hover:text-blue-300 hover:underline"
                                    >
                                        {oier.name}
                                    </a>
                                </td>
                                <td className="p-3">{formatGender(oier.gender)}</td>
                                <td className="p-3">{oier.enroll_middle || 'N/A'}</td>
                                <td className="p-3">{oier.oierdb_score}</td>
                                <td className="p-3">{oier.ccf_score}</td>
                                <td className="p-3">{oier.ccf_level}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </details>
    </div>
  );
}

export default ResultsDisplay;
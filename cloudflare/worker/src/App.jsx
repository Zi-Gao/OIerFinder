// src/App.jsx
import React, { useState } from 'react';
import QueryBuilder from './components/QueryBuilder';
import JsonQuery from './components/JsonQuery';
import LuoguQuery from './components/LuoguQuery';

const TABS = {
  BUILDER: 'UI Builder',
  JSON: 'Raw JSON',
  LUOGU: 'Luogu UID',
};

function App() {
  const [activeTab, setActiveTab] = useState(TABS.BUILDER);

  const renderTabContent = () => {
    switch (activeTab) {
      case TABS.LUOGU:
        return <LuoguQuery />;
      case TABS.JSON:
        return <JsonQuery />;
      case TABS.BUILDER:
      default:
        return <QueryBuilder />;
    }
  };

  return (
    <div className="container mx-auto p-4 md:p-8">
      <header className="text-center mb-8">
        <h1 className="text-4xl md:text-5xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-500">
          OIer Finder
        </h1>
        <p className="text-gray-400 mt-2">A powerful tool to find competitive programmers.</p>
      </header>

      <div className="bg-gray-800 rounded-lg shadow-xl p-2 mb-8 max-w-md mx-auto">
        <div className="flex justify-center space-x-1">
          {Object.values(TABS).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`w-full px-4 py-2 text-sm font-semibold rounded-md transition-colors duration-200 ${
                activeTab === tab
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

      <main>
        {renderTabContent()}
      </main>
    </div>
  );
}

export default App;
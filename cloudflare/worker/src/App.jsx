// src/App.jsx (修改)
import React, { useState, useEffect } from 'react'; // 1. 导入 useEffect
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
  
  // 2. 使用函数式初始值从 localStorage 加载数据
  // 这确保了 localStorage 只在组件首次渲染时被读取一次
  const [adminSecret, setAdminSecret] = useState(
    () => localStorage.getItem('oierFinderAdminSecret') || ''
  );
  const [limit, setLimit] = useState(
    () => parseInt(localStorage.getItem('oierFinderLimit'), 10) || 10
  );

  // 3. 使用 useEffect 在数据变化时将其保存到 localStorage
  useEffect(() => {
    localStorage.setItem('oierFinderAdminSecret', adminSecret);
  }, [adminSecret]); // 这个 effect 只在 adminSecret 变化时运行

  useEffect(() => {
    localStorage.setItem('oierFinderLimit', limit);
  }, [limit]); // 这个 effect 只在 limit 变化时运行


  const renderTabContent = () => {
    const props = { adminSecret, limit };
    switch (activeTab) {
      case TABS.LUOGU:
        return <LuoguQuery {...props} />;
      case TABS.JSON:
        return <JsonQuery {...props} />;
      case TABS.BUILDER:
      default:
        return <QueryBuilder {...props} />;
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

      <div className="grid grid-cols-1 md:grid-cols-12 gap-8">
        {/* Left Sidebar: Global Settings */}
        <aside className="md:col-span-4 lg:col-span-3">
          <div className="bg-gray-800 rounded-lg shadow-xl p-6 sticky top-8">
            <h2 className="text-xl font-semibold text-gray-200 border-b border-gray-600 pb-2 mb-4">
              Global Settings
            </h2>
            <div className="space-y-4">
              <div>
                <label htmlFor="admin-secret" className="block text-sm text-gray-400 mb-1">X-Admin-Secret Header</label>
                <input
                  id="admin-secret"
                  type="password"
                  value={adminSecret}
                  onChange={(e) => setAdminSecret(e.target.value)}
                  placeholder="Optional admin secret"
                  className="w-full bg-gray-700 text-white p-2 border border-gray-600 rounded-md focus:ring-2 focus:ring-blue-500 focus:outline-none"
                />
              </div>
              <div>
                <label htmlFor="global-limit" className="block text-sm text-gray-400 mb-1">Result Limit</label>
                <input
                  id="global-limit"
                  type="number"
                  value={limit}
                  onChange={(e) => setLimit(Number(e.target.value) || 0)}
                  className="w-full bg-gray-700 text-white p-2 border border-gray-600 rounded-md focus:ring-2 focus:ring-blue-500 focus:outline-none"
                />
              </div>
            </div>
          </div>
        </aside>

        {/* Right Content Area */}
        <main className="md:col-span-8 lg:col-span-9">
          <div className="bg-gray-800 rounded-lg shadow-xl p-2 mb-8 max-w-md">
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
          <div>
            {renderTabContent()}
          </div>
        </main>
      </div>
    </div>
  );
}

export default App;
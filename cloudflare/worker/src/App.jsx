// src/App.jsx
import React, { useState, useEffect } from 'react';
import QueryBuilder from './components/QueryBuilder';
import JsonQuery from './components/JsonQuery';
import LuoguQuery from './components/LuoguQuery';
import ResultsDisplay from './components/ResultsDisplay'; // 引入 ResultsDisplay
import { searchOiers } from './api/client'; // 引入 searchOiers

const TABS = {
  BUILDER: 'UI Builder',
  JSON: 'Raw JSON',
  LUOGU: 'Luogu UID',
};

// 辅助函数：清理过滤器中的空值
const cleanObject = (obj) => {
    const newObj = {};
    for (const key in obj) {
        const value = obj[key];
        if (value !== '' && value !== null && value !== undefined) {
            newObj[key] = value;
        }
    }
    return newObj;
};

function App() {
  const [activeTab, setActiveTab] = useState(TABS.BUILDER);
  
  // --- 共享的查询状态 ---
  const [recordFilters, setRecordFilters] = useState([{}]);
  const [oierFilters, setOierFilters] = useState({});

  // --- 共享的结果状态 ---
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // --- 全局设置状态 ---
  const [adminSecret, setAdminSecret] = useState(() => localStorage.getItem('oierFinderAdminSecret') || '');
  const [limit, setLimit] = useState(() => parseInt(localStorage.getItem('oierFinderLimit'), 10) || 10);

  useEffect(() => {
    localStorage.setItem('oierFinderAdminSecret', adminSecret);
  }, [adminSecret]);

  useEffect(() => {
    localStorage.setItem('oierFinderLimit', limit);
  }, [limit]);

  // --- [新增] 核心搜索函数，由 App 组件统一执行 ---
  const handleSearch = async (currentRecordFilters, currentOierFilters) => {
    setLoading(true);
    setError('');
    setResults(null);
    
    const stringToArray = (str) => str.split(',').map(item => item.trim()).filter(Boolean);
    const stringToNumberArray = (str) => stringToArray(str).map(Number);

    const processedRecordFilters = currentRecordFilters
      .map(f => {
        const cleaned = cleanObject(f);
        if (cleaned.provinces && typeof cleaned.provinces === 'string') cleaned.provinces = stringToArray(cleaned.provinces);
        if (cleaned.years && typeof cleaned.years === 'string') cleaned.years = stringToNumberArray(cleaned.years);
        if (cleaned.contest_ids && typeof cleaned.contest_ids === 'string') cleaned.contest_ids = stringToNumberArray(cleaned.contest_ids);
        if (cleaned.school_ids && typeof cleaned.school_ids === 'string') cleaned.school_ids = stringToNumberArray(cleaned.school_ids);
        return cleaned;
      })
      .filter(f => Object.keys(f).length > 0);
      
    const processedOierFilters = cleanObject(currentOierFilters);
    if (processedOierFilters.initials && typeof processedOierFilters.initials === 'string') {
        processedOierFilters.initials = stringToArray(processedOierFilters.initials);
    }
    // if (processedOierFilters.gender) {
    //     processedOierFilters.gender = Number(processedOierFilters.gender);
    // }

    const payload = {
      record_filters: processedRecordFilters,
      oier_filters: processedOierFilters,
      limit: Number(limit) || 10
    };

    try {
      const data = await searchOiers(payload, adminSecret);
      setResults(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // --- [新增] 从洛谷查询转换到 UI Builder 的函数 ---
  const handleLuoguQueryImport = (queryPayload) => {
    setRecordFilters(queryPayload.record_filters || [{}]);
    setOierFilters(queryPayload.oier_filters || {});
    setActiveTab(TABS.BUILDER);
    // 可选：立即执行搜索
    // handleSearch(queryPayload.record_filters || [{}], queryPayload.oier_filters || {});
  };

  const renderTabContent = () => {
    const commonProps = { adminSecret, limit };
    switch (activeTab) {
      case TABS.LUOGU:
        return <LuoguQuery {...commonProps} onImportQuery={handleLuoguQueryImport} />;
      case TABS.JSON:
        return (
            <JsonQuery
                {...commonProps}
                recordFilters={recordFilters}
                oierFilters={oierFilters}
                onFiltersChange={(newRecords, newOier) => {
                    setRecordFilters(newRecords);
                    setOierFilters(newOier);
                }}
                onSearch={(records, oier) => handleSearch(records, oier)}
            />
        );
      case TABS.BUILDER:
      default:
        return (
            <QueryBuilder 
                {...commonProps}
                recordFilters={recordFilters}
                oierFilters={oierFilters}
                onRecordFiltersChange={setRecordFilters}
                onOierFiltersChange={setOierFilters}
                onSearch={(records, oier) => handleSearch(records, oier)}
            />
        );
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
          <div className="space-y-6">
            {renderTabContent()}
            {/* [修改] 结果展示区移到 App 级别，成为所有 Tab 共享的组件 */}
            <ResultsDisplay results={results} error={error} loading={loading} />
          </div>
        </main>
      </div>
    </div>
  );
}

export default App;
// src/components/JsonQuery.jsx
import React, { useState, useEffect } from 'react';

function JsonQuery({ 
    recordFilters, 
    oierFilters, 
    onFiltersChange, 
    onSearch,
    limit 
}) {
  // 本地状态仅用于文本框的显示
  const [jsonString, setJsonString] = useState('');

  // [修改] 当从 App 传入的 filters 变化时（例如从 UI tab 切换过来），更新文本框内容
  useEffect(() => {
    const queryPayload = {
      record_filters: recordFilters,
      oier_filters: oierFilters,
      limit: limit // 包含 limit
    };
    setJsonString(JSON.stringify(queryPayload, null, 2));
  }, [recordFilters, oierFilters, limit]);
  
  const handleTextChange = (e) => {
    const newJsonString = e.target.value;
    setJsonString(newJsonString);
    // [新增] 实时尝试解析 JSON 并更新 App 状态
    try {
      const parsed = JSON.parse(newJsonString);
      // 验证解析出的对象结构是否正确
      const newRecords = Array.isArray(parsed.record_filters) ? parsed.record_filters : [{}];
      const newOier = typeof parsed.oier_filters === 'object' && parsed.oier_filters !== null ? parsed.oier_filters : {};
      onFiltersChange(newRecords, newOier);
    } catch (error) {
      // 如果 JSON 格式不正确，则不更新 App 状态，允许用户继续编辑
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    try {
        const parsed = JSON.parse(jsonString);
        // 执行搜索时，使用文本框中最新的、可能未同步到 App 的数据
        onSearch(parsed.record_filters || [], parsed.oier_filters || {});
    } catch (err) {
        alert("Invalid JSON format: " + err.message);
    }
  };

  return (
    <div className="bg-gray-800 rounded-lg shadow-xl p-6">
      <form onSubmit={handleSubmit}>
        <textarea
          value={jsonString}
          onChange={handleTextChange}
          rows={15}
          className="w-full p-3 bg-gray-900 text-gray-200 font-mono border border-gray-600 rounded-md focus:ring-2 focus:ring-blue-500 focus:outline-none"
        />
        <button type="submit" className="mt-4 w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded-md transition-colors">
          Search with JSON
        </button>
      </form>
      {/* ResultsDisplay has been moved to App.jsx */}
    </div>
  );
}

export default JsonQuery;
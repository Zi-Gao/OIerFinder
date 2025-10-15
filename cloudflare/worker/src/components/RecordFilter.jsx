// src/components/RecordFilter.jsx
import React, { useState } from 'react';

// --- Reusable, styled form components ---
const Input = ({ ...props }) => <input className="w-full bg-gray-700 text-white p-2 border border-gray-600 rounded-md focus:ring-2 focus:ring-blue-500 focus:outline-none" {...props} />;
const Select = ({ children, ...props }) => <select className="w-full bg-gray-700 text-white p-2 border border-gray-600 rounded-md focus:ring-2 focus:ring-blue-500 focus:outline-none" {...props}>{children}</select>;
const Label = ({ children }) => <label className="block text-sm text-gray-400 mb-1">{children}</label>;

const CONTEST_TYPES = ["CSP入门", "CSP提高", "NOIP普及", "NOIP提高", "NOIP", "WC", "NOID类", "NOI", "APIO", "CTSC"];
const LEVELS = ["金牌", "银牌", "铜牌", "一等奖", "二等奖", "三等奖"];

function RecordFilter({ filter, onChange, onRemove }) {
  const [showAdvanced, setShowAdvanced] = useState(false);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    const newValue = type === 'checkbox' ? (checked ? true : false) : value;
    onChange({ ...filter, [name]: newValue });
  };
  
  // [修改] 清理高级选项时，也包括 year_start 和 year_end
  const toggleAdvanced = () => {
    if (showAdvanced) {
      // 从 filter 对象中移除所有高级字段
      const {
        years, provinces, contest_ids, school_ids,
        min_score, max_score, min_rank, max_rank, fall_semester,
        year_start, year_end, // <-- 新增清理字段
        ...basicFilter
      } = filter;
      onChange(basicFilter);
    }
    setShowAdvanced(!showAdvanced);
  };

  return (
    <div className="bg-gray-700/50 p-4 rounded-lg border border-gray-600 relative space-y-4">
      <button onClick={onRemove} className="absolute -top-3 -right-3 bg-red-600 hover:bg-red-700 text-white rounded-full w-7 h-7 flex items-center justify-center font-bold text-lg shadow-lg transition-transform hover:scale-110 z-10">
        &times;
      </button>
      
      {/* --- [修改] 基础选项现在使用单个 Year 输入 --- */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div>
          <Label>Contest Type</Label>
          <Select name="contest_type" value={filter.contest_type || ''} onChange={handleChange}>
            <option value="">Any</option>
            {CONTEST_TYPES.map(c => <option key={c} value={c}>{c}</option>)}
          </Select>
        </div>
        <div>
          <Label>Level</Label>
          <Select name="level" value={filter.level || ''} onChange={handleChange}>
            <option value="">Any</option>
            {LEVELS.map(l => <option key={l} value={l}>{l}</option>)}
          </Select>
        </div>
        <div>
          <Label>Year</Label>
          <Input 
            type="number" 
            name="year" 
            placeholder="e.g., 2023" 
            value={filter.year || ''} 
            onChange={handleChange} 
          />
        </div>
      </div>
      
      {/* --- 高级选项开关 --- */}
      <div className="border-t border-gray-600/50 pt-3">
        <button onClick={toggleAdvanced} className="text-blue-400 hover:text-blue-300 text-sm font-medium">
          {showAdvanced ? 'Hide Advanced Options ▲' : 'Show Advanced Options ▼'}
        </button>
      </div>

      {/* --- [修改] 高级选项容器，现在包含 Year Range 和 Years --- */}
      {showAdvanced && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 border-t border-gray-600/50 pt-4 animate-fade-in">
          
          {/* 年份相关高级选项 */}
          <div className="sm:col-span-2 lg:col-span-2">
            <Label>Year Range (Start - End)</Label>
            <div className="flex items-center gap-2">
              <Input type="number" name="year_start" placeholder="Start" value={filter.year_start || ''} onChange={handleChange} />
              <span>-</span>
              <Input type="number" name="year_end" placeholder="End" value={filter.year_end || ''} onChange={handleChange} />
            </div>
          </div>
          <div className="lg:col-span-3">
            <Label>Years (comma-separated, overrides other year fields)</Label>
            <Input type="text" name="years" placeholder="e.g., 2020, 2022" value={filter.years || ''} onChange={handleChange} />
          </div>
          
          {/* 其他高级选项 */}
          <div className="lg:col-span-3">
            <Label>Provinces (comma-separated)</Label>
            <Input type="text" name="provinces" placeholder="e.g., 北京, 上海, 浙江" value={filter.provinces || ''} onChange={handleChange} />
          </div>
          <div>
            <Label>Score Range (Min - Max)</Label>
            <div className="flex items-center gap-2">
              <Input type="number" name="min_score" placeholder="Min" value={filter.min_score || ''} onChange={handleChange} />
              <span>-</span>
              <Input type="number" name="max_score" placeholder="Max" value={filter.max_score || ''} onChange={handleChange} />
            </div>
          </div>
          
          <div>
            <Label>Rank Range (Min - Max)</Label>
            <div className="flex items-center gap-2">
              <Input type="number" name="min_rank" placeholder="Min" value={filter.min_rank || ''} onChange={handleChange} />
              <span>-</span>
              <Input type="number" name="max_rank" placeholder="Max" value={filter.max_rank || ''} onChange={handleChange} />
            </div>
          </div>
          <div className="flex items-center justify-start pt-6">
            <label className="flex items-center space-x-2 text-gray-300">
              <Input type="checkbox" name="fall_semester" checked={!!filter.fall_semester} onChange={handleChange} className="w-4 h-4 rounded" />
              <span>Fall Semester Only</span>
            </label>
          </div>
          <div className="lg:col-span-3">
            <Label>Contest IDs (comma-separated)</Label>
            <Input type="text" name="contest_ids" placeholder="e.g., 101, 102" value={filter.contest_ids || ''} onChange={handleChange} />
          </div>
          
          <div className="lg:col-span-3">
            <Label>School IDs (comma-separated)</Label>
            <Input type="text" name="school_ids" placeholder="e.g., 233, 234" value={filter.school_ids || ''} onChange={handleChange} />
          </div>
        </div>
      )}
    </div>
  );
}

export default RecordFilter;
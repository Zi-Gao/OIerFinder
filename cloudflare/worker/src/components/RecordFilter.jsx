// src/components/RecordFilter.jsx
import React from 'react';

// --- Reusable, styled form components ---
const Input = ({ ...props }) => <input className="w-full bg-gray-700 text-white p-2 border border-gray-600 rounded-md focus:ring-2 focus:ring-blue-500 focus:outline-none" {...props} />;
const Select = ({ children, ...props }) => <select className="w-full bg-gray-700 text-white p-2 border border-gray-600 rounded-md focus:ring-2 focus:ring-blue-500 focus:outline-none" {...props}>{children}</select>;
const Label = ({ children }) => <label className="block text-sm text-gray-400 mb-1">{children}</label>;

const CONTEST_TYPES = ["CSP入门", "CSP提高", "NOIP普及", "NOIP提高", "NOIP", "WC", "NOID类", "NOI", "APIO", "CTSC"];
const LEVELS = ["金牌", "银牌", "铜牌", "一等奖", "二等獎", "三等奖"];

function RecordFilter({ filter, onChange, onRemove }) {
  const handleChange = (e) => {
    const { name, value } = e.target;
    // Keep empty strings for controlled inputs, the parent will clean them up.
    onChange({ ...filter, [name]: value });
  };

  return (
    <div className="bg-gray-700/50 p-4 rounded-lg border border-gray-600 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 relative">
      <button onClick={onRemove} className="absolute -top-3 -right-3 bg-red-600 hover:bg-red-700 text-white rounded-full w-7 h-7 flex items-center justify-center font-bold text-lg shadow-lg transition-transform hover:scale-110">
        &times;
      </button>
      
      {/* Contest and Level */}
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

      {/* Year Range */}
      <div className="sm:col-span-2 lg:col-span-1">
        <Label>Year Range</Label>
        <div className="flex items-center gap-2">
          <Input type="number" name="year_start" placeholder="Start" value={filter.year_start || ''} onChange={handleChange} />
          <span>-</span>
          <Input type="number" name="year_end" placeholder="End" value={filter.year_end || ''} onChange={handleChange} />
        </div>
      </div>

      {/* Score Range */}
      <div className="sm:col-span-2 lg:col-span-1">
        <Label>Score Range</Label>
        <div className="flex items-center gap-2">
          <Input type="number" name="min_score" placeholder="Min" value={filter.min_score || ''} onChange={handleChange} />
          <span>-</span>
          <Input type="number" name="max_score" placeholder="Max" value={filter.max_score || ''} onChange={handleChange} />
        </div>
      </div>

      {/* Provinces */}
      <div className="col-span-1 sm:col-span-2">
        <Label>Provinces (comma-separated)</Label>
        <Input type="text" name="provinces" placeholder="e.g., 北京, 上海, 浙江" value={filter.provinces || ''} onChange={handleChange} />
      </div>
    </div>
  );
}

export default RecordFilter;
// src/components/QueryBuilder.jsx
import React, { useState } from 'react';
import RecordFilter from './RecordFilter';

// --- Reusable, styled form components ---
const Input = ({ ...props }) => <input className="w-full bg-gray-700 text-white p-2 border border-gray-600 rounded-md focus:ring-2 focus:ring-blue-500 focus:outline-none" {...props} />;
const Select = ({ children, ...props }) => <select className="w-full bg-gray-700 text-white p-2 border border-gray-600 rounded-md focus:ring-2 focus:ring-blue-500 focus:outline-none" {...props}>{children}</select>;
const Label = ({ children }) => <label className="block text-sm text-gray-400 mb-1">{children}</label>;

function QueryBuilder({ 
    recordFilters, 
    oierFilters, 
    onRecordFiltersChange, 
    onOierFiltersChange, 
    onSearch 
}) {
  const [showAdvancedOier, setShowAdvancedOier] = useState(false);

  const addFilter = () => onRecordFiltersChange([...recordFilters, {}]);
  const removeFilter = (index) => onRecordFiltersChange(recordFilters.filter((_, i) => i !== index));
  const updateRecordFilter = (index, newFilter) => {
    const newFilters = [...recordFilters];
    newFilters[index] = newFilter;
    onRecordFiltersChange(newFilters);
  };
  const handleOierFilterChange = (e) => {
    const { name, value } = e.target;
    onOierFiltersChange(prev => ({ ...prev, [name]: value }));
  };
  const toggleAdvancedOier = () => {
    if (showAdvancedOier) {
      const { gender, enroll_min, enroll_max, ...basicFilters } = oierFilters;
      onOierFiltersChange(basicFilters);
    }
    setShowAdvancedOier(!showAdvancedOier);
  };

  const handleLocalSearch = () => {
    onSearch(recordFilters, oierFilters);
  };

  return (
    <div className="bg-gray-800 rounded-lg shadow-xl p-6 space-y-6">
      <div>
        <h3 className="text-xl font-semibold text-gray-200 border-b border-gray-600 pb-2 mb-4">
          Record Conditions
          <span className="text-sm font-normal text-gray-400"> (OIer must satisfy ALL of these)</span>
        </h3>
        <div className="space-y-4">
          {recordFilters.map((filter, index) => (
            <RecordFilter
              key={index}
              filter={filter}
              onChange={(newFilter) => updateRecordFilter(index, newFilter)}
              onRemove={() => removeFilter(index)}
            />
          ))}
        </div>
        <button onClick={addFilter} className="mt-4 bg-green-600/50 hover:bg-green-600/80 text-green-200 font-bold py-2 px-4 rounded-md transition-colors text-sm">
          + Add Record Condition
        </button>
      </div>

      <div>
        <h3 className="text-xl font-semibold text-gray-200 border-b border-gray-600 pb-2 mb-4">OIer Conditions</h3>
        <div className="bg-gray-700/50 p-4 rounded-lg border border-gray-600 space-y-4">
            <div>
                <Label>Initials (comma-separated)</Label>
                <Input
                    type="text"
                    name="initials"
                    placeholder="e.g., QZH, DMY"
                    value={oierFilters.initials || ''}
                    onChange={handleOierFilterChange}
                />
            </div>
            <div className="border-t border-gray-600/50 pt-3">
              <button onClick={toggleAdvancedOier} className="text-blue-400 hover:text-blue-300 text-sm font-medium">
                {showAdvancedOier ? 'Hide Advanced Options ▲' : 'Show Advanced Options ▼'}
              </button>
            </div>
            {showAdvancedOier && (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 border-t border-gray-600/50 pt-4 animate-fade-in">
                  <div>
                      <Label>Gender</Label>
                      <Select name="gender" value={oierFilters.gender || ''} onChange={handleOierFilterChange}>
                          <option value="">Any</option>
                          <option value="1">Male</option>
                          <option value="-1">Female</option>
                      </Select>
                  </div>
                  <div className="sm:col-span-2">
                      <Label>Enrollment Year Range (Start - End)</Label>
                      <div className="flex items-center gap-2">
                          <Input type="number" name="enroll_min" placeholder="Start Year" value={oierFilters.enroll_min || ''} onChange={handleOierFilterChange}/>
                          <span>-</span>
                          <Input type="number" name="enroll_max" placeholder="End Year" value={oierFilters.enroll_max || ''} onChange={handleOierFilterChange}/>
                      </div>
                  </div>
              </div>
            )}
        </div>
      </div>

      <div className="flex items-center justify-end gap-4 pt-4 border-t border-gray-700">
        <button onClick={handleLocalSearch} className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-6 rounded-md transition-colors">
          Search
        </button>
      </div>
      
      {/* ResultsDisplay has been moved to App.jsx */}
    </div>
  );
}

export default QueryBuilder;
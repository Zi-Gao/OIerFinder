// src/components/QueryBuilder.jsx
import React, { useState } from 'react';
import RecordFilter from './RecordFilter';
import ResultsDisplay from './ResultsDisplay';
import { searchOiers } from '../api/client';

// --- Reusable, styled form components ---
const Input = ({ ...props }) => <input className="w-full bg-gray-700 text-white p-2 border border-gray-600 rounded-md focus:ring-2 focus:ring-blue-500 focus:outline-none" {...props} />;
const Select = ({ children, ...props }) => <select className="w-full bg-gray-700 text-white p-2 border border-gray-600 rounded-md focus:ring-2 focus:ring-blue-500 focus:outline-none" {...props}>{children}</select>;
const Label = ({ children }) => <label className="block text-sm text-gray-400 mb-1">{children}</label>;


function QueryBuilder() {
  const [recordFilters, setRecordFilters] = useState([{}]);
  const [oierFilters, setOierFilters] = useState({});
  const [limit, setLimit] = useState(10);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const addFilter = () => setRecordFilters([...recordFilters, {}]);
  const removeFilter = (index) => setRecordFilters(recordFilters.filter((_, i) => i !== index));
  const updateRecordFilter = (index, newFilter) => {
    const newFilters = [...recordFilters];
    newFilters[index] = newFilter;
    setRecordFilters(newFilters);
  };

  const handleOierFilterChange = (e) => {
    const { name, value } = e.target;
    setOierFilters(prev => ({ ...prev, [name]: value }));
  };

  const handleSearch = async () => {
    setLoading(true);
    setError('');
    setResults(null);

    // --- Payload Cleanup and Formatting ---
    const cleanObject = (obj) => {
        const newObj = {};
        for (const key in obj) {
            if (obj[key] !== '' && obj[key] !== null && obj[key] !== undefined) {
                // Convert numeric fields from string
                if (['year_start', 'year_end', 'min_score', 'max_score', 'enroll_min', 'enroll_max', 'gender'].includes(key)) {
                    newObj[key] = Number(obj[key]);
                } else {
                    newObj[key] = obj[key];
                }
            }
        }
        return newObj;
    };

    const processedRecordFilters = recordFilters
        .map(f => {
            const cleaned = cleanObject(f);
            if (cleaned.provinces && typeof cleaned.provinces === 'string') {
                cleaned.provinces = cleaned.provinces.split(',').map(p => p.trim()).filter(Boolean);
            }
            return cleaned;
        })
        .filter(f => Object.keys(f).length > 0);

    const processedOierFilters = cleanObject(oierFilters);

    const payload = { 
        record_filters: processedRecordFilters, 
        oier_filters: processedOierFilters, 
        limit: Number(limit) || 10 
    };
    // --- End of Payload Cleanup ---

    try {
      const data = await searchOiers(payload);
      setResults(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
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
        <div className="bg-gray-700/50 p-4 rounded-lg border border-gray-600 grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
                <Label>Gender</Label>
                <Select name="gender" value={oierFilters.gender || ''} onChange={handleOierFilterChange}>
                    <option value="">Any</option>
                    <option value="1">Male</option>
                    <option value="-1">Female</option>
                </Select>
            </div>
            <div className="sm:col-span-2">
                <Label>Enrollment Year Range</Label>
                <div className="flex items-center gap-2">
                    <Input type="number" name="enroll_min" placeholder="Start Year" value={oierFilters.enroll_min || ''} onChange={handleOierFilterChange}/>
                    <span>-</span>
                    <Input type="number" name="enroll_max" placeholder="End Year" value={oierFilters.enroll_max || ''} onChange={handleOierFilterChange}/>
                </div>
            </div>
        </div>
      </div>
      
      <div className="flex items-center justify-end gap-4 pt-4 border-t border-gray-700">
        <label htmlFor="limit" className="text-gray-300">Limit:</label>
        <Input
          id="limit"
          type="number"
          value={limit}
          onChange={(e) => setLimit(e.target.value)}
          className="w-24"
        />
        <button onClick={handleSearch} disabled={loading} className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-6 rounded-md transition-colors disabled:bg-gray-500 disabled:cursor-not-allowed">
          {loading ? 'Searching...' : 'Search'}
        </button>
      </div>

      <ResultsDisplay results={results} error={error} loading={loading} />
    </div>
  );
}

export default QueryBuilder;
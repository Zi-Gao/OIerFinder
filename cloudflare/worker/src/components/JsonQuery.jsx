import React, { useState, useEffect } from 'react';
import BannerCard from './BannerCard';
import ActionBar from './ActionBar';
import { Code2 } from "lucide-react";

function JsonQuery({ 
    recordFilters, 
    oierFilters, 
    onFiltersChange, 
    onLimitChange,
    onSearch,
    limit,
    loading
}) {
  const [jsonString, setJsonString] = useState('');

  const parsePayload = (value) => {
    const parsed = JSON.parse(value);
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
      throw new Error('The payload must be a JSON object.');
    }
    if (!Array.isArray(parsed.record_filters)) {
      throw new Error("'record_filters' must be an array.");
    }
    if (
      typeof parsed.oier_filters !== 'object' ||
      parsed.oier_filters === null ||
      Array.isArray(parsed.oier_filters)
    ) {
      throw new Error("'oier_filters' must be an object.");
    }
    const parsedLimit = Number(parsed.limit);
    if (!Number.isFinite(parsedLimit) || parsedLimit <= 0) {
      throw new Error("'limit' must be a positive number.");
    }
    return {
      recordFilters: parsed.record_filters,
      oierFilters: parsed.oier_filters,
      limit: Math.min(Math.floor(parsedLimit), 100),
    };
  };

  useEffect(() => {
    const queryPayload = {
      record_filters: recordFilters,
      oier_filters: oierFilters,
      limit: limit
    };
    setJsonString(JSON.stringify(queryPayload, null, 2));
  }, [recordFilters, oierFilters, limit]);
  
  const handleTextChange = (e) => {
    const newJsonString = e.target.value;
    setJsonString(newJsonString);
    try {
      const parsed = parsePayload(newJsonString);
      onFiltersChange(parsed.recordFilters, parsed.oierFilters);
      onLimitChange(parsed.limit);
    } catch {
      // Allow invalid JSON while typing
    }
  };

  const handleSubmit = (e) => {
    if (e) e.preventDefault();
    try {
        const parsed = parsePayload(jsonString);
        onSearch(parsed.recordFilters, parsed.oierFilters, parsed.limit);
    } catch (err) {
        alert("Invalid JSON format: " + err.message);
    }
  };

  return (
    <div className="space-y-4 animate-fade-in">
      <BannerCard
        icon={Code2}
        title="JSON Payload Editor"
        description="Edit the search structure directly. Ensure valid JSON format."
        contentClassName="p-0 relative group"
      >
        <textarea
          value={jsonString}
          onChange={handleTextChange}
          rows={16}
          spellCheck={false}
          className="w-full p-6 bg-background text-primary font-mono text-sm leading-relaxed border-none focus:ring-0 focus:outline-none resize-none selection:bg-primary/10"
        />
      </BannerCard>
      
      <ActionBar 
        onClick={handleSubmit} 
        loading={loading} 
        label="Execute JSON Query"
        className="mt-2"
      />
    </div>
  );
}

export default JsonQuery;

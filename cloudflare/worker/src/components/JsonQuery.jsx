import React, { useState, useEffect } from 'react';
import BannerCard from './BannerCard';
import ActionBar from './ActionBar';
import { Button } from "@/components/ui/button";
import { Search, Code2 } from "lucide-react";

function JsonQuery({ 
    recordFilters, 
    oierFilters, 
    onFiltersChange, 
    onSearch,
    limit,
    loading
}) {
  const [jsonString, setJsonString] = useState('');

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
      const parsed = JSON.parse(newJsonString);
      const newRecords = Array.isArray(parsed.record_filters) ? parsed.record_filters : [{}];
      const newOier = typeof parsed.oier_filters === 'object' && parsed.oier_filters !== null ? parsed.oier_filters : {};
      onFiltersChange(newRecords, newOier);
    } catch (error) {
      // Allow invalid JSON while typing
    }
  };

  const handleSubmit = (e) => {
    if (e) e.preventDefault();
    try {
        const parsed = JSON.parse(jsonString);
        onSearch(parsed.record_filters || [], parsed.oier_filters || {});
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

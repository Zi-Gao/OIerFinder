import React, { useState } from 'react';
import RecordFilter from './RecordFilter';
import BannerCard from './BannerCard';
import ActionBar from './ActionBar';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { 
  Select, 
  SelectContent, 
  SelectItem, 
  SelectTrigger, 
  SelectValue 
} from "@/components/ui/select";
import { PlusCircle, Settings2, User, Trophy } from "lucide-react";

function QueryBuilder({ 
    recordFilters, 
    oierFilters, 
    onRecordFiltersChange, 
    onOierFiltersChange, 
    onSearch,
    loading
}) {
  const [showAdvancedOier, setShowAdvancedOier] = useState(false);

  const addFilter = () => onRecordFiltersChange([...recordFilters, {}]);
  const removeFilter = (index) => onRecordFiltersChange(recordFilters.filter((_, i) => i !== index));
  const updateRecordFilter = (index, newFilter) => {
    const newFilters = [...recordFilters];
    newFilters[index] = newFilter;
    onRecordFiltersChange(newFilters);
  };
  
  const handleOierFilterChange = (name, value) => {
    onOierFiltersChange(prev => ({ ...prev, [name]: value }));
  };

  const handleLocalSearch = () => {
    onSearch(recordFilters, oierFilters);
  };

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Record Conditions Card */}
      <BannerCard
        icon={Trophy}
        title="Record Conditions"
        description="OIer must satisfy ALL award records listed below."
        action={
          <Button 
            variant="outline" 
            size="sm" 
            onClick={addFilter}
            className="h-8 gap-1.5 text-xs bg-background shadow-sm hover:shadow-md transition-all border-muted/50 font-bold"
          >
            <PlusCircle className="size-3.5" />
            Add Record
          </Button>
        }
      >
        <div className="space-y-4">
          {recordFilters.map((filter, index) => (
            <RecordFilter
              key={index}
              filter={filter}
              onChange={(newFilter) => updateRecordFilter(index, newFilter)}
              onRemove={() => removeFilter(index)}
            />
          ))}
          {recordFilters.length === 0 && (
            <div className="border border-dashed border-muted-foreground/30 rounded-xl py-12 flex flex-col items-center justify-center bg-muted/5">
              <p className="text-xs text-muted-foreground mb-3 font-semibold uppercase tracking-wider opacity-60">No records added</p>
              <Button variant="outline" size="sm" onClick={addFilter} className="h-8 text-xs gap-1.5 shadow-sm border-muted/50">
                <PlusCircle className="size-3.5" />
                Add First Condition
              </Button>
            </div>
          )}
        </div>
      </BannerCard>

      {/* OIer Conditions Card */}
      <BannerCard
        icon={User}
        title="OIer Conditions"
        description="Filter by programmer initials, gender, and enrollment."
      >
        <div className="space-y-6">
          <div className="flex flex-col sm:flex-row gap-4 items-end">
            <div className="flex-grow space-y-2 w-full">
              <Label htmlFor="initials" className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/80 ml-1">Initials</Label>
              <Input
                id="initials"
                placeholder="e.g., QZH, DMY"
                value={oierFilters.initials || ''}
                onChange={(e) => handleOierFilterChange('initials', e.target.value)}
                className="bg-muted/5 h-10 border-muted/40 text-sm shadow-sm"
              />
            </div>
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={() => setShowAdvancedOier(!showAdvancedOier)}
              className="h-10 text-primary hover:text-primary hover:bg-primary/5 gap-1.5 text-xs font-bold uppercase tracking-widest flex-shrink-0"
            >
              <Settings2 className="size-3.5" />
              {showAdvancedOier ? 'Hide Advanced' : 'Show Advanced'}
            </Button>
          </div>

          {showAdvancedOier && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-5 pt-4 border-t border-muted/20 animate-fade-in">
              <div className="space-y-2">
                <Label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/80">Gender</Label>
                <Select 
                  value={oierFilters.gender || 'any'} 
                  onValueChange={(val) => handleOierFilterChange('gender', val === 'any' ? '' : val)}
                >
                  <SelectTrigger className="bg-muted/10 h-10 border-muted/40 text-sm shadow-sm">
                    <SelectValue placeholder="Any" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="any">Any</SelectItem>
                    <SelectItem value="1">Male</SelectItem>
                    <SelectItem value="-1">Female</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="sm:col-span-2 space-y-2">
                <Label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/80">Enrollment Year</Label>
                <div className="grid grid-cols-2 gap-3">
                  <Input 
                    type="number" 
                    placeholder="From" 
                    value={oierFilters.enroll_min ?? ''}
                    onChange={(e) => handleOierFilterChange('enroll_min', e.target.value)}
                    className="bg-muted/5 h-10 border-muted/40 text-sm shadow-sm"
                  />
                  <Input 
                    type="number" 
                    placeholder="To" 
                    value={oierFilters.enroll_max ?? ''}
                    onChange={(e) => handleOierFilterChange('enroll_max', e.target.value)}
                    className="bg-muted/5 h-10 border-muted/40 text-sm shadow-sm"
                  />
                </div>
              </div>
            </div>
          )}
        </div>
      </BannerCard>

      {/* Action Footer */}
      <ActionBar 
        onClick={handleLocalSearch} 
        loading={loading} 
        label="Execute Search"
        className="mt-2"
      />
    </div>
  );
}

export default QueryBuilder;

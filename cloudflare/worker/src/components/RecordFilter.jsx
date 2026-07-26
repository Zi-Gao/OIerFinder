import React, { useState } from 'react';
import { Card, CardContent } from "@/components/ui/card";
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
import { X, ChevronDown, ChevronUp, Trophy, Calendar, MapPin, Hash, GraduationCap } from "lucide-react";

const CONTEST_TYPES = ["CSP入门", "CSP提高", "NOIP普及", "NOIP提高", "NOIP", "WC", "NOID类", "NOI", "APIO", "CTSC"];
const LEVELS = ["金牌", "银牌", "铜牌", "一等奖", "二等奖", "三等奖"];

function RecordFilter({ filter, onChange, onRemove }) {
  const [showAdvanced, setShowAdvanced] = useState(false);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    onChange({ ...filter, [name]: value });
  };

  const handleSelectChange = (name, value) => {
    onChange({ ...filter, [name]: value === 'any' ? '' : value });
  };

  const handleSemesterChange = (value) => {
    const nextFilter = { ...filter };
    if (value === 'any') {
      delete nextFilter.fall_semester;
    } else {
      nextFilter.fall_semester = value === 'fall';
    }
    onChange(nextFilter);
  };
  
  const toggleAdvanced = () => {
    setShowAdvanced((current) => !current);
  };

  return (
    <Card className="relative border-muted/50 shadow-sm hover:border-primary/20 transition-all duration-200 py-6 overflow-visible">
      <Button 
        variant="outline" 
        size="icon" 
        onClick={onRemove}
        className="absolute -top-3 -right-3 size-8 rounded-full bg-background shadow-md text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-all border border-muted/50 z-50 active:scale-90"
      >
        <X className="size-4" />
      </Button>

      <CardContent className="pt-2 pb-2 space-y-6">

        {/* Basic Fields */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
          <div className="space-y-2">
            <Label className="flex items-center gap-2 text-xs font-bold uppercase text-muted-foreground tracking-tight">
              <Trophy className="size-3.5" />
              Contest Type
            </Label>
            <Select 
              value={filter.contest_type || 'any'} 
              onValueChange={(val) => handleSelectChange('contest_type', val)}
            >
              <SelectTrigger className="bg-muted/30 h-10">
                <SelectValue placeholder="Any" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="any">Any</SelectItem>
                {CONTEST_TYPES.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label className="flex items-center gap-2 text-xs font-bold uppercase text-muted-foreground tracking-tight">
              <Trophy className="size-3.5" />
              Level
            </Label>
            <Select 
              value={filter.level || 'any'} 
              onValueChange={(val) => handleSelectChange('level', val)}
            >
              <SelectTrigger className="bg-muted/30 h-10">
                <SelectValue placeholder="Any" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="any">Any</SelectItem>
                {LEVELS.map(l => <SelectItem key={l} value={l}>{l}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label className="flex items-center gap-2 text-xs font-bold uppercase text-muted-foreground tracking-tight">
              <Calendar className="size-3.5" />
              Year
            </Label>
            <Input 
              type="number" 
              name="year" 
              placeholder="e.g., 2023" 
              value={filter.year ?? ''}
              onChange={handleInputChange} 
              className="bg-muted/30 h-10"
            />
          </div>
        </div>
        
        {/* Advanced Toggle */}
        <div className="flex justify-center -my-1">
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={toggleAdvanced}
            className="h-8 text-xs font-bold uppercase tracking-widest text-muted-foreground/60 hover:text-primary gap-1.5"
          >
            {showAdvanced ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
            {showAdvanced ? 'Hide Options' : 'More Options'}
          </Button>
        </div>

        {/* Advanced Fields */}
        {showAdvanced && (
          <div className="pt-6 border-t border-muted/50 space-y-8 animate-fade-in">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-8 gap-y-6">
              
              <div className="sm:col-span-2 space-y-2">
                <Label className="flex items-center gap-2 text-[10px] uppercase tracking-widest font-black text-muted-foreground/70">
                  <Calendar className="size-3" />
                  Year Range
                </Label>
                <div className="grid grid-cols-2 gap-4 items-center">
                  <Input type="number" name="year_start" placeholder="From" value={filter.year_start ?? ''} onChange={handleInputChange} className="bg-muted/20 h-10 text-sm" />
                  <Input type="number" name="year_end" placeholder="To" value={filter.year_end ?? ''} onChange={handleInputChange} className="bg-muted/20 h-10 text-sm" />
                </div>
              </div>

              <div className="space-y-2">
                <Label className="flex items-center gap-2 text-[10px] uppercase tracking-widest font-black text-muted-foreground/70">
                  <MapPin className="size-3" />
                  Provinces
                </Label>
                <Input type="text" name="provinces" placeholder="北京, 上海..." value={filter.provinces || ''} onChange={handleInputChange} className="bg-muted/20 h-10 text-sm" />
              </div>

              <div className="space-y-2">
                <Label className="flex items-center gap-2 text-[10px] uppercase tracking-widest font-black text-muted-foreground/70">
                  <Hash className="size-3" />
                  Score Range
                </Label>
                <div className="grid grid-cols-2 gap-3">
                  <Input type="number" name="min_score" placeholder="Min" value={filter.min_score ?? ''} onChange={handleInputChange} className="bg-muted/20 h-10 text-sm" />
                  <Input type="number" name="max_score" placeholder="Max" value={filter.max_score ?? ''} onChange={handleInputChange} className="bg-muted/20 h-10 text-sm" />
                </div>
              </div>
              
              <div className="space-y-2">
                <Label className="flex items-center gap-2 text-[10px] uppercase tracking-widest font-black text-muted-foreground/70">
                  <Hash className="size-3" />
                  Rank Range
                </Label>
                <div className="grid grid-cols-2 gap-3">
                  <Input type="number" name="min_rank" placeholder="Min" value={filter.min_rank ?? ''} onChange={handleInputChange} className="bg-muted/20 h-10 text-sm" />
                  <Input type="number" name="max_rank" placeholder="Max" value={filter.max_rank ?? ''} onChange={handleInputChange} className="bg-muted/20 h-10 text-sm" />
                </div>
              </div>

              <div className="space-y-2">
                <Label className="flex items-center gap-2 text-[10px] uppercase tracking-widest font-black text-muted-foreground/70">
                  <GraduationCap className="size-3" />
                  Academic Term
                </Label>
                <Select
                  value={
                    filter.fall_semester === true
                      ? 'fall'
                      : filter.fall_semester === false
                        ? 'non-fall'
                        : 'any'
                  }
                  onValueChange={handleSemesterChange}
                >
                  <SelectTrigger className="bg-muted/20 h-10 text-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="any">Any term</SelectItem>
                    <SelectItem value="fall">Fall term (new school year)</SelectItem>
                    <SelectItem value="non-fall">Non-fall term (previous school year)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-4">
              <div className="space-y-2">
                <Label className="flex items-center gap-2 text-[10px] uppercase tracking-widest font-black text-muted-foreground/70">
                  <Calendar className="size-3" />
                  Specific Years List
                </Label>
                <Input type="text" name="years" placeholder="2020, 2022... (Overrides range)" value={filter.years || ''} onChange={handleInputChange} className="bg-muted/20 h-10 text-sm" />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <Label className="text-[10px] uppercase tracking-widest font-black text-muted-foreground/70">Contest IDs</Label>
                  <Input type="text" name="contest_ids" placeholder="101, 102..." value={filter.contest_ids || ''} onChange={handleInputChange} className="bg-muted/20 h-10 text-sm" />
                </div>
                <div className="space-y-2">
                  <Label className="text-[10px] uppercase tracking-widest font-black text-muted-foreground/70">School IDs</Label>
                  <Input type="text" name="school_ids" placeholder="233, 234..." value={filter.school_ids || ''} onChange={handleInputChange} className="bg-muted/20 h-10 text-sm" />
                </div>
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default RecordFilter;

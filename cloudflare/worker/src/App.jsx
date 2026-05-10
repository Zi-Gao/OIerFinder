import React, { useState, useEffect } from 'react';
import QueryBuilder from './components/QueryBuilder';
import JsonQuery from './components/JsonQuery';
import LuoguQuery from './components/LuoguQuery';
import ResultsDisplay from './components/ResultsDisplay';
import { searchOiers } from './api/client';
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Toaster } from "@/components/ui/sonner";
import { toast } from "sonner";
import { LayoutGrid, Braces, UserCircle } from "lucide-react";

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

  // --- 核心搜索函数 ---
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

    const payload = {
      record_filters: processedRecordFilters,
      oier_filters: processedOierFilters,
      limit: Number(limit) || 10
    };

    try {
      const data = await searchOiers(payload, adminSecret);
      setResults(data);
      if (data.data.length === 0) {
        toast.info("No results found.");
      } else {
        toast.success(`Found ${data.data.length} results.`);
      }
    } catch (err) {
      setError(err.message);
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleLuoguQueryImport = (queryPayload) => {
    setRecordFilters(queryPayload.record_filters || [{}]);
    setOierFilters(queryPayload.oier_filters || {});
    setActiveTab(TABS.BUILDER);
    toast.success("Query imported from Luogu.");
  };

  return (
    <div className="min-h-screen bg-background font-sans antialiased">
      <div className="container mx-auto py-10 px-4 md:px-8 max-w-7xl">
        <header className="flex flex-col items-center mb-12 space-y-2">
          <h1 className="text-5xl font-extrabold tracking-tight lg:text-6xl bg-clip-text text-transparent bg-gradient-to-b from-foreground to-foreground/70">
            OIer Finder
          </h1>
          <p className="text-xl text-muted-foreground font-medium">
            Search for competitive programmers with precision.
          </p>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Sidebar */}
          <aside className="lg:col-span-3 space-y-6">
            <Card className="shadow-sm border-muted/50">
              <CardHeader className="pb-4">
                <CardTitle className="text-lg font-semibold tracking-tight">Settings</CardTitle>
                <CardDescription>Global configuration for search.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="admin-secret" className="text-xs font-bold uppercase tracking-wider text-muted-foreground/80">Admin Secret</Label>
                  <Input
                    id="admin-secret"
                    type="password"
                    value={adminSecret}
                    onChange={(e) => setAdminSecret(e.target.value)}
                    placeholder="X-Admin-Secret"
                    className="bg-muted/20 border-muted/40 h-9"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="global-limit" className="text-xs font-bold uppercase tracking-wider text-muted-foreground/80">Result Limit</Label>
                  <Input
                    id="global-limit"
                    type="number"
                    value={limit}
                    onChange={(e) => setLimit(Number(e.target.value) || 0)}
                    className="bg-muted/20 border-muted/40 h-9"
                  />
                </div>
              </CardContent>
            </Card>
          </aside>

          {/* Main Area */}
          <main className="lg:col-span-9 space-y-8">
            <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
              <TabsList className="!w-full !h-12 p-1 bg-muted/40 border border-muted/40 flex items-center justify-between rounded-2xl mb-2 shadow-sm">
                <TabsTrigger 
                  value={TABS.BUILDER} 
                  className="flex-1 !h-full rounded-xl data-[state=active]:bg-background data-[state=active]:shadow-sm data-[state=active]:text-primary transition-all duration-300 flex items-center justify-center gap-2 group border-none"
                >
                  <LayoutGrid className="size-4 opacity-50 group-data-[state=active]:opacity-100 group-data-[state=active]:scale-110 transition-transform" />
                  <span className="font-extrabold tracking-tight">{TABS.BUILDER}</span>
                </TabsTrigger>
                <TabsTrigger 
                  value={TABS.JSON} 
                  className="flex-1 !h-full rounded-xl data-[state=active]:bg-background data-[state=active]:shadow-sm data-[state=active]:text-primary transition-all duration-300 flex items-center justify-center gap-2 group border-none"
                >
                  <Braces className="size-4 opacity-50 group-data-[state=active]:opacity-100 group-data-[state=active]:scale-110 transition-transform" />
                  <span className="font-extrabold tracking-tight">{TABS.JSON}</span>
                </TabsTrigger>
                <TabsTrigger 
                  value={TABS.LUOGU} 
                  className="flex-1 !h-full rounded-xl data-[state=active]:bg-background data-[state=active]:shadow-sm data-[state=active]:text-primary transition-all duration-300 flex items-center justify-center gap-2 group border-none"
                >
                  <UserCircle className="size-4 opacity-50 group-data-[state=active]:opacity-100 group-data-[state=active]:scale-110 transition-transform" />
                  <span className="font-extrabold tracking-tight">{TABS.LUOGU}</span>
                </TabsTrigger>
              </TabsList>

              <TabsContent value={TABS.BUILDER} className="mt-0 ring-offset-background focus-visible:outline-none">
                <QueryBuilder 
                  recordFilters={recordFilters}
                  oierFilters={oierFilters}
                  onRecordFiltersChange={setRecordFilters}
                  onOierFiltersChange={setOierFilters}
                  onSearch={handleSearch}
                  loading={loading}
                />
              </TabsContent>

              <TabsContent value={TABS.JSON} className="mt-0 ring-offset-background focus-visible:outline-none">
                <JsonQuery
                  recordFilters={recordFilters}
                  oierFilters={oierFilters}
                  limit={limit}
                  onFiltersChange={(newRecords, newOier) => {
                    setRecordFilters(newRecords);
                    setOierFilters(newOier);
                  }}
                  onSearch={handleSearch}
                  loading={loading}
                />
              </TabsContent>

              <TabsContent value={TABS.LUOGU} className="mt-0 ring-offset-background focus-visible:outline-none">
                <LuoguQuery 
                  adminSecret={adminSecret} 
                  onImportQuery={handleLuoguQueryImport} 
                />
              </TabsContent>
            </Tabs>

            <ResultsDisplay results={results} error={error} loading={loading} />
          </main>
        </div>
      </div>
      <Toaster position="top-right" richColors />
    </div>
  );
}

export default App;

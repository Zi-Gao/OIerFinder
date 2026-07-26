import React, { useState, useEffect } from 'react';
import QueryBuilder from './components/QueryBuilder';
import JsonQuery from './components/JsonQuery';
import LuoguQuery from './components/LuoguQuery';
import ResultsDisplay from './components/ResultsDisplay';
import VersionBadge from './components/VersionBadge';
import { getVersionInfo, searchOiers } from './api/client';
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Toaster } from "@/components/ui/sonner";
import { toast } from "sonner";
import { useTheme } from "next-themes";
import { LayoutGrid, Braces, UserCircle, BookOpen, Code2, ExternalLink, Moon, Sun, Settings2 } from "lucide-react";
import logo from './logo.svg';
import BannerCard from './components/BannerCard';
import InteractiveBackground from './components/InteractiveBackground';

const TABS = {
  BUILDER: 'UI Builder',
  JSON: 'Raw JSON',
  LUOGU: 'Luogu UID',
};

// 辅助函数：清理过滤器中的空值
const cleanObject = (obj) => {
    if (typeof obj !== 'object' || obj === null || Array.isArray(obj)) {
      throw new Error('Each filter must be a JSON object.');
    }
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
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const [versionInfo, setVersionInfo] = useState(null);

  // --- 共享的查询状态 ---
  const [recordFilters, setRecordFilters] = useState([{}]);
  const [oierFilters, setOierFilters] = useState({});

  // --- 共享的结果状态 ---
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // --- 全局设置状态 ---
  const [adminSecret, setAdminSecret] = useState('');
  const [limit, setLimit] = useState(() => {
    const storedLimit = Number.parseInt(
      localStorage.getItem('oierFinderLimit'),
      10,
    );
    return Number.isFinite(storedLimit) && storedLimit > 0
      ? Math.min(storedLimit, 100)
      : 10;
  });

  useEffect(() => {
    // Secrets are intentionally kept in memory only. Remove values persisted by
    // older versions of the UI.
    localStorage.removeItem('oierFinderAdminSecret');
    setMounted(true);
  }, []);

  useEffect(() => {
    localStorage.setItem('oierFinderLimit', limit);
  }, [limit]);

  useEffect(() => {
    let cancelled = false;

    getVersionInfo()
      .then((data) => {
        if (!cancelled) setVersionInfo(data);
      })
      .catch(() => {
        if (!cancelled) setVersionInfo({});
      });

    return () => {
      cancelled = true;
    };
  }, []);

  // --- 核心搜索函数 ---
  const handleSearch = async (currentRecordFilters, currentOierFilters, currentLimit = limit) => {
    setLoading(true);
    setError('');
    setResults(null);

    try {
      if (!Array.isArray(currentRecordFilters)) {
        throw new Error("'record_filters' must be an array.");
      }

      const stringToArray = (str) => str.split(',').map(item => item.trim()).filter(Boolean);
      const stringToNumberArray = (str, fieldName) => {
        const values = stringToArray(str).map(Number);
        if (values.some(value => !Number.isFinite(value))) {
          throw new Error(`All values in '${fieldName}' must be numbers.`);
        }
        return values;
      };

      const processedRecordFilters = currentRecordFilters
        .map(f => {
          const cleaned = cleanObject(f);
          if (cleaned.provinces && typeof cleaned.provinces === 'string') cleaned.provinces = stringToArray(cleaned.provinces);
          if (cleaned.years && typeof cleaned.years === 'string') cleaned.years = stringToNumberArray(cleaned.years, 'years');
          if (cleaned.contest_ids && typeof cleaned.contest_ids === 'string') cleaned.contest_ids = stringToNumberArray(cleaned.contest_ids, 'contest_ids');
          if (cleaned.school_ids && typeof cleaned.school_ids === 'string') cleaned.school_ids = stringToNumberArray(cleaned.school_ids, 'school_ids');
          return cleaned;
        })
        .filter(f => Object.keys(f).length > 0);

      const processedOierFilters = cleanObject(currentOierFilters);
      if (processedOierFilters.initials && typeof processedOierFilters.initials === 'string') {
          processedOierFilters.initials = stringToArray(processedOierFilters.initials);
      }

      const requestedLimit = Number(currentLimit);
      if (!Number.isFinite(requestedLimit) || requestedLimit <= 0) {
        throw new Error("'limit' must be a positive number.");
      }

      const payload = {
        record_filters: processedRecordFilters,
        oier_filters: processedOierFilters,
        limit: Math.min(Math.floor(requestedLimit), 100)
      };

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
    <div className="min-h-screen bg-background font-sans antialiased selection:bg-primary/10 text-foreground relative overflow-hidden flex flex-col">
      {/* Dynamic Interactive Background */}
      <InteractiveBackground />

      <div className="container mx-auto py-16 px-4 md:px-8 max-w-7xl relative z-10 flex-grow">
        <header className="flex flex-col items-center mb-16 animate-fade-in">
          <div className="flex items-center gap-6">
            <div className="size-20 relative group transition-transform hover:-rotate-3 duration-300">
              <img src={logo} alt="OIerFinder Logo" className="w-full h-full bg-white shadow-2xl rounded-2xl border border-slate-200/50" />
            </div>
            <div className="flex flex-col">
              <h1 className="text-5xl md:text-6xl font-black tracking-tighter text-slate-950 dark:text-slate-50">
                OIer<span className="text-primary italic">Finder</span>
              </h1>
            </div>
          </div>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-start">
          {/* Sidebar */}
          <aside className="lg:col-span-3 space-y-6">
            <BannerCard
              icon={Settings2}
              title="Settings"
              description="Global configuration for search."
            >
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="admin-secret" className="text-[10px] font-black uppercase tracking-wider text-muted-foreground/60 ml-1">Admin Secret</Label>
                  <Input
                    id="admin-secret"
                    type="password"
                    value={adminSecret}
                    onChange={(e) => setAdminSecret(e.target.value)}
                    placeholder="X-Admin-Secret"
                    className="bg-muted/5 border-muted/40 h-10 shadow-sm focus:bg-background transition-colors"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="global-limit" className="text-[10px] font-black uppercase tracking-wider text-muted-foreground/60 ml-1">Result Limit</Label>
                  <Input
                    id="global-limit"
                    type="number"
                    value={limit}
                    onChange={(e) => setLimit(Number(e.target.value) || 0)}
                    className="bg-muted/5 border-muted/40 h-10 shadow-sm focus:bg-background transition-colors"
                  />
                </div>
                {mounted && (
                  <div className="flex items-center justify-between pt-2 border-t border-muted/20">
                    <div className="flex flex-col gap-1">
                      <Label className="text-[10px] font-black uppercase tracking-wider text-muted-foreground/60 ml-1">Dark Mode</Label>
                      <span className="text-[10px] text-muted-foreground/40 ml-1">Toggle theme preference</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Sun className="size-3 text-muted-foreground/60" />
                      <Switch 
                        checked={theme === 'dark'} 
                        onCheckedChange={(checked) => setTheme(checked ? 'dark' : 'light')} 
                      />
                      <Moon className="size-3 text-muted-foreground/60" />
                    </div>
                  </div>
                )}
              </div>
            </BannerCard>
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
                  onLimitChange={setLimit}
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

      <footer className="relative z-10 border-t border-muted/80 bg-muted/30 backdrop-blur-sm py-16 mt-24">
        <div className="container mx-auto px-4 md:px-8 max-w-7xl">
          <div className="flex flex-col md:flex-row justify-between items-start gap-12">
            <div className="flex flex-col items-center md:items-start gap-4">
              <div className="flex items-center gap-2.5 group cursor-default">
                <div className="size-8 relative group-hover:rotate-6 transition-transform">
                  <img src={logo} alt="OIerFinder Logo" className="w-full h-full bg-white shadow-lg rounded-md border border-slate-200/50" />
                </div>
                <span className="text-lg font-black tracking-tighter text-slate-950 dark:text-slate-50">
                  OIer<span className="text-primary italic">Finder</span>
                </span>
              </div>
              <div className="flex flex-col gap-2 max-w-md">
                <p className="text-[11px] text-slate-600 dark:text-slate-400 font-bold uppercase tracking-widest flex items-center gap-2">
                  <span className="size-1.5 rounded-full bg-primary" />
                  Professional Search Infrastructure
                </p>
                <p className="text-xs text-muted-foreground/70 font-medium leading-relaxed">
                  Fully powered by Cloudflare serverless edge and D1 database. All data is aggregated from public records, ensuring extreme performance and low-latency precision for the competitive programming community.
                </p>
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-x-12 gap-y-6 w-full md:w-auto">
              <div className="flex flex-col gap-3">
                <span className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400 dark:text-slate-500">Resources</span>
                <a
                  href="/docs"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 text-xs font-bold text-muted-foreground hover:text-primary transition-colors group"
                >
                  <BookOpen className="size-4 opacity-60 group-hover:opacity-100" />
                  API Documentation
                </a>
                <a 
                  href="https://github.com/Zi-Gao/OIerFinder" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 text-xs font-bold text-muted-foreground hover:text-primary transition-colors group"
                >
                  <Code2 className="size-4 opacity-60 group-hover:opacity-100" />
                  GitHub Source
                </a>
              </div>
              <div className="flex flex-col gap-3">
                <span className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400 dark:text-slate-500">Data Source</span>
                <a 
                  href="https://oier.baoshuo.dev/" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 text-xs font-bold text-muted-foreground hover:text-primary transition-colors group"
                >
                  <ExternalLink className="size-4 opacity-60 group-hover:opacity-100" />
                  OIerDB (Baoshuo)
                </a>
              </div>
            </div>
          </div>
          
          <div className="mt-12 pt-8 border-t border-muted/30 flex flex-col md:flex-row justify-between items-center gap-4">
            <p className="text-[10px] text-muted-foreground/50 font-medium uppercase tracking-[0.2em]">
              © {new Date().getFullYear()} OIerFinder Engine. No rights reserved.
            </p>
            <div className="flex flex-wrap items-center justify-center gap-2">
              <VersionBadge
                label="OIerFinder"
                sha={versionInfo?.oierfinder_sha}
                repositoryUrl="https://github.com/Zi-Gao/OIerFinder"
              />
              <VersionBadge
                label="OIerDB-data"
                sha={versionInfo?.oierdb_data_sha}
                repositoryUrl="https://github.com/OIerDb-ng/OIerDb-data-generator"
              />
            </div>
          </div>
        </div>
      </footer>
      <Toaster position="top-right" richColors />
    </div>
  );
}

export default App;

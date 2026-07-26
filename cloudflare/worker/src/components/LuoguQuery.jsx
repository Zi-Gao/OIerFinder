import React, { useState } from 'react';
import { getLuoguPrizes } from '../api/client';
import BannerCard from './BannerCard';
import ActionBar from './ActionBar';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from "@/components/ui/table";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Search, Import, AlertCircle, UserSearch, Download } from "lucide-react";
import { toast } from "sonner";

function LuoguQuery({ adminSecret, onImportQuery }) {
  const [uid, setUid] = useState('');
  const [prizes, setPrizes] = useState(null);
  const [queryPayload, setQueryPayload] = useState(null);
  const [loading, setLoading] = useState({ prizes: false, import: false });
  const [error, setError] = useState('');

  const handleFetchPrizes = async () => {
    if (!uid) {
      toast.error('Please enter a Luogu UID.');
      return;
    }
    setLoading(current => ({ ...current, prizes: true }));
    setError('');
    setPrizes(null);
    setQueryPayload(null);
    try {
      const data = await getLuoguPrizes(uid, adminSecret);
      setPrizes(data.prizes);
      setQueryPayload(data.query_payload);
      if (data.synced) {
        toast.success(`Fetched ${data.prizes.length} awards from Luogu.`);
      } else {
        toast.info(`Showing ${data.prizes.length} historical records (Luogu sync failed).`);
      }
    } catch (err) {
      setError(err.message);
      toast.error("Failed to fetch awards.");
    } finally {
      setLoading(current => ({ ...current, prizes: false }));
    }
  };

  const handleImport = () => {
    if (!queryPayload) {
      toast.error("No query payload is available. Fetch awards again.");
      return;
    }
    setLoading(current => ({ ...current, import: true }));
    setError('');
    try {
      onImportQuery(queryPayload);
    } catch (err) {
      setError(err.message);
      toast.error("Failed to import query.");
    } finally {
      setLoading(current => ({ ...current, import: false }));
    }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <BannerCard
        icon={UserSearch}
        title="Luogu UID Import"
        description="Fetch user awards from Luogu and generate a query payload automatically."
      >
        <div className="space-y-6">
          <div className="flex flex-col sm:flex-row gap-4 items-end">
            <div className="flex-grow space-y-2">
              <Label htmlFor="luogu-uid" className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/80 ml-1">Luogu User ID</Label>
              <div className="relative">
                <Search className="absolute left-3 top-3 size-4 text-muted-foreground opacity-50" />
                <Input
                  id="luogu-uid"
                  type="text"
                  value={uid}
                  onChange={(e) => {
                    setUid(e.target.value);
                    setPrizes(null);
                    setQueryPayload(null);
                    setError('');
                  }}
                  placeholder="e.g., 2"
                  className="pl-10 bg-muted/5 h-10 border-muted/40 text-sm shadow-sm"
                />
              </div>
            </div>

            <ActionBar 
              onClick={handleFetchPrizes} 
              loading={loading.prizes} 
              label="Fetch Awards" 
              icon={Download}
              className="pt-0 flex-shrink-0"
            />
          </div>

          {error && (
            <Alert variant="destructive" className="bg-destructive/5 border-destructive/20 text-destructive rounded-xl">
              <AlertCircle className="size-4" />
              <AlertTitle className="font-bold">Error</AlertTitle>
              <AlertDescription className="text-xs">{error}</AlertDescription>
            </Alert>
          )}

          {prizes && (
            <div className="border border-muted/40 rounded-2xl overflow-hidden shadow-sm bg-background">
              <div className="bg-muted/30 border-b border-muted/30 py-3 px-6 flex items-center justify-between">
                <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/80">
                  Awards Records List
                </span>
                <Badge variant="outline" className="bg-background text-primary border-muted/50 font-bold text-[9px] px-2.5">
                  {prizes.length} ITEMS
                </Badge>
              </div>
              
              <div className="max-h-[300px] overflow-y-auto">
                <Table>
                  <TableHeader className="bg-muted/10 sticky top-0 z-10">
                    <TableRow className="hover:bg-transparent border-muted/30">
                      <TableHead className="w-[100px] px-6 py-3 text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70">Year</TableHead>
                      <TableHead className="px-6 py-3 text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70">Contest</TableHead>
                      <TableHead className="px-6 py-3 text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70">Prize</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {prizes.map((p, i) => (
                      <TableRow key={i} className="hover:bg-primary/5 transition-colors border-muted/20">
                        <TableCell className="px-6 py-3 font-medium text-xs text-muted-foreground">{p.year ?? 'N/A'}</TableCell>
                        <TableCell className="px-6 py-3 font-bold text-foreground text-sm">{p.contest_name}</TableCell>
                        <TableCell className="px-6 py-3">
                          {p.is_noi_series ? (
                            <Badge variant="secondary" className="bg-primary/10 text-primary border-none font-bold text-[10px] px-2 py-0 h-5">
                              {p.prize_level}
                            </Badge>
                          ) : (
                            <span className="text-xs text-muted-foreground">{p.prize_level}</span>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              <div className="p-4 bg-muted/10 border-t border-muted/30">
                <Button 
                  onClick={handleImport} 
                  disabled={loading.import} 
                  variant="secondary"
                  className="w-full h-10 gap-2 shadow-sm border border-muted/40 font-black uppercase text-[10px] tracking-widest bg-background hover:bg-muted/50"
                >
                  {loading.import ? (
                    <span className="size-4 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
                  ) : (
                    <Import className="size-4" />
                  )}
                  Import Selection to Query Builder
                </Button>
              </div>
            </div>
          )}
        </div>
      </BannerCard>
    </div>
  );
}
export default LuoguQuery;

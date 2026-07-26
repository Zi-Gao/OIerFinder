import React from 'react';
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from "@/components/ui/table";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import BannerCard from './BannerCard';
import { ExternalLink, AlertCircle, Info, Database, Users } from "lucide-react";

function ResultsDisplay({ results, error, loading }) {
  if (loading) {
    return (
      <div className="space-y-4 animate-pulse">
        <Skeleton className="h-8 w-48" />
        <Card className="border-muted shadow-sm">
          <CardContent className="p-0">
            <div className="space-y-2 p-4">
              {[...Array(5)].map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive" className="bg-destructive/5 border-destructive/20 text-destructive animate-fade-in rounded-2xl">
        <AlertCircle className="size-4" />
        <AlertTitle className="font-bold">Search Error</AlertTitle>
        <AlertDescription className="text-sm">{error}</AlertDescription>
      </Alert>
    );
  }
  
  if (!results) return null;

  const formatGender = (gender) => {
    switch (gender) {
      case 1:
        return <Badge variant="secondary" className="bg-blue-50 text-blue-700 hover:bg-blue-50 border-none px-2 py-0 h-5 text-[10px] font-bold">Male</Badge>;
      case -1:
        return <Badge variant="secondary" className="bg-pink-50 text-pink-700 hover:bg-pink-50 border-none px-2 py-0 h-5 text-[10px] font-bold">Female</Badge>;
      default:
        return <Badge variant="outline" className="text-muted-foreground border-muted px-2 py-0 h-5 text-[10px] font-bold">N/A</Badge>;
    }
  };

  const formatCCFLevel = (level) => {
    if (level === null || level === undefined || level === '') {
      return <span className="text-muted-foreground text-xs">—</span>;
    }
    const numLevel = parseInt(level);
    if (isNaN(numLevel)) return level;
    
    let colorClass = "bg-muted/50 text-muted-foreground";
    if (numLevel >= 9) colorClass = "bg-red-50 text-red-700";
    else if (numLevel >= 7) colorClass = "bg-orange-50 text-orange-700";
    else if (numLevel >= 5) colorClass = "bg-blue-50 text-blue-700";
    else if (numLevel >= 3) colorClass = "bg-emerald-50 text-emerald-700";

    return (
      <Badge variant="secondary" className={`${colorClass} hover:${colorClass} border-none font-bold px-2 py-0 h-5 text-[10px]`}>
        Level {level}
      </Badge>
    );
  };

  return (
    <div className="space-y-6 animate-fade-in pt-4">
        <BannerCard
          icon={Users}
          title="Search Results"
          description={`${results.data.length} programmers found matching your criteria.`}
          contentClassName="p-0"
          action={
            <Badge variant="outline" className="bg-background text-primary border-muted/50 font-bold uppercase tracking-widest text-[9px] px-3">
              LIVE DATA
            </Badge>
          }
        >
          <div className="overflow-x-auto">
            <Table>
                <TableHeader className="bg-muted/20">
                    <TableRow className="hover:bg-transparent border-muted/30">
                        <TableHead className="w-[80px] px-6 py-4 font-bold text-[10px] uppercase tracking-wider text-muted-foreground/80">UID</TableHead>
                        <TableHead className="px-6 py-4 font-bold text-[10px] uppercase tracking-wider text-muted-foreground/80">Name</TableHead>
                        <TableHead className="px-6 py-4 font-bold text-[10px] uppercase tracking-wider text-muted-foreground/80">Gender</TableHead>
                        <TableHead className="px-6 py-4 font-bold text-[10px] uppercase tracking-wider text-muted-foreground/80">Enrollment</TableHead>
                        <TableHead className="px-6 py-4 font-bold text-[10px] uppercase tracking-wider text-muted-foreground/80 text-right">OIerDB</TableHead>
                        <TableHead className="px-6 py-4 font-bold text-[10px] uppercase tracking-wider text-muted-foreground/80 text-right">CCF Score</TableHead>
                        <TableHead className="px-6 py-4 font-bold text-[10px] uppercase tracking-wider text-muted-foreground/80 text-center">CCF Level</TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {results.data.map((oier) => (
                        <TableRow key={oier.uid} className="hover:bg-muted/5 transition-colors border-muted/20">
                            <TableCell className="px-6 py-4 font-mono text-[11px] text-muted-foreground">{oier.uid}</TableCell>
                            <TableCell className="px-6 py-4">
                                <a 
                                    href={`https://oier.baoshuo.dev/oier/${oier.uid}`} 
                                    target="_blank" 
                                    rel="noopener noreferrer"
                                    className="flex items-center gap-1.5 font-bold text-primary hover:text-primary/80 transition-colors group text-sm"
                                >
                                    {oier.name}
                                    <ExternalLink className="size-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                                </a>
                            </TableCell>
                            <TableCell className="px-6 py-4">{formatGender(oier.gender)}</TableCell>
                            <TableCell className="px-6 py-4 font-medium text-xs">{oier.enroll_middle ?? 'N/A'}</TableCell>
                            <TableCell className="px-6 py-4 text-right font-mono font-bold text-xs">{oier.oierdb_score}</TableCell>
                            <TableCell className="px-6 py-4 text-right font-mono font-bold text-xs">{oier.ccf_score}</TableCell>
                            <TableCell className="px-6 py-4 text-center">{formatCCFLevel(oier.ccf_level)}</TableCell>
                        </TableRow>
                    ))}
                    {results.data.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={7} className="h-40 text-center text-muted-foreground text-xs italic">
                          No programmers matched your criteria. Try loosening your filters.
                        </TableCell>
                      </TableRow>
                    )}
                </TableBody>
            </Table>
          </div>
        </BannerCard>

        {results.usage && (
          <details className="group bg-muted/20 border border-muted/40 rounded-2xl overflow-hidden transition-all">
              <summary className="flex items-center gap-2 cursor-pointer p-4 font-bold text-[10px] uppercase tracking-widest text-muted-foreground/60 hover:bg-muted/30 select-none">
                  <Database className="size-3.5" />
                  Performance Metrics
                  <Info className="size-3 ml-auto opacity-40" />
              </summary>
              <div className="p-4 pt-0">
                <pre className="text-[10px] bg-background/50 p-4 rounded-xl overflow-x-auto font-mono text-muted-foreground/80 border border-muted/30">
                    <code>{JSON.stringify(results.usage, null, 2)}</code>
                </pre>
              </div>
          </details>
        )}
    </div>
  );
}

export default ResultsDisplay;

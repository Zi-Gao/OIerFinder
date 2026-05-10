import React from 'react';
import { Button } from "@/components/ui/button";
import { Search, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Standardized sleek black action button for primary search triggers.
 */
function ActionBar({ 
  onClick, 
  loading, 
  label = "Execute Search", 
  icon: Icon = Search,
  className 
}) {
  return (
    <div className={cn("flex justify-end", className)}>
      <Button 
        onClick={onClick}
        disabled={loading}
        size="lg"
        className="bg-slate-950 hover:bg-slate-800 text-white px-8 h-10 text-xs font-bold uppercase tracking-wider shadow-md rounded-xl transition-all hover:scale-[1.02] active:scale-95 border-none gap-2"
      >
        {loading ? (
          <Loader2 className="size-4 animate-spin" />
        ) : (
          <Icon className="size-4" />
        )}
        {loading ? "Processing..." : label}
      </Button>
    </div>
  );
}

export default ActionBar;

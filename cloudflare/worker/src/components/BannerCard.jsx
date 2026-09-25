import React from 'react';
import { cn } from "@/lib/utils";

/**
 * Standardized card component with a gray banner header.
 */
function BannerCard({ 
  icon: Icon, 
  title, 
  description, 
  action, 
  children, 
  className,
  contentClassName
}) {
  return (
    <div className={cn("border border-muted/60 shadow-sm overflow-hidden rounded-2xl bg-card text-card-foreground", className)}>
      <div className="bg-muted/30 border-b border-muted/30 px-4 py-3 md:px-5 md:py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-2.5 min-w-0">
          {Icon && <Icon className="size-4.5 text-primary shrink-0" />}
          <div className="space-y-0.5 min-w-0">
            <h3 className="text-base md:text-[17px] font-bold tracking-tight text-foreground leading-none">
              {title}
            </h3>
            {description && (
              <p className="text-xs md:text-sm font-medium text-muted-foreground leading-none mt-0.5">
                {description}
              </p>
            )}
          </div>
        </div>
        {action && <div className="shrink-0 ml-3">{action}</div>}
      </div>
      <div className={cn("p-4 md:p-5", contentClassName)}>
        {children}
      </div>
    </div>
  );
}

export default BannerCard;

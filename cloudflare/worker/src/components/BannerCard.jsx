import React from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
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
    <Card className={cn("!py-0 !gap-0 border-muted/60 shadow-sm overflow-hidden rounded-2xl bg-background", className)}>
      <CardHeader className="bg-muted/30 border-b border-muted/30 py-3 px-4.5 md:px-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            {Icon && <Icon className="size-4.5 text-primary shrink-0" />}
            <div className="space-y-0.5">
              <CardTitle className="text-base md:text-lg font-bold tracking-tight text-foreground leading-none">
                {title}
              </CardTitle>
              {description && (
                <CardDescription className="text-xs font-medium text-muted-foreground leading-none mt-1">
                  {description}
                </CardDescription>
              )}
            </div>
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </div>
      </CardHeader>
      <CardContent className={cn("p-3.5 md:p-4", contentClassName)}>
        {children}
      </CardContent>
    </Card>
  );
}

export default BannerCard;

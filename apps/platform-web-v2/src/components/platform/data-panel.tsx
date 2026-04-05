import type { HTMLAttributes, ReactNode } from "react";

import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils/cn";

export function DataPanel({
  children,
  className,
  description,
  title,
  toolbar,
  ...props
}: HTMLAttributes<HTMLDivElement> & {
  description?: string;
  title: string;
  toolbar?: ReactNode;
}) {
  return (
    <Card className={cn("p-6", className)} {...props}>
      <div className="mb-4 flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <h2 className="text-[2rem] font-semibold tracking-tight text-[var(--foreground)]">{title}</h2>
          {description ? (
            <p className="mt-2 max-w-2xl text-sm leading-7 text-[var(--muted-foreground)]">{description}</p>
          ) : null}
        </div>

        {toolbar ? <div className="flex flex-wrap items-center gap-3">{toolbar}</div> : null}
      </div>

      {children}
    </Card>
  );
}

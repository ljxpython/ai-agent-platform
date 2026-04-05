import type { HTMLAttributes, ReactNode } from "react";

import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils/cn";

type DetailPanelProps = HTMLAttributes<HTMLDivElement> & {
  title: string;
  description?: string;
  eyebrow?: string;
  actions?: ReactNode;
};

export function DetailPanel({
  actions,
  children,
  className,
  description,
  eyebrow,
  title,
  ...props
}: DetailPanelProps) {
  return (
    <Card className={cn("p-6", className)} {...props}>
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          {eyebrow ? (
            <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
              {eyebrow}
            </div>
          ) : null}
          <h3 className="mt-2 text-2xl font-semibold tracking-tight text-[var(--foreground)]">
            {title}
          </h3>
          {description ? (
            <p className="mt-3 max-w-2xl text-sm leading-7 text-[var(--muted-foreground)]">
              {description}
            </p>
          ) : null}
        </div>

        {actions ? (
          <div className="flex flex-wrap items-center gap-3">{actions}</div>
        ) : null}
      </div>

      <div className="mt-6">{children}</div>
    </Card>
  );
}

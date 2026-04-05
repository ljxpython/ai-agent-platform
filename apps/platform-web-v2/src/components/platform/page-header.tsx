import type { ReactNode } from "react";

import { cn } from "@/lib/utils/cn";

export function PageHeader({
  actions,
  description,
  eyebrow,
  title,
}: {
  actions?: ReactNode;
  description: string;
  eyebrow?: string;
  title: string;
}) {
  return (
    <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div>
        {eyebrow ? (
          <div className={cn("text-xs font-bold uppercase tracking-[0.14em]", "text-[var(--muted-foreground)]")}>
            {eyebrow}
          </div>
        ) : null}
        <h1 className="mt-1 text-4xl font-semibold tracking-tight text-[var(--foreground)]">{title}</h1>
        <p className="mt-2 max-w-3xl text-sm leading-7 text-[var(--muted-foreground)]">{description}</p>
      </div>

      {actions ? <div className="flex flex-wrap items-center gap-3">{actions}</div> : null}
    </div>
  );
}

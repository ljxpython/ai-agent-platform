import type { HTMLAttributes, ReactNode } from "react";

import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils/cn";

export function FormSection({
  actions,
  children,
  className,
  description,
  title,
  ...props
}: HTMLAttributes<HTMLDivElement> & {
  actions?: ReactNode;
  description?: string;
  title: string;
}) {
  return (
    <Card className={cn("p-6", className)} {...props}>
      <div className="mb-5 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-[var(--foreground)]">
            {title}
          </h2>
          {description ? (
            <p className="mt-2 max-w-2xl text-sm leading-7 text-[var(--muted-foreground)]">
              {description}
            </p>
          ) : null}
        </div>

        {actions ? (
          <div className="flex flex-wrap items-center gap-3">{actions}</div>
        ) : null}
      </div>

      {children}
    </Card>
  );
}

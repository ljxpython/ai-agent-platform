import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils/cn";

export function PageActions({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("flex flex-wrap items-center gap-3", className)}
      {...props}
    />
  );
}

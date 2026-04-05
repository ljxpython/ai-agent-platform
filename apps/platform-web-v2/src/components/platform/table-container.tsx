import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils/cn";

export function TableContainer({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("overflow-hidden rounded-[1.5rem] border", className)}
      style={{
        borderColor: "var(--border)",
      }}
      {...props}
    />
  );
}

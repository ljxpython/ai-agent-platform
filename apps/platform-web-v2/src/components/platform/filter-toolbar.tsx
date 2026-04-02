import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils/cn";

export function FilterToolbar({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-3 rounded-[1.25rem] border px-3 py-3",
        className,
      )}
      style={{
        borderColor: "var(--border)",
        background: "var(--surface-soft)",
      }}
      {...props}
    />
  );
}

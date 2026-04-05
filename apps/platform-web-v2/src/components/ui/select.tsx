import type { SelectHTMLAttributes } from "react";

import { cn } from "@/lib/utils/cn";

export function Select({
  className,
  style,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        "h-10 w-full rounded-xl border px-3 text-sm transition duration-150 outline-none focus:ring-2 focus:ring-[color:var(--primary)]/20",
        className,
      )}
      style={{
        background: "var(--input-background)",
        color: "var(--input-foreground)",
        borderColor: "var(--border)",
        ...style,
      }}
      {...props}
    />
  );
}

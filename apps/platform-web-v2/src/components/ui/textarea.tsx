import type { TextareaHTMLAttributes } from "react";

import { cn } from "@/lib/utils/cn";

export function Textarea({
  className,
  style,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(
        "min-h-28 w-full rounded-2xl border px-3 py-3 text-sm transition duration-150 outline-none placeholder:text-[var(--muted-foreground)] focus:ring-2 focus:ring-[color:var(--primary)]/20",
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

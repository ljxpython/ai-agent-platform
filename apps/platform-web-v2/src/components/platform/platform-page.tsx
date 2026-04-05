import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils/cn";

export function PlatformPage({ className, ...props }: HTMLAttributes<HTMLElement>) {
  return <section className={cn("flex min-w-0 flex-col gap-6", className)} {...props} />;
}

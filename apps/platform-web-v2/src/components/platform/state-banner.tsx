import type { HTMLAttributes } from "react";

import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils/cn";

function getBannerStyle(variant: "error" | "info" | "success") {
  if (variant === "error") {
    return {
      background: "var(--status-danger-background)",
      borderColor: "transparent",
      color: "var(--status-danger-foreground)",
    };
  }

  if (variant === "success") {
    return {
      background: "var(--status-success-background)",
      borderColor: "transparent",
      color: "var(--status-success-foreground)",
    };
  }

  return {
    background: "var(--status-neutral-background)",
    borderColor: "transparent",
    color: "var(--status-neutral-foreground)",
  };
}

export function StateBanner({
  className,
  message,
  variant = "info",
  ...props
}: HTMLAttributes<HTMLDivElement> & {
  message: string;
  variant?: "error" | "info" | "success";
}) {
  return (
    <Card className={cn("px-4 py-3 text-sm font-medium", className)} style={getBannerStyle(variant)} {...props}>
      {message}
    </Card>
  );
}

import { cn } from "@/lib/utils/cn";

type StatusPillProps = {
  label: string;
  variant?: "success" | "warning" | "neutral" | "danger";
};

function getStatusStyle(variant: NonNullable<StatusPillProps["variant"]>) {
  if (variant === "success") {
    return {
      background: "var(--status-success-background)",
      color: "var(--status-success-foreground)",
    };
  }

  if (variant === "warning") {
    return {
      background: "var(--status-warning-background)",
      color: "var(--status-warning-foreground)",
    };
  }

  if (variant === "danger") {
    return {
      background: "var(--status-danger-background)",
      color: "var(--status-danger-foreground)",
    };
  }

  return {
    background: "var(--status-neutral-background)",
    color: "var(--status-neutral-foreground)",
  };
}

export function StatusPill({ label, variant = "neutral" }: StatusPillProps) {
  return (
    <span
      className={cn(
        "inline-flex min-h-7 items-center rounded-full px-3 text-xs font-bold uppercase tracking-[0.08em]",
      )}
      style={getStatusStyle(variant)}
    >
      {label}
    </span>
  );
}

import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type PageStateProps = {
  message: ReactNode;
  className?: string;
  testId: "state-loading" | "state-empty" | "state-error" | "state-notice";
};

const PAGE_STATE_A11Y: Record<
  PageStateProps["testId"],
  { role: "status" | "alert"; ariaLive: "polite" | "assertive"; ariaAtomic: boolean }
> = {
  "state-loading": { role: "status", ariaLive: "polite", ariaAtomic: true },
  "state-empty": { role: "status", ariaLive: "polite", ariaAtomic: true },
  "state-error": { role: "alert", ariaLive: "assertive", ariaAtomic: true },
  "state-notice": { role: "status", ariaLive: "polite", ariaAtomic: true },
};

function PageState({ message, className, testId }: PageStateProps) {
  const a11y = PAGE_STATE_A11Y[testId];

  return (
    <p
      data-testid={testId}
      role={a11y.role}
      aria-live={a11y.ariaLive}
      aria-atomic={a11y.ariaAtomic}
      className={cn("mt-4 rounded-md border border-border bg-muted/40 px-3 py-2 text-sm", className)}
    >
      {message}
    </p>
  );
}

type PageStateMessageProps = {
  message?: ReactNode;
  className?: string;
};

export function PageStateLoading({ message = "Loading...", className }: PageStateMessageProps) {
  return <PageState testId="state-loading" message={message} className={cn("text-muted-foreground", className)} />;
}

export function PageStateEmpty({ message, className }: PageStateMessageProps) {
  return <PageState testId="state-empty" message={message ?? "No data found."} className={cn("text-muted-foreground", className)} />;
}

export function PageStateError({ message, className }: PageStateMessageProps) {
  return <PageState testId="state-error" message={message ?? "Something went wrong."} className={cn("border-destructive/40 bg-destructive/10 text-destructive", className)} />;
}

export function PageStateNotice({ message, className }: PageStateMessageProps) {
  return <PageState testId="state-notice" message={message ?? "Done."} className={cn("border-primary/30 bg-primary/10 text-foreground", className)} />;
}

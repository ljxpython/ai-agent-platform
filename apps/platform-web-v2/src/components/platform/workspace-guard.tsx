"use client";

import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";

import { ensureOidcSession } from "@/lib/oidc-storage";

export function WorkspaceGuard({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;

    void ensureOidcSession().then((loggedIn) => {
      if (cancelled) {
        return;
      }

      if (!loggedIn) {
        router.replace("/auth/login?redirect=/workspace/overview");
        return;
      }

      setReady(true);
    });

    return () => {
      cancelled = true;
    };
  }, [router]);

  if (!ready) {
    return <div className="p-6 text-sm text-[var(--muted-foreground)]">Checking workspace session...</div>;
  }

  return children;
}

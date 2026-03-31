"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { type ReactNode, useEffect, useMemo, useState } from "react";

import { ensureOidcSession } from "@/lib/oidc-storage";

export function WorkspaceAuthGuard({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [ready, setReady] = useState(false);
  const [loggedIn, setLoggedIn] = useState(false);

  const redirectTarget = useMemo(() => {
    const query = searchParams.toString();
    return query ? `${pathname}?${query}` : pathname;
  }, [pathname, searchParams]);

  useEffect(() => {
    let cancelled = false;

    void ensureOidcSession().then((nextLoggedIn) => {
      if (cancelled) {
        return;
      }

      setLoggedIn(nextLoggedIn);
      setReady(true);

      if (!nextLoggedIn) {
        const params = new URLSearchParams();
        params.set("redirect", redirectTarget);
        router.replace(`/auth/login?${params.toString()}`);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [pathname, redirectTarget, router]);

  if (!ready || !loggedIn) {
    return <div className="p-6">Redirecting to login...</div>;
  }

  return <>{children}</>;
}

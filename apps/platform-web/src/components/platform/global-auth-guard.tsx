"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { type ReactNode, useEffect, useMemo, useState } from "react";

import { ensureOidcSession } from "@/lib/oidc-storage";

const PUBLIC_PATH_PREFIXES = ["/auth/login", "/auth/callback"];

function isPublicPath(pathname: string): boolean {
  return PUBLIC_PATH_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

export function GlobalAuthGuard({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [ready, setReady] = useState(false);
  const [loggedIn, setLoggedIn] = useState(false);

  const redirectTarget = useMemo(() => {
    const query = searchParams.toString();
    return query ? `${pathname}?${query}` : pathname;
  }, [pathname, searchParams]);

  const publicPath = isPublicPath(pathname);

  useEffect(() => {
    let cancelled = false;

    void ensureOidcSession().then((nextLoggedIn) => {
      if (cancelled) {
        return;
      }

      setLoggedIn(nextLoggedIn);
      setReady(true);

      if (publicPath) {
        if (nextLoggedIn && pathname.startsWith("/auth/login")) {
          router.replace("/workspace/chat");
        }
        return;
      }

      if (!nextLoggedIn) {
        const params = new URLSearchParams();
        params.set("redirect", redirectTarget);
        router.replace(`/auth/login?${params.toString()}`);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [pathname, publicPath, redirectTarget, router]);

  if (!publicPath && (!ready || !loggedIn)) {
    return <div className="p-6">Redirecting to login...</div>;
  }

  return <>{children}</>;
}

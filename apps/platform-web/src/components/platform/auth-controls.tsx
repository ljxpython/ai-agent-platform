"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { clearOidcTokenSet, hasOidcSession } from "@/lib/oidc-storage";

export function AuthControls() {
  const router = useRouter();
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    setLoggedIn(hasOidcSession());
  }, []);

  return loggedIn ? (
    <button
      type="button"
      className="bg-background rounded-md border px-3 py-1 text-sm"
      onClick={() => {
        clearOidcTokenSet();
        router.replace("/auth/login");
      }}
    >
      Sign out
    </button>
  ) : (
    <button
      type="button"
      className="bg-foreground text-background rounded-md px-3 py-1 text-sm"
      onClick={() => router.push("/auth/login")}
    >
      Sign in
    </button>
  );
}

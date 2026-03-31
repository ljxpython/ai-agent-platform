"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { hasOidcSession } from "@/lib/oidc-storage";


export default function Page() {
  const router = useRouter();

  useEffect(() => {
    if (hasOidcSession()) {
      router.replace("/workspace/projects");
      return;
    }
    router.replace("/auth/login");
  }, [router]);

  return null;
}

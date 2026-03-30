"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";

export default function TestcaseIndexPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const query = searchParams.toString();
    router.replace(query ? `/workspace/testcase/generate?${query}` : "/workspace/testcase/generate");
  }, [router, searchParams]);

  return <div className="p-6 text-sm text-muted-foreground">Redirecting to Testcase workspace...</div>;
}

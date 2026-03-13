import type { Metadata } from "next";
import { NuqsAdapter } from "nuqs/adapters/next/app";
import type { ReactNode } from "react";
import { Suspense } from "react";

import "./globals.css";

import { GlobalAuthGuard } from "@/components/platform/global-auth-guard";

export const metadata: Metadata = {
  title: "Platform Web",
  description: "Platform workspace UI for management, chat, and runtime operations.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="font-sans">
        <NuqsAdapter>
          <Suspense fallback={<div className="p-6">Loading...</div>}>
            <GlobalAuthGuard>{children}</GlobalAuthGuard>
          </Suspense>
        </NuqsAdapter>
      </body>
    </html>
  );
}

import type { Metadata } from "next";
import { NuqsAdapter } from "nuqs/adapters/next/app";
import type { ReactNode } from "react";

import "./globals.css";

import { ThemeProvider } from "@/providers/ThemeProvider";
import { buildThemeInitScript } from "@/theme/theme-script";

export const metadata: Metadata = {
  title: "Platform Web V2",
  description: "Next generation workspace UI for the platform console.",
  icons: {
    icon: "/favicon.svg",
  },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body>
        <script dangerouslySetInnerHTML={{ __html: buildThemeInitScript() }} />
        <NuqsAdapter>
          <ThemeProvider>{children}</ThemeProvider>
        </NuqsAdapter>
      </body>
    </html>
  );
}

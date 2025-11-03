"use client";
// eslint-disable  MC8yOmFIVnBZMlhtblk3a3ZiUG1yS002UVZRNU9RPT06ZGJhY2FmZTc=

import { Thread } from "@/components/thread";
import { StreamProvider } from "@/providers/Stream";
import { ThreadProvider } from "@/providers/Thread";
import { ArtifactProvider } from "@/components/thread/artifact";
import { Toaster } from "@/components/ui/sonner";
import React from "react";
// NOTE  MS8yOmFIVnBZMlhtblk3a3ZiUG1yS002UVZRNU9RPT06ZGJhY2FmZTc=

export default function DemoPage(): React.ReactNode {
  return (
    <React.Suspense fallback={<div>加载中...</div>}>
      <Toaster />
      <ThreadProvider>
        <StreamProvider>
          <ArtifactProvider>
            <Thread />
          </ArtifactProvider>
        </StreamProvider>
      </ThreadProvider>
    </React.Suspense>
  );
}

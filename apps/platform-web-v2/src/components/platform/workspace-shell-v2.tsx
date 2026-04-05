"use client";

import type { ReactNode } from "react";

import { SidebarNav } from "@/components/platform/sidebar-nav";
import { TopContextBar } from "@/components/platform/top-context-bar";

export function WorkspaceShellV2({ children }: { children: ReactNode }) {
  return (
    <div className="workspace-shell">
      <aside className="workspace-shell__sidebar">
        <div className="workspace-shell__brand">
          <div className="workspace-shell__brand-mark">PW</div>
          <div>
            <div className="workspace-shell__brand-title">Platform Workspace</div>
            <div className="workspace-shell__brand-subtitle">enterprise console</div>
          </div>
        </div>

        <SidebarNav />

        <div className="workspace-shell__sidebar-footer">
          <div className="workspace-shell__workspace-card">
            <div className="workspace-shell__workspace-name">Byte AI Lab</div>
            <div className="workspace-shell__workspace-meta">Shanghai Workspace</div>
          </div>
        </div>
      </aside>

      <div className="workspace-shell__main">
        <TopContextBar />
        <main className="workspace-shell__content">{children}</main>
      </div>
    </div>
  );
}

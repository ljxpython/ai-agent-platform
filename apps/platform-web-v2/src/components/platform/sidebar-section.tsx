import type { ReactNode } from "react";

type SidebarSectionProps = {
  label: string;
  children: ReactNode;
};

export function SidebarSection({ label, children }: SidebarSectionProps) {
  return (
    <section className="workspace-shell__nav-group">
      <div className="workspace-shell__nav-label">{label}</div>
      {children}
    </section>
  );
}

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useWorkspaceContext } from "@/providers/WorkspaceProvider";

import { SidebarSection } from "./sidebar-section";

type NavItem = {
  href: string;
  label: string;
  requiresAuditAccess?: boolean;
  children?: readonly {
    href: string;
    label: string;
  }[];
};

const NAV_GROUPS = [
  {
    label: "Workspace",
    items: [
      { href: "/workspace/overview", label: "Overview" },
      { href: "/workspace/projects", label: "Projects" },
      { href: "/workspace/assistants", label: "Assistants" },
      { href: "/workspace/users", label: "Users" },
    ],
  },
  {
    label: "Account",
    items: [
      { href: "/workspace/me", label: "My Profile" },
      { href: "/workspace/security", label: "Security" },
    ],
  },
  {
    label: "Advanced",
    items: [
      { href: "/workspace/graphs", label: "Graphs" },
      { href: "/workspace/runtime", label: "Runtime" },
      { href: "/workspace/sql-agent", label: "SQL Agent" },
      { href: "/workspace/audit", label: "Audit", requiresAuditAccess: true },
      { href: "/workspace/threads", label: "Threads" },
      { href: "/workspace/chat", label: "Chat" },
      {
        href: "/workspace/testcase/generate",
        label: "Testcase",
        children: [
          { href: "/workspace/testcase/generate", label: "AI 对话生成" },
          { href: "/workspace/testcase/cases", label: "用例管理" },
          { href: "/workspace/testcase/documents", label: "文档解析" },
        ],
      },
    ],
  },
] as const satisfies readonly {
  label: string;
  items: readonly NavItem[];
}[];

function buildScopedHref(href: string, projectId: string) {
  const normalizedProjectId = projectId.trim();
  if (!normalizedProjectId) {
    return href;
  }

  const params = new URLSearchParams({ projectId: normalizedProjectId });
  return `${href}?${params.toString()}`;
}

function isItemActive(pathname: string | null, item: NavItem) {
  if (!pathname) {
    return false;
  }
  if (pathname === item.href) {
    return true;
  }
  return pathname.startsWith(`${item.href}/`);
}

export function SidebarNav() {
  const pathname = usePathname();
  const { canAccessAudit, projectId } = useWorkspaceContext();

  const visibleGroups: Array<{ label: string; items: NavItem[] }> = NAV_GROUPS.map((group) => ({
    ...group,
    items: [...group.items].filter(
      (item) =>
        !("requiresAuditAccess" in item) ||
        !item.requiresAuditAccess ||
        canAccessAudit,
    ),
  })).filter((group) => group.items.length > 0);

  return (
    <>
      {visibleGroups.map((group) => (
        <SidebarSection key={group.label} label={group.label}>
          <nav className="workspace-shell__nav-list" aria-label={group.label}>
            {group.items.map((item) => {
              const active = isItemActive(pathname, item);
              return (
                <div key={item.href} className="workspace-shell__nav-entry">
                  <Link
                    className={`workspace-shell__nav-item ${active ? "is-active" : ""}`}
                    href={buildScopedHref(item.href, projectId)}
                  >
                    {item.label}
                  </Link>
                  {item.children?.length ? (
                    <div className="workspace-shell__nav-sublist">
                      {item.children.map((child) => {
                        const childActive = pathname === child.href;
                        return (
                          <Link
                            key={child.href}
                            className={`workspace-shell__nav-subitem ${childActive ? "is-active" : ""}`}
                            href={buildScopedHref(child.href, projectId)}
                          >
                            {child.label}
                          </Link>
                        );
                      })}
                    </div>
                  ) : null}
                </div>
              );
            })}
          </nav>
        </SidebarSection>
      ))}
    </>
  );
}

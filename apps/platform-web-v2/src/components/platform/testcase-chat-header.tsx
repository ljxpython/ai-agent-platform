"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils/cn";
import { useWorkspaceContext } from "@/providers/WorkspaceContext";

const HEADER_ITEMS = [
  {
    label: "固定目标",
    value: "test_case_agent",
    meta: "graph",
  },
  {
    label: "持久化范围",
    value: "documents + test_cases",
    meta: "documents 上传即落库，test_cases 正式保存后可回看",
  },
];

const TESTCASE_NAV_ITEMS = [
  {
    href: "/workspace/testcase/generate",
    label: "AI 对话生成",
  },
  {
    href: "/workspace/testcase/cases",
    label: "用例列表",
  },
  {
    href: "/workspace/testcase/documents",
    label: "文档列表",
  },
];

function buildScopedHref(pathname: string, projectId: string) {
  const normalizedProjectId = projectId.trim();
  if (!normalizedProjectId) {
    return pathname;
  }

  const params = new URLSearchParams({ projectId: normalizedProjectId });
  return `${pathname}?${params.toString()}`;
}

export function TestcaseWorkspaceNav() {
  const pathname = usePathname();
  const { projectId } = useWorkspaceContext();

  return (
    <div className="flex flex-wrap gap-2">
      {TESTCASE_NAV_ITEMS.map((item) => {
        const active = pathname === item.href;
        return (
          <Link
            key={item.href}
            href={buildScopedHref(item.href, projectId)}
            className={cn(
              "inline-flex h-9 items-center rounded-full border px-4 text-sm font-medium transition-colors",
              active
                ? "border-primary/30 bg-primary/10 text-foreground"
                : "border-border bg-background/80 text-muted-foreground hover:text-foreground",
            )}
          >
            {item.label}
          </Link>
        );
      })}
    </div>
  );
}

export function TestcaseChatHeader() {
  const { projectId } = useWorkspaceContext();

  return (
    <div className="grid max-w-[min(100%,32rem)] gap-2">
      <div className="grid gap-1 rounded-md bg-muted/25 px-2 py-2">
        <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">当前项目</div>
        <div className="break-all text-sm font-semibold">{projectId || "未选择项目"}</div>
        <div className="text-xs text-muted-foreground">WorkspaceContext project scope</div>
      </div>
      {HEADER_ITEMS.map((item) => (
        <div key={item.label} className="grid gap-1 rounded-md bg-muted/25 px-2 py-2">
          <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">{item.label}</div>
          <div className="text-sm font-semibold">{item.value}</div>
          <div className="text-xs text-muted-foreground">{item.meta}</div>
        </div>
      ))}
    </div>
  );
}

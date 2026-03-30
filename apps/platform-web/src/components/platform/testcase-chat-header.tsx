"use client";

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
    meta: "正式保存后可回看",
  },
];

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

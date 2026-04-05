"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { TestcaseOverview } from "@/lib/management-api/testcase";

function formatDateTime(value?: string | null) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

export function TestcaseOverviewStrip({ overview }: { overview: TestcaseOverview | null }) {
  const items = [
    {
      label: "正式用例",
      value: String(overview?.test_cases_total ?? 0),
      meta: overview?.latest_batch_id ?? "无批次",
    },
    {
      label: "解析文档",
      value: String(overview?.documents_total ?? 0),
      meta: `parsed=${overview?.parsed_documents_total ?? 0}`,
    },
    {
      label: "失败文档",
      value: String(overview?.failed_documents_total ?? 0),
      meta: overview?.failed_documents_total ? "需要回看" : "状态正常",
    },
    {
      label: "最近活动",
      value: formatDateTime(overview?.latest_activity_at),
      meta: overview?.project_id || "未选择项目",
    },
  ];

  return (
    <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => (
        <Card key={item.label} className="gap-3 py-4">
          <CardHeader className="px-4">
            <CardTitle className="text-sm font-medium text-muted-foreground">{item.label}</CardTitle>
          </CardHeader>
          <CardContent className="px-4">
            <div className="text-lg font-semibold tracking-tight">{item.value}</div>
            <div className="mt-1 text-xs text-muted-foreground">{item.meta}</div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

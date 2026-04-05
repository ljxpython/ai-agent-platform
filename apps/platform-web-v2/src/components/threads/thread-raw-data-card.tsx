"use client";

import { useState } from "react";

import { toPrettyJson } from "@/lib/threads";

export function ThreadRawDataCard({
  metadata,
  values,
  state,
}: {
  metadata?: Record<string, unknown> | null;
  values?: Record<string, unknown> | null;
  state?: Record<string, unknown> | null;
}) {
  return (
    <section className="grid gap-3 rounded-lg border border-border/80 bg-card/70 p-4">
      <div>
        <h3 className="text-base font-semibold">Raw Data</h3>
        <p className="mt-1 text-sm text-muted-foreground">大对象默认收起，需要时再展开，避免页面初始化被 JSON 渲染拖死。</p>
      </div>
      <JsonBlock title="Metadata" value={metadata} defaultExpanded />
      <JsonBlock title="Values" value={values} />
      <JsonBlock title="State" value={state} />
    </section>
  );
}

function summarizeValue(value: unknown): string {
  if (value == null) {
    return "empty";
  }
  if (Array.isArray(value)) {
    return `${value.length} items`;
  }
  if (typeof value === "object") {
    return `${Object.keys(value as Record<string, unknown>).length} keys`;
  }
  if (typeof value === "string") {
    return `${value.length} chars`;
  }
  return typeof value;
}

function JsonBlock({
  title,
  value,
  defaultExpanded = false,
}: {
  title: string;
  value: unknown;
  defaultExpanded?: boolean;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  return (
    <div className="grid gap-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{title}</p>
        <button
          type="button"
          className="rounded-md border border-border/70 bg-background/60 px-2 py-1 text-[11px] text-muted-foreground"
          onClick={() => setExpanded((current) => !current)}
        >
          {expanded ? "收起" : `展开 ${summarizeValue(value)}`}
        </button>
      </div>
      {expanded ? (
        <pre className="overflow-x-auto rounded-md border border-border/70 bg-background/60 p-3 text-xs whitespace-pre-wrap break-words">
          {toPrettyJson(value)}
        </pre>
      ) : null}
    </div>
  );
}

"use client";

import { useState } from "react";

import type { ThreadHistoryEntry } from "@/lib/management-api/threads";
import { getHistoryEntryId, getHistoryEntryTime, toPrettyJson } from "@/lib/threads";

import { PageStateEmpty } from "@/components/platform/page-state";

export function ThreadHistoryTimeline({
  items,
  loading,
}: {
  items: ThreadHistoryEntry[];
  loading?: boolean;
}) {
  const [expandedIds, setExpandedIds] = useState<Record<string, boolean>>({});

  function toggleEntry(entryId: string) {
    setExpandedIds((current) => ({ ...current, [entryId]: !current[entryId] }));
  }

  return (
    <section className="grid gap-3 rounded-lg border border-border/80 bg-card/70 p-4">
      <div>
        <h3 className="text-base font-semibold">History</h3>
        <p className="mt-1 text-sm text-muted-foreground">默认只展示 checkpoint 摘要，避免历史 JSON 全量展开把页面拖慢。</p>
      </div>
      {loading ? <p className="text-sm text-muted-foreground">Loading history...</p> : null}
      {!loading && items.length === 0 ? (
        <PageStateEmpty className="mt-0" message="No history entries found for this thread." />
      ) : null}
      {!loading ? (
        <div className="grid gap-3">
          {items.map((entry, index) => {
            const entryId = getHistoryEntryId(entry, index);
            const expanded = Boolean(expandedIds[entryId]);
            return (
              <article key={entryId} className="rounded-md border border-border/70 bg-background/60 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="grid gap-1">
                    <p className="font-mono text-xs text-muted-foreground">{entryId}</p>
                    <p className="text-xs text-muted-foreground">{getHistoryEntryTime(entry)}</p>
                  </div>
                  <button
                    type="button"
                    className="rounded-md border border-border/70 bg-background px-2 py-1 text-[11px] text-muted-foreground"
                    onClick={() => toggleEntry(entryId)}
                  >
                    {expanded ? "收起 payload" : "展开 payload"}
                  </button>
                </div>
                {expanded ? (
                  <pre className="mt-3 overflow-x-auto text-xs whitespace-pre-wrap break-words">{toPrettyJson(entry)}</pre>
                ) : null}
              </article>
            );
          })}
        </div>
      ) : null}
    </section>
  );
}

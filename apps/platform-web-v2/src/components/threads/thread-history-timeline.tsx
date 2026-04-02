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
  return (
    <section className="grid gap-3 rounded-lg border border-border/80 bg-card/70 p-4">
      <div>
        <h3 className="text-base font-semibold">History</h3>
        <p className="mt-1 text-sm text-muted-foreground">Checkpoint and history entries returned by the LangGraph threads history API.</p>
      </div>
      {loading ? <p className="text-sm text-muted-foreground">Loading history...</p> : null}
      {!loading && items.length === 0 ? (
        <PageStateEmpty className="mt-0" message="No history entries found for this thread." />
      ) : null}
      {!loading ? (
        <div className="grid gap-3">
          {items.map((entry, index) => (
            <article key={getHistoryEntryId(entry, index)} className="rounded-md border border-border/70 bg-background/60 p-3">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <p className="font-mono text-xs text-muted-foreground">{getHistoryEntryId(entry, index)}</p>
                <p className="text-xs text-muted-foreground">{getHistoryEntryTime(entry)}</p>
              </div>
              <pre className="overflow-x-auto text-xs whitespace-pre-wrap break-words">{toPrettyJson(entry)}</pre>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}

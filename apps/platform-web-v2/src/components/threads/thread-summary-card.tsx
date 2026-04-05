import type { ManagementThread } from "@/lib/management-api/threads";

import { getThreadAssistantId, getThreadGraphId, formatThreadTime } from "@/lib/threads";

export function ThreadSummaryCard({
  thread,
  onCopyThreadId,
  onOpenInChat,
}: {
  thread: ManagementThread;
  onCopyThreadId: (threadId: string) => void;
  onOpenInChat: (threadId: string) => void;
}) {
  return (
    <section className="grid gap-3 rounded-lg border border-border/80 bg-card/70 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold">Thread Summary</h3>
          <p className="mt-1 font-mono text-xs text-muted-foreground">{thread.thread_id}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="inline-flex h-9 items-center justify-center rounded-md border border-border bg-background px-3 text-sm"
            onClick={() => onCopyThreadId(thread.thread_id)}
          >
            Copy Thread ID
          </button>
          <button
            type="button"
            className="inline-flex h-9 items-center justify-center rounded-md border border-border bg-background px-3 text-sm"
            onClick={() => onOpenInChat(thread.thread_id)}
          >
            Open in Chat
          </button>
        </div>
      </div>

      <dl className="grid gap-3 text-sm sm:grid-cols-2 xl:grid-cols-3">
        <Meta label="Status" value={thread.status || "-"} />
        <Meta label="Assistant" value={getThreadAssistantId(thread) || "-"} />
        <Meta label="Graph" value={getThreadGraphId(thread) || "-"} />
        <Meta label="Created" value={formatThreadTime(thread.created_at)} />
        <Meta label="Updated" value={formatThreadTime(thread.updated_at)} />
      </dl>
    </section>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-1 rounded-md border border-border/70 bg-background/60 p-3">
      <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="break-all text-sm">{value}</dd>
    </div>
  );
}

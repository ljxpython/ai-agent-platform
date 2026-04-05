import type { ManagementThread } from "@/lib/management-api/threads";
import { formatThreadTime, getThreadAssistantId, getThreadGraphId, getThreadListTitle } from "@/lib/threads";
import { cn } from "@/lib/utils";

export function ThreadListItem({
  item,
  selected,
  onClick,
}: {
  item: ManagementThread;
  selected?: boolean;
  onClick: () => void;
}) {
  const assistantId = getThreadAssistantId(item);
  const graphId = getThreadGraphId(item);
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex min-h-28 w-full flex-col justify-between rounded-none border border-t-0 px-3 py-3 text-left transition-colors first:rounded-t-lg first:border-t last:rounded-b-lg",
        selected
          ? "border-sidebar-primary/60 bg-sidebar-primary/10"
          : "border-border/70 bg-card/70 hover:bg-muted/40",
      )}
    >
      <div className="grid gap-2">
        <div className="line-clamp-2 overflow-hidden break-words text-sm font-medium leading-5">
          {getThreadListTitle(item)}
        </div>
        <div className="flex flex-wrap gap-2 text-[11px] text-muted-foreground">
          {item.status ? <span className="rounded-full border border-border/70 px-2 py-0.5">{item.status}</span> : null}
          {assistantId ? <span className="rounded-full border border-border/70 px-2 py-0.5">{assistantId}</span> : null}
          {graphId ? <span className="rounded-full border border-border/70 px-2 py-0.5">{graphId}</span> : null}
        </div>
      </div>
      <div className="grid gap-1">
        <div className="font-mono text-[11px] text-muted-foreground">{item.thread_id}</div>
        <div className="text-[11px] text-muted-foreground">
          updated {formatThreadTime(item.updated_at ?? item.created_at ?? null)}
        </div>
      </div>
    </button>
  );
}

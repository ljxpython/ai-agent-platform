import type { ManagementThread } from "@/lib/management-api/threads";
import { getThreadPreviewText } from "@/lib/management-api/threads";
import { formatThreadTime } from "@/lib/threads";
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
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex h-24 w-full flex-col justify-between rounded-none border border-t-0 px-3 py-3 text-left transition-colors first:rounded-t-lg first:border-t last:rounded-b-lg",
        selected
          ? "border-sidebar-primary/60 bg-sidebar-primary/10"
          : "border-border/70 bg-card/70 hover:bg-muted/40",
      )}
    >
      <div className="line-clamp-2 overflow-hidden break-words text-sm font-medium leading-5">
        {getThreadPreviewText(item)}
      </div>
      <div className="font-mono text-[11px] text-muted-foreground">{item.thread_id}</div>
      <div className="text-[11px] text-muted-foreground">
        updated {formatThreadTime(item.updated_at ?? item.created_at ?? null)}
      </div>
    </button>
  );
}

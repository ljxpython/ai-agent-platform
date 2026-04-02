import type { ManagementThread } from "@/lib/management-api/threads";

import { ThreadHistoryEmpty } from "./thread-history-empty";
import { ThreadHistoryLoading } from "./thread-history-loading";
import { ThreadListItem } from "./thread-list-item";

export function ThreadList({
  items,
  selectedThreadId,
  loading,
  onSelect,
}: {
  items: ManagementThread[];
  selectedThreadId?: string;
  loading?: boolean;
  onSelect: (item: ManagementThread) => void;
}) {
  if (loading) {
    return <ThreadHistoryLoading />;
  }

  if (items.length === 0) {
    return <ThreadHistoryEmpty message="No threads found for the current filters." />;
  }

  return (
    <div className="grid gap-0">
      {items.map((item) => (
        <ThreadListItem
          key={item.thread_id}
          item={item}
          selected={item.thread_id === selectedThreadId}
          onClick={() => onSelect(item)}
        />
      ))}
    </div>
  );
}

import type { Message } from "@langchain/langgraph-sdk";

import { PageStateEmpty, PageStateError, PageStateLoading } from "@/components/platform/page-state";
import type { ManagementThread, ThreadHistoryEntry } from "@/lib/management-api/threads";

import { ThreadHistoryTimeline } from "./thread-history-timeline";
import { ThreadMessagePreview } from "./thread-message-preview";
import { ThreadRawDataCard } from "./thread-raw-data-card";
import { ThreadSummaryCard } from "./thread-summary-card";

export function ThreadDetailPanel({
  thread,
  state,
  historyItems,
  messages,
  loading,
  error,
  onCopyThreadId,
  onOpenInChat,
}: {
  thread?: ManagementThread | null;
  state?: Record<string, unknown> | null;
  historyItems: ThreadHistoryEntry[];
  messages: Message[];
  loading?: boolean;
  error?: string | null;
  onCopyThreadId: (threadId: string) => void;
  onOpenInChat: (threadId: string) => void;
}) {
  if (!thread) {
    return <PageStateEmpty className="mt-0" message="Select a thread to inspect its detail and history." />;
  }

  if (loading) {
    return <PageStateLoading className="mt-0" message="Loading thread detail..." />;
  }

  if (error) {
    return <PageStateError className="mt-0" message={error} />;
  }

  return (
    <div className="grid gap-4">
      <ThreadSummaryCard thread={thread} onCopyThreadId={onCopyThreadId} onOpenInChat={onOpenInChat} />
      <ThreadMessagePreview messages={messages} />
      <ThreadHistoryTimeline items={historyItems} />
      <ThreadRawDataCard
        metadata={thread.metadata as Record<string, unknown> | null | undefined}
        values={thread.values as Record<string, unknown> | null | undefined}
        state={state}
      />
    </div>
  );
}

import { Button } from "@/components/ui/button";
import { useThreads } from "@/providers/Thread";
import { Thread } from "@langchain/langgraph-sdk";
import { useEffect, useMemo, useState } from "react";

import { getContentString } from "../utils";
import { useQueryState, parseAsBoolean } from "nuqs";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { PanelRightOpen, PanelRightClose, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { useMediaQuery } from "@/hooks/useMediaQuery";

const THREAD_HISTORY_SKELETON_KEYS = Array.from(
  { length: 30 },
  (_, index) => `thread-history-skeleton-${index + 1}`,
);

function isStaleTenantScopeError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error);
  return (
    message.includes("tenant_access_denied") ||
    message.includes("Tenant membership not found")
  );
}

type StatusFilter = "all" | "idle" | "busy" | "interrupted" | "error";

type ThreadListItem = {
  id: string;
  title: string;
  updatedAt: Date | null;
  status: string;
};

const STATUS_FILTERS: Array<{ value: StatusFilter; label: string }> = [
  { value: "all", label: "All" },
  { value: "interrupted", label: "Interrupted" },
  { value: "busy", label: "Busy" },
  { value: "idle", label: "Idle" },
  { value: "error", label: "Error" },
];

const GROUP_ORDER = ["interrupted", "today", "yesterday", "week", "older"] as const;
type GroupKey = (typeof GROUP_ORDER)[number];

const GROUP_LABELS: Record<GroupKey, string> = {
  interrupted: "Needs Attention",
  today: "Today",
  yesterday: "Yesterday",
  week: "This Week",
  older: "Older",
};

function parseDate(value: unknown): Date | null {
  if (typeof value !== "string" || !value.trim()) {
    return null;
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }
  return parsed;
}

function deriveThreadTitle(thread: Thread): string {
  if (
    typeof thread.values === "object" &&
    thread.values &&
    "messages" in thread.values &&
    Array.isArray(thread.values.messages) &&
    thread.values.messages.length > 0
  ) {
    const firstHuman = thread.values.messages.find(
      (message) => message && typeof message === "object" && "type" in message && message.type === "human",
    ) as { content?: unknown } | undefined;
    const firstMessage = firstHuman ?? (thread.values.messages[0] as { content?: unknown });
    const content = getContentString(firstMessage?.content ?? "");
    if (content.trim()) {
      return content.trim();
    }
  }
  return thread.thread_id;
}

function normalizeThreadStatus(status: unknown): string {
  if (typeof status !== "string") {
    return "idle";
  }
  return status;
}

function getStatusDotClass(status: string): string {
  if (status === "interrupted") return "bg-amber-500";
  if (status === "busy") return "bg-blue-500";
  if (status === "error") return "bg-red-500";
  return "bg-emerald-500";
}

function formatThreadTime(date: Date | null): string {
  if (!date) {
    return "";
  }
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function calcDayDiff(date: Date, now: Date): number {
  const nowAtMidnight = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const dateAtMidnight = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const diffMs = nowAtMidnight.getTime() - dateAtMidnight.getTime();
  return Math.floor(diffMs / (1000 * 60 * 60 * 24));
}

function groupThreadsByTime(items: ThreadListItem[]): Record<GroupKey, ThreadListItem[]> {
  const grouped: Record<GroupKey, ThreadListItem[]> = {
    interrupted: [],
    today: [],
    yesterday: [],
    week: [],
    older: [],
  };
  const now = new Date();

  for (const item of items) {
    if (item.status === "interrupted") {
      grouped.interrupted.push(item);
      continue;
    }

    if (!item.updatedAt) {
      grouped.older.push(item);
      continue;
    }

    const dayDiff = calcDayDiff(item.updatedAt, now);
    if (dayDiff <= 0) {
      grouped.today.push(item);
    } else if (dayDiff === 1) {
      grouped.yesterday.push(item);
    } else if (dayDiff < 7) {
      grouped.week.push(item);
    } else {
      grouped.older.push(item);
    }
  }

  return grouped;
}

function ThreadList({
  items,
  onThreadClick,
}: {
  items: ThreadListItem[];
  onThreadClick?: (threadId: string) => void;
}) {
  const [threadId, setThreadId] = useQueryState("threadId");

  return (
    <div className="flex h-full w-full flex-col items-start justify-start gap-2 overflow-y-scroll [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-border [&::-webkit-scrollbar-track]:bg-transparent">
      {items.map((item) => {
        return (
          <div
            key={item.id}
            className="w-full px-1"
          >
            <Button
              variant="ghost"
              className={cn(
                "h-auto w-[280px] justify-start px-3 py-2 text-left font-normal",
                threadId === item.id
                  ? "bg-accent text-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
              onClick={(e) => {
                e.preventDefault();
                onThreadClick?.(item.id);
                if (item.id === threadId) return;
                setThreadId(item.id);
              }}
            >
              <div className="grid w-full grid-cols-[auto_1fr_auto] items-center gap-2">
                <span className={cn("inline-block size-2 rounded-full", getStatusDotClass(item.status))} />
                <p className="truncate text-ellipsis text-sm">{item.title}</p>
                <span className="text-[11px] text-muted-foreground">{formatThreadTime(item.updatedAt)}</span>
              </div>
            </Button>
          </div>
        );
      })}
    </div>
  );
}

function ThreadHistoryLoading() {
  return (
    <div className="flex h-full w-full flex-col items-start justify-start gap-2 overflow-y-scroll [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-border [&::-webkit-scrollbar-track]:bg-transparent">
      {THREAD_HISTORY_SKELETON_KEYS.map((key) => (
        <Skeleton
          key={key}
          className="h-10 w-[280px]"
        />
      ))}
    </div>
  );
}

export default function ThreadHistory() {
  const isLargeScreen = useMediaQuery("(min-width: 1024px)");
  const [chatHistoryOpen, setChatHistoryOpen] = useQueryState(
    "chatHistoryOpen",
    parseAsBoolean.withDefault(false),
  );
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

  const { getThreads, threads, setThreads, threadsLoading, setThreadsLoading } =
    useThreads();

  useEffect(() => {
    if (typeof window === "undefined") return;
    setThreadsLoading(true);
    getThreads()
      .then(setThreads)
      .catch((error) => {
        if (isStaleTenantScopeError(error)) return;
        console.error(error);
      })
      .finally(() => setThreadsLoading(false));
  }, [getThreads, setThreads, setThreadsLoading]);

  const normalizedThreads = useMemo<ThreadListItem[]>(
    () =>
      threads
        .map((thread) => ({
          id: thread.thread_id,
          title: deriveThreadTitle(thread),
          updatedAt: parseDate(thread.updated_at),
          status: normalizeThreadStatus(thread.status),
        }))
        .sort((a, b) => (b.updatedAt?.getTime() ?? 0) - (a.updatedAt?.getTime() ?? 0)),
    [threads],
  );

  const interruptedCount = useMemo(
    () => normalizedThreads.filter((item) => item.status === "interrupted").length,
    [normalizedThreads],
  );

  const filteredThreads = useMemo(
    () =>
      statusFilter === "all"
        ? normalizedThreads
        : normalizedThreads.filter((item) => item.status === statusFilter),
    [normalizedThreads, statusFilter],
  );

  const groupedThreads = useMemo(() => groupThreadsByTime(filteredThreads), [filteredThreads]);

  return (
    <>
      <div className="shadow-inner-right hidden h-screen w-[300px] shrink-0 flex-col items-start justify-start gap-6 border-r border-border bg-card lg:flex">
        <div className="w-full border-b border-border/80 px-3 py-2">
          <div className="mb-2 flex w-full items-center justify-between">
            <Button
              className="text-muted-foreground hover:bg-muted hover:text-foreground"
              variant="ghost"
              onClick={() => setChatHistoryOpen((p) => !p)}
            >
              {chatHistoryOpen ? (
                <PanelRightOpen className="size-5" />
              ) : (
                <PanelRightClose className="size-5" />
              )}
            </Button>
            <h1 className="text-lg font-semibold tracking-tight">Thread History</h1>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-muted-foreground"
              onClick={() => {
                setThreadsLoading(true);
                getThreads()
                  .then(setThreads)
                  .catch((error) => {
                    if (isStaleTenantScopeError(error)) return;
                    console.error(error);
                  })
                  .finally(() => setThreadsLoading(false));
              }}
              disabled={threadsLoading}
            >
              <RefreshCw className={cn("size-4", threadsLoading && "animate-spin")} />
            </Button>
          </div>
          <div className="flex flex-wrap gap-1">
            {STATUS_FILTERS.map((filter) => (
              <button
                key={filter.value}
                type="button"
                onClick={() => setStatusFilter(filter.value)}
                className={cn(
                  "rounded-full border px-2 py-0.5 text-xs transition-colors",
                  statusFilter === filter.value
                    ? "border-primary bg-primary/10 text-foreground"
                    : "border-border bg-background text-muted-foreground hover:text-foreground",
                )}
              >
                {filter.label}
                {filter.value === "interrupted" && interruptedCount > 0 ? ` (${interruptedCount})` : ""}
              </button>
            ))}
          </div>
        </div>
        {threadsLoading ? (
          <ThreadHistoryLoading />
        ) : (
          <div className="w-full overflow-y-auto px-1 pb-3">
            {GROUP_ORDER.map((groupKey) => {
              const groupItems = groupedThreads[groupKey];
              if (groupItems.length === 0) return null;
              return (
                <div key={groupKey} className="mb-3">
                  <p className="px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                    {GROUP_LABELS[groupKey]}
                  </p>
                  <ThreadList items={groupItems} />
                </div>
              );
            })}
            {filteredThreads.length === 0 ? (
              <p className="px-3 py-4 text-xs text-muted-foreground">No threads under current filter.</p>
            ) : null}
          </div>
        )}
      </div>
      <div className="lg:hidden">
        <Sheet
          open={!!chatHistoryOpen && !isLargeScreen}
          onOpenChange={(open) => {
            if (isLargeScreen) return;
            setChatHistoryOpen(open);
          }}
        >
          <SheetContent
            side="left"
            className="flex lg:hidden"
          >
            <SheetHeader>
              <SheetTitle>Thread History</SheetTitle>
            </SheetHeader>
            <div className="mb-3 flex flex-wrap gap-1">
              {STATUS_FILTERS.map((filter) => (
                <button
                  key={filter.value}
                  type="button"
                  onClick={() => setStatusFilter(filter.value)}
                  className={cn(
                    "rounded-full border px-2 py-0.5 text-xs transition-colors",
                    statusFilter === filter.value
                      ? "border-primary bg-primary/10 text-foreground"
                      : "border-border bg-background text-muted-foreground",
                  )}
                >
                  {filter.label}
                  {filter.value === "interrupted" && interruptedCount > 0 ? ` (${interruptedCount})` : ""}
                </button>
              ))}
            </div>
            <div className="w-full overflow-y-auto">
              {GROUP_ORDER.map((groupKey) => {
                const groupItems = groupedThreads[groupKey];
                if (groupItems.length === 0) return null;
                return (
                  <div key={groupKey} className="mb-3">
                    <p className="px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                      {GROUP_LABELS[groupKey]}
                    </p>
                    <ThreadList
                      items={groupItems}
                      onThreadClick={() => setChatHistoryOpen((o) => !o)}
                    />
                  </div>
                );
              })}
            </div>
          </SheetContent>
        </Sheet>
      </div>
    </>
  );
}

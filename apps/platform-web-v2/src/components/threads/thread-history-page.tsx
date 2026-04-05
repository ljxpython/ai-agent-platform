"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import {
  listAssistantsPage,
  type ManagementAssistant,
} from "@/lib/management-api/assistants";
import { listGraphsPage, type ManagementGraph } from "@/lib/management-api/graphs";
import {
  type ListThreadsOptions,
  type ManagementThread,
  type ThreadHistoryEntry,
  getThreadDetail,
  getThreadHistoryPage,
  getThreadState,
  listThreadsPage,
} from "@/lib/management-api/threads";
import {
  getThreadAssistantId,
  getThreadGraphId,
  getThreadMessages,
} from "@/lib/threads";
import {
  applyChatTargetToSearchParams,
  normalizeChatTarget,
  writeRecentChatTarget,
} from "@/lib/chat-target-preference";
import { useWorkspaceContext } from "@/providers/WorkspaceContext";

import { ThreadDetailPanel } from "./thread-detail-panel";
import { ThreadHistoryToolbar } from "./thread-history-toolbar";
import { ThreadListPanel } from "./thread-list-panel";

export function ThreadHistoryPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { projectId, assistantId } = useWorkspaceContext();
  const initialThreadId = searchParams.get("threadId") || "";
  const initialQuery = searchParams.get("threadQuery") || "";
  const initialThreadIdFilter = searchParams.get("threadThreadId") || "";
  const initialAssistantFilter = searchParams.get("threadAssistantId") || assistantId || "";
  const initialGraphFilter = searchParams.get("threadGraphId") || "";
  const initialStatusFilter = searchParams.get("threadStatus") || "";

  const [items, setItems] = useState<ManagementThread[]>([]);
  const [selectedThread, setSelectedThread] = useState<ManagementThread | null>(null);
  const [selectedThreadId, setSelectedThreadId] = useState(initialThreadId);
  const [threadState, setThreadState] = useState<Record<string, unknown> | null>(null);
  const [historyItems, setHistoryItems] = useState<ThreadHistoryEntry[]>([]);
  const [assistantOptions, setAssistantOptions] = useState<ManagementAssistant[]>([]);
  const [graphOptions, setGraphOptions] = useState<ManagementGraph[]>([]);
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [searching, setSearching] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [customPage, setCustomPage] = useState("1");
  const [previewQuery, setPreviewQuery] = useState(initialQuery);
  const [threadIdQuery, setThreadIdQuery] = useState(initialThreadIdFilter);
  const [assistantFilter, setAssistantFilter] = useState(initialAssistantFilter);
  const [graphFilter, setGraphFilter] = useState(initialGraphFilter);
  const [statusFilter, setStatusFilter] = useState(initialStatusFilter);
  const [appliedFilters, setAppliedFilters] = useState({
    query: initialQuery,
    threadId: initialThreadIdFilter,
    assistantId: initialAssistantFilter,
    graphId: initialGraphFilter,
    status: initialStatusFilter,
  });

  const filters = useMemo<ListThreadsOptions>(
    () => ({
      query: appliedFilters.query.trim() || undefined,
      threadId: appliedFilters.threadId.trim() || undefined,
      assistantId: appliedFilters.assistantId.trim() || undefined,
      graphId: appliedFilters.graphId.trim() || undefined,
      status: appliedFilters.status.trim() || undefined,
      limit: pageSize,
      offset,
    }),
    [appliedFilters, offset, pageSize],
  );

  const refreshList = useCallback(async (nextFilters?: ListThreadsOptions) => {
    const activeFilters = nextFilters ?? filters;
    if (!projectId) {
      setItems([]);
      setTotal(0);
      setSelectedThread(null);
      setSelectedThreadId("");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const payload = await listThreadsPage(projectId, activeFilters);
      setItems(payload.items);
      setTotal(payload.total);
      if (selectedThreadId) {
        const matched = payload.items.find((item) => item.thread_id === selectedThreadId);
        if (matched) {
          setSelectedThread((current) => (current?.thread_id === matched.thread_id ? { ...current, ...matched } : matched));
        }
      }
      if (payload.total > 0 && offset >= payload.total) {
        const fallbackOffset = Math.max(0, (Math.ceil(payload.total / pageSize) - 1) * pageSize);
        if (fallbackOffset !== offset) {
          setOffset(fallbackOffset);
        }
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to load threads");
    } finally {
      setLoading(false);
    }
  }, [filters, offset, pageSize, projectId, selectedThreadId]);

  const refreshDetail = useCallback(async () => {
    if (!projectId || !selectedThreadId) {
      setSelectedThread(null);
      setThreadState(null);
      setHistoryItems([]);
      return;
    }
    const selectedSummary = items.find((item) => item.thread_id === selectedThreadId) ?? null;
    if (selectedSummary) {
      setSelectedThread(selectedSummary);
    }
    setDetailLoading(true);
    setDetailError(null);
    try {
      const [detail, state, history] = await Promise.all([
        selectedSummary ? Promise.resolve(selectedSummary) : getThreadDetail(projectId, selectedThreadId),
        getThreadState(projectId, selectedThreadId).catch(() => null),
        getThreadHistoryPage(projectId, selectedThreadId, { limit: 20 }).catch(() => []),
      ]);
      setSelectedThread(detail);
      setThreadState(state);
      setHistoryItems(history);
    } catch (requestError) {
      setDetailError(requestError instanceof Error ? requestError.message : "Failed to load thread detail");
      setSelectedThread(null);
      setThreadState(null);
      setHistoryItems([]);
    } finally {
      setDetailLoading(false);
    }
  }, [items, projectId, selectedThreadId]);

  useEffect(() => {
    let cancelled = false;
    async function loadFilterOptions() {
      if (!projectId) {
        setAssistantOptions([]);
        setGraphOptions([]);
        return;
      }
      try {
        const [assistantsPayload, graphsPayload] = await Promise.all([
          listAssistantsPage(projectId, {
            limit: 30,
            offset: 0,
            query: assistantFilter?.trim() || undefined,
          }).catch(() => ({ items: [], total: 0 })),
          listGraphsPage(projectId, {
            limit: 30,
            offset: 0,
            query: graphFilter?.trim() || undefined,
          }).catch(() => ({ items: [], total: 0, limit: 30, offset: 0 })),
        ]);
        if (cancelled) {
          return;
        }
        setAssistantOptions(assistantsPayload.items);
        setGraphOptions(graphsPayload.items);
      } catch {
        if (!cancelled) {
          setAssistantOptions([]);
          setGraphOptions([]);
        }
      }
    }

    void loadFilterOptions();

    return () => {
      cancelled = true;
    };
  }, [assistantFilter, graphFilter, projectId]);

  useEffect(() => {
    setPreviewQuery((prev) => (prev ? prev : initialQuery));
    setThreadIdQuery((prev) => (prev ? prev : initialThreadIdFilter));
    setAssistantFilter((prev) => (prev ? prev : initialAssistantFilter));
    setGraphFilter((prev) => (prev ? prev : initialGraphFilter));
    setStatusFilter((prev) => (prev ? prev : initialStatusFilter));
    setAppliedFilters((prev) =>
      (prev.assistantId || prev.graphId || prev.query || prev.threadId || prev.status) &&
      prev.assistantId === initialAssistantFilter &&
      prev.graphId === initialGraphFilter &&
      prev.query === initialQuery &&
      prev.threadId === initialThreadIdFilter &&
      prev.status === initialStatusFilter
        ? prev
        : {
            query: initialQuery,
            threadId: initialThreadIdFilter,
            assistantId: initialAssistantFilter,
            graphId: initialGraphFilter,
            status: initialStatusFilter,
          },
    );
  }, [initialAssistantFilter, initialGraphFilter, initialQuery, initialStatusFilter, initialThreadIdFilter]);

  useEffect(() => {
    void refreshList();
  }, [refreshList]);

  useEffect(() => {
    void refreshDetail();
  }, [refreshDetail]);

  const maxPage = Math.max(1, Math.ceil(total / pageSize));
  const currentPage = Math.min(maxPage, Math.floor(offset / pageSize) + 1);
  const messages = getThreadMessages(selectedThread, threadState);

  function applyCustomPage() {
    const parsed = Number(customPage);
    if (!Number.isFinite(parsed)) {
      return;
    }
    const normalizedPage = Math.max(1, Math.floor(parsed));
    setOffset((normalizedPage - 1) * pageSize);
    setCustomPage(String(normalizedPage));
  }

  function handleOpenInChat(nextThreadId: string) {
    const params = new URLSearchParams(searchParams.toString());
    const targetThread =
      selectedThread?.thread_id === nextThreadId
        ? selectedThread
        : items.find((item) => item.thread_id === nextThreadId) || null;
    const targetGraphId = getThreadGraphId(targetThread);
    const targetAssistantId = getThreadAssistantId(targetThread);

    params.set("threadId", nextThreadId);
    if (projectId) {
      params.set("projectId", projectId);
    }

    const nextTarget = normalizeChatTarget(
      targetGraphId
        ? {
            targetType: "graph",
            graphId: targetGraphId,
          }
        : targetAssistantId
          ? {
              targetType: "assistant",
              assistantId: targetAssistantId,
            }
          : graphFilter?.trim()
            ? {
                targetType: "graph",
                graphId: graphFilter.trim(),
              }
            : assistantFilter?.trim()
              ? {
                  targetType: "assistant",
                  assistantId: assistantFilter.trim(),
                }
              : null,
    );

    if (nextTarget) {
      applyChatTargetToSearchParams(params, nextTarget);
      if (projectId) {
        writeRecentChatTarget(projectId, nextTarget);
      }
    }

    router.push(`/workspace/chat?${params.toString()}`);
  }

  async function handleCopyThreadId(nextThreadId: string) {
    try {
      await navigator.clipboard.writeText(nextThreadId);
      toast.success("Thread ID copied");
    } catch {
      toast.error("Failed to copy thread ID");
    }
  }

  function handleSelectThread(item: ManagementThread) {
    setSelectedThreadId(item.thread_id);
    setSelectedThread(item);
    setDetailError(null);
    setDetailLoading(true);
  }

  return (
    <section className="grid gap-4 p-4 sm:p-6">
      <ThreadHistoryToolbar
        previewQuery={previewQuery}
        threadIdQuery={threadIdQuery}
        assistantFilter={assistantFilter}
        graphFilter={graphFilter}
        statusFilter={statusFilter}
        onPreviewQueryChange={setPreviewQuery}
        onThreadIdQueryChange={setThreadIdQuery}
        onAssistantFilterChange={setAssistantFilter}
        onGraphFilterChange={setGraphFilter}
        onStatusFilterChange={setStatusFilter}
        assistantOptions={assistantOptions}
        graphOptions={graphOptions}
        searching={searching}
        clearing={clearing}
        refreshing={refreshing}
        onSearch={async () => {
          const nextFilters = {
            query: previewQuery,
            threadId: threadIdQuery,
            assistantId: assistantFilter,
            graphId: graphFilter,
            status: statusFilter,
          };
          setSearching(true);
          setOffset(0);
          setCustomPage("1");
          setAppliedFilters(nextFilters);
          try {
            await refreshList({
              ...nextFilters,
              limit: pageSize,
              offset: 0,
            });
          } finally {
            setSearching(false);
          }
        }}
        onClear={async () => {
          setClearing(true);
          setOffset(0);
          setCustomPage("1");
          setPreviewQuery("");
          setThreadIdQuery("");
          setAssistantFilter("");
          setGraphFilter("");
          setStatusFilter("");
          setAppliedFilters({
            query: "",
            threadId: "",
            assistantId: "",
            graphId: "",
            status: "",
          });
          try {
            await refreshList({
              query: undefined,
              threadId: undefined,
              assistantId: undefined,
              graphId: undefined,
              status: undefined,
              limit: pageSize,
              offset: 0,
            });
            toast.success("Filters cleared");
          } finally {
            setClearing(false);
          }
        }}
        onRefresh={async () => {
          setRefreshing(true);
          setError(null);
          setDetailError(null);
          try {
            await Promise.all([refreshList(), refreshDetail()]);
            toast.success("Threads refreshed");
          } finally {
            setRefreshing(false);
          }
        }}
        loading={loading}
      />

      {projectId ? (
        <div className="grid items-start gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
          <ThreadListPanel
            items={items}
            selectedThreadId={selectedThreadId || undefined}
            loading={loading}
            total={total}
            limit={pageSize}
            offset={offset}
            error={error}
            customPage={customPage}
            currentPage={currentPage}
            maxPage={maxPage}
            onSelect={handleSelectThread}
            onPageSizeChange={(next) => {
              setOffset(0);
              setPageSize(next);
              setCustomPage("1");
            }}
            onCustomPageChange={setCustomPage}
            onApplyCustomPage={applyCustomPage}
            onPrevious={() => setOffset((prev) => Math.max(0, prev - pageSize))}
            onNext={() => setOffset((prev) => prev + pageSize)}
          />

          <ThreadDetailPanel
            thread={selectedThread}
            state={threadState}
            historyItems={historyItems}
            messages={messages}
            loading={detailLoading}
            error={detailError || error}
            onCopyThreadId={handleCopyThreadId}
            onOpenInChat={handleOpenInChat}
          />
        </div>
      ) : (
        <div className="rounded-lg border border-border/80 bg-card/70 p-4 text-sm text-muted-foreground">
          Select a project first. Thread history is always scoped to the current workspace project.
        </div>
      )}
    </section>
  );
}

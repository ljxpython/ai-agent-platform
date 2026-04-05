"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { DataPanel } from "@/components/platform/data-panel";
import { EmptyState } from "@/components/platform/empty-state";
import { PageHeader } from "@/components/platform/page-header";
import { PageActions } from "@/components/platform/page-actions";
import { PlatformPage } from "@/components/platform/platform-page";
import { StateBanner } from "@/components/platform/state-banner";
import { StatusPill } from "@/components/platform/status-pill";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  listGraphsPage,
  refreshGraphsCatalog,
  type ManagementGraph,
} from "@/lib/management-api/graphs";
import {
  buildChatHref,
  writeRecentChatTarget,
} from "@/lib/chat-target-preference";
import { useWorkspaceContext } from "@/providers/WorkspaceProvider";

function getSyncVariant(
  status: string,
): "success" | "warning" | "danger" | "neutral" {
  if (status === "synced" || status === "ready") {
    return "success";
  }
  if (status === "failed" || status === "error") {
    return "danger";
  }
  if (status === "pending") {
    return "warning";
  }
  return "neutral";
}

export default function GraphsPage() {
  const router = useRouter();
  const { currentProject, projectId } = useWorkspaceContext();
  const [items, setItems] = useState<ManagementGraph[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [pageSize] = useState(20);
  const [query, setQuery] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [lastSyncedAt, setLastSyncedAt] = useState<string | null>(null);

  const refreshList = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const payload = await listGraphsPage(projectId, {
        limit: pageSize,
        offset,
        query,
      });
      setItems(payload.items);
      setTotal(payload.total);
      setLastSyncedAt(payload.last_synced_at ?? null);
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Failed to load graphs",
      );
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [offset, pageSize, projectId, query]);

  useEffect(() => {
    void refreshList();
  }, [refreshList]);

  async function onRefreshCatalog() {
    setRefreshing(true);
    setError(null);
    setNotice(null);
    try {
      const payload = await refreshGraphsCatalog(projectId || undefined);
      setNotice(`Graph catalog refreshed: ${payload.count} item(s) synced`);
      await refreshList();
    } catch (refreshError) {
      setError(
        refreshError instanceof Error
          ? refreshError.message
          : "Failed to refresh graph catalog",
      );
    } finally {
      setRefreshing(false);
    }
  }

  const currentPage = Math.floor(offset / pageSize) + 1;
  const maxPage = Math.max(1, Math.ceil(total / pageSize));
  const syncedCount = useMemo(
    () =>
      items.filter(
        (item) => item.sync_status === "synced" || item.sync_status === "ready",
      ).length,
    [items],
  );

  return (
    <PlatformPage>
      <PageHeader
        actions={
          <PageActions>
            <Button
              disabled={refreshing}
              type="button"
              variant="ghost"
              onClick={() => void onRefreshCatalog()}
            >
              {refreshing ? "Refreshing..." : "Refresh catalog"}
            </Button>
          </PageActions>
        }
        description="图谱目录页先承接 catalog 可见性、搜索和快速跳转。助手配置已经依赖这套目录，所以不能继续留在旧平台里。"
        eyebrow="Advanced"
        title="Graphs"
      />

      <section className="grid gap-4 xl:grid-cols-4">
        <Card className="p-5">
          <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
            Current Project
          </div>
          <div className="mt-4 text-3xl font-semibold tracking-tight text-[var(--foreground)]">
            {currentProject?.name || "Unscoped"}
          </div>
        </Card>
        <Card className="p-5">
          <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
            Visible Rows
          </div>
          <div className="mt-4 text-3xl font-semibold tracking-tight text-[var(--foreground)]">
            {items.length}
          </div>
        </Card>
        <Card className="p-5">
          <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
            Synced
          </div>
          <div className="mt-4 text-3xl font-semibold tracking-tight text-[var(--foreground)]">
            {syncedCount}
          </div>
        </Card>
        <Card className="p-5">
          <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
            Last Synced
          </div>
          <div className="mt-4 text-sm leading-7 text-[var(--muted-foreground)]">
            {lastSyncedAt ? new Date(lastSyncedAt).toLocaleString() : "Never"}
          </div>
        </Card>
      </section>

      {notice ? <StateBanner message={notice} variant="success" /> : null}
      {error ? <StateBanner message={error} variant="error" /> : null}

      <DataPanel
        description="这里保留搜索、分页和两条常用跳转：直接打开 Chat，或者带图谱筛选跳到 Threads。"
        title="Graph Catalog"
        toolbar={
          <>
            <Input
              className="min-w-[280px]"
              placeholder="Search by graph ID, display name or description"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
            />
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                setOffset(0);
                setQuery(searchInput.trim());
              }}
            >
              Search
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                setOffset(0);
                setSearchInput("");
                setQuery("");
              }}
            >
              Clear
            </Button>
          </>
        }
      >
        {loading ? (
          <div className="text-sm text-[var(--muted-foreground)]">
            Loading graph catalog...
          </div>
        ) : null}

        {!loading && items.length === 0 ? (
          <EmptyState
            description="当前没有读取到图谱目录。可以尝试刷新 catalog，或者确认平台 API 与运行时同步链路是否正常。"
            title="No graphs found"
          />
        ) : null}

        {!loading && items.length > 0 ? (
          <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[1080px] border-collapse">
                <thead>
                  <tr
                    className="border-b"
                    style={{ borderColor: "var(--border)" }}
                  >
                    {[
                      "Graph",
                      "Display Name",
                      "Description",
                      "Source",
                      "Sync",
                      "Action",
                    ].map((label) => (
                      <th
                        key={label}
                        className="px-4 py-3 text-left text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase"
                      >
                        {label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr
                      key={item.graph_id}
                      className="border-b last:border-b-0"
                      style={{ borderColor: "var(--border)" }}
                    >
                      <td className="px-4 py-4 align-top">
                        <div className="font-semibold text-[var(--foreground)]">
                          {item.graph_id}
                        </div>
                        <div className="mt-1 text-xs text-[var(--muted-foreground)]">
                          {item.id}
                        </div>
                      </td>
                      <td className="px-4 py-4 align-top text-sm text-[var(--foreground)]">
                        {item.display_name || item.graph_id}
                      </td>
                      <td className="px-4 py-4 align-top text-sm leading-7 text-[var(--muted-foreground)]">
                        {item.description?.trim() || "No description"}
                      </td>
                      <td className="px-4 py-4 align-top text-sm text-[var(--muted-foreground)]">
                        {item.source_type || "-"}
                      </td>
                      <td className="px-4 py-4 align-top">
                        <div className="flex flex-col gap-2">
                          <StatusPill
                            label={item.sync_status || "unknown"}
                            variant={getSyncVariant(item.sync_status)}
                          />
                          <div className="text-xs text-[var(--muted-foreground)]">
                            {item.last_synced_at
                              ? new Date(item.last_synced_at).toLocaleString()
                              : "No sync timestamp"}
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-4 align-top">
                        <div className="flex flex-wrap gap-2">
                          <Button
                            size="sm"
                            type="button"
                            variant="ghost"
                            onClick={() => {
                              const target = {
                                targetType: "graph" as const,
                                graphId: item.graph_id,
                              };
                              if (projectId) {
                                writeRecentChatTarget(projectId, target);
                              }
                              router.push(
                                buildChatHref({
                                  projectId,
                                  target,
                                }),
                              );
                            }}
                          >
                            Open chat
                          </Button>
                          <Button asChild size="sm" variant="ghost">
                            <Link
                              href={`/workspace/threads?${new URLSearchParams({
                                ...(projectId ? { projectId } : {}),
                                threadGraphId: item.graph_id,
                              }).toString()}`}
                            >
                              View threads
                            </Link>
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
              <div className="text-sm text-[var(--muted-foreground)]">
                Page {currentPage} / {maxPage}
              </div>
              <div className="flex items-center gap-3">
                <Button
                  disabled={loading || offset === 0}
                  type="button"
                  variant="ghost"
                  onClick={() =>
                    setOffset((prev) => Math.max(0, prev - pageSize))
                  }
                >
                  Previous
                </Button>
                <Button
                  disabled={loading || offset + pageSize >= total}
                  type="button"
                  variant="ghost"
                  onClick={() => setOffset((prev) => prev + pageSize)}
                >
                  Next
                </Button>
              </div>
            </div>
          </>
        ) : null}
      </DataPanel>
    </PlatformPage>
  );
}

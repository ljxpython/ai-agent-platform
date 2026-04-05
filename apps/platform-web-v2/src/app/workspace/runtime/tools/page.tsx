"use client";

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
  listRuntimeTools,
  refreshRuntimeTools,
  type RuntimeToolItem,
} from "@/lib/management-api/runtime";

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

export default function RuntimeToolsPage() {
  const [items, setItems] = useState<RuntimeToolItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [lastSyncedAt, setLastSyncedAt] = useState<string | null>(null);

  const refreshList = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const payload = await listRuntimeTools();
      setItems(Array.isArray(payload.tools) ? payload.tools : []);
      setLastSyncedAt(payload.last_synced_at ?? null);
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Failed to load runtime tools",
      );
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshList();
  }, [refreshList]);

  async function onRefreshCatalog() {
    setRefreshing(true);
    setError(null);
    setNotice(null);
    try {
      const payload = await refreshRuntimeTools();
      setNotice(`Runtime tools refreshed: ${payload.count} item(s) synced`);
      await refreshList();
    } catch (refreshError) {
      setError(
        refreshError instanceof Error
          ? refreshError.message
          : "Failed to refresh runtime tools",
      );
    } finally {
      setRefreshing(false);
    }
  }

  const filteredItems = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) {
      return items;
    }
    return items.filter((item) => {
      return (
        item.name.toLowerCase().includes(normalized) ||
        item.source.toLowerCase().includes(normalized) ||
        item.description.toLowerCase().includes(normalized)
      );
    });
  }, [items, query]);

  const uniqueSources = useMemo(
    () => new Set(items.map((item) => item.source).filter(Boolean)).size,
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
        description="工具目录页承接 source、description 和同步状态，让助手配置时不再摸黑选工具。"
        eyebrow="Advanced"
        title="Runtime Tools"
      />

      <section className="grid gap-4 xl:grid-cols-4">
        <Card className="p-5">
          <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
            Tools
          </div>
          <div className="mt-4 text-3xl font-semibold tracking-tight text-[var(--foreground)]">
            {items.length}
          </div>
        </Card>
        <Card className="p-5">
          <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
            Sources
          </div>
          <div className="mt-4 text-3xl font-semibold tracking-tight text-[var(--foreground)]">
            {uniqueSources}
          </div>
        </Card>
        <Card className="p-5">
          <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
            Visible Rows
          </div>
          <div className="mt-4 text-3xl font-semibold tracking-tight text-[var(--foreground)]">
            {filteredItems.length}
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
        description="工具目录页先解决查找、过滤和来源识别，避免助手接工具时还要回旧页面翻资料。"
        title="Tool Catalog"
        toolbar={
          <>
            <Input
              className="min-w-[280px]"
              placeholder="Search by name, source or description"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
            />
            <Button
              type="button"
              variant="ghost"
              onClick={() => setQuery(searchInput.trim())}
            >
              Search
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
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
            Loading runtime tools...
          </div>
        ) : null}

        {!loading && filteredItems.length === 0 ? (
          <EmptyState
            description={
              items.length === 0
                ? "当前 runtime 没有返回任何工具目录。"
                : "没有工具命中当前搜索条件。"
            }
            title="No tools found"
          />
        ) : null}

        {!loading && filteredItems.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1120px] border-collapse">
              <thead>
                <tr
                  className="border-b"
                  style={{ borderColor: "var(--border)" }}
                >
                  {["Tool", "Source", "Description", "Runtime", "Sync"].map(
                    (label) => (
                      <th
                        key={label}
                        className="px-4 py-3 text-left text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase"
                      >
                        {label}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((item) => (
                  <tr
                    key={`${item.source}:${item.name}:${item.tool_key}`}
                    className="border-b last:border-b-0"
                    style={{ borderColor: "var(--border)" }}
                  >
                    <td className="px-4 py-4 align-top">
                      <div className="font-mono text-xs text-[var(--foreground)]">
                        {item.name}
                      </div>
                      <div className="mt-1 text-xs text-[var(--muted-foreground)]">
                        {item.tool_key}
                      </div>
                    </td>
                    <td className="px-4 py-4 align-top text-sm text-[var(--muted-foreground)]">
                      {item.source || "-"}
                    </td>
                    <td className="px-4 py-4 align-top text-sm leading-7 text-[var(--muted-foreground)]">
                      {item.description?.trim() || "No description"}
                    </td>
                    <td className="px-4 py-4 align-top text-sm text-[var(--muted-foreground)]">
                      {item.runtime_id || "-"}
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
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </DataPanel>
    </PlatformPage>
  );
}

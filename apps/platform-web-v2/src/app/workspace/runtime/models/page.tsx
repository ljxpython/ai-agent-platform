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
  listRuntimeModels,
  refreshRuntimeModels,
  type RuntimeModelItem,
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

export default function RuntimeModelsPage() {
  const [items, setItems] = useState<RuntimeModelItem[]>([]);
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
      const payload = await listRuntimeModels();
      setItems(Array.isArray(payload.models) ? payload.models : []);
      setLastSyncedAt(payload.last_synced_at ?? null);
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Failed to load runtime models",
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
      const payload = await refreshRuntimeModels();
      setNotice(`Runtime models refreshed: ${payload.count} item(s) synced`);
      await refreshList();
    } catch (refreshError) {
      setError(
        refreshError instanceof Error
          ? refreshError.message
          : "Failed to refresh runtime models",
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
        item.model_id.toLowerCase().includes(normalized) ||
        item.display_name.toLowerCase().includes(normalized)
      );
    });
  }, [items, query]);

  const defaultCount = useMemo(
    () => items.filter((item) => item.is_default).length,
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
        description="模型目录页先承接 runtime 暴露的模型清单、默认项和同步状态。助手创建页会直接消费这些数据。"
        eyebrow="Advanced"
        title="Runtime Models"
      />

      <section className="grid gap-4 xl:grid-cols-4">
        <Card className="p-5">
          <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
            Models
          </div>
          <div className="mt-4 text-3xl font-semibold tracking-tight text-[var(--foreground)]">
            {items.length}
          </div>
        </Card>
        <Card className="p-5">
          <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
            Default Models
          </div>
          <div className="mt-4 text-3xl font-semibold tracking-tight text-[var(--foreground)]">
            {defaultCount}
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
        description="这里保留模型搜索和同步状态，先把最常见的 runtime 可见性问题收回来。"
        title="Model Catalog"
        toolbar={
          <>
            <Input
              className="min-w-[280px]"
              placeholder="Search by model ID or display name"
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
            Loading runtime models...
          </div>
        ) : null}

        {!loading && filteredItems.length === 0 ? (
          <EmptyState
            description={
              items.length === 0
                ? "当前 runtime 没有返回任何模型目录。"
                : "没有模型命中当前搜索条件。"
            }
            title="No models found"
          />
        ) : null}

        {!loading && filteredItems.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[980px] border-collapse">
              <thead>
                <tr
                  className="border-b"
                  style={{ borderColor: "var(--border)" }}
                >
                  {[
                    "Model ID",
                    "Display Name",
                    "Default",
                    "Runtime",
                    "Sync",
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
                {filteredItems.map((item) => (
                  <tr
                    key={item.model_id}
                    className="border-b last:border-b-0"
                    style={{ borderColor: "var(--border)" }}
                  >
                    <td className="px-4 py-4 align-top font-mono text-xs text-[var(--muted-foreground)]">
                      {item.model_id}
                    </td>
                    <td className="px-4 py-4 align-top text-sm text-[var(--foreground)]">
                      {item.display_name}
                    </td>
                    <td className="px-4 py-4 align-top">
                      {item.is_default ? (
                        <StatusPill label="default" variant="success" />
                      ) : (
                        <StatusPill label="no" variant="neutral" />
                      )}
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

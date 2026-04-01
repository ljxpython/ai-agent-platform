"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

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
  listAssistantsPage,
  type ManagementAssistant,
} from "@/lib/management-api/assistants";
import { useWorkspaceContext } from "@/providers/WorkspaceProvider";

function getAssistantStatusVariant(
  status: string,
): "success" | "warning" | "neutral" {
  if (status === "active") {
    return "success";
  }
  if (status === "disabled") {
    return "warning";
  }
  return "neutral";
}

function getSyncStatusVariant(
  status: string,
): "success" | "warning" | "danger" | "neutral" {
  if (status === "synced" || status === "ready") {
    return "success";
  }
  if (status === "failed") {
    return "danger";
  }
  if (status === "pending") {
    return "warning";
  }
  return "neutral";
}

export default function AssistantsPage() {
  const { currentProject, projectId } = useWorkspaceContext();
  const [items, setItems] = useState<ManagementAssistant[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [pageSize] = useState(20);
  const [query, setQuery] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function refresh() {
      if (!projectId) {
        setItems([]);
        setTotal(0);
        return;
      }

      setLoading(true);
      setError(null);
      try {
        const payload = await listAssistantsPage(projectId, {
          limit: pageSize,
          offset,
          query,
        });
        if (cancelled) {
          return;
        }
        setItems(payload.items);
        setTotal(payload.total);
      } catch (fetchError) {
        if (!cancelled) {
          setError(
            fetchError instanceof Error
              ? fetchError.message
              : "Failed to load assistants",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void refresh();

    return () => {
      cancelled = true;
    };
  }, [offset, pageSize, projectId, query]);

  const currentPage = Math.floor(offset / pageSize) + 1;
  const maxPage = Math.max(1, Math.ceil(total / pageSize));
  const activeCount = useMemo(
    () => items.filter((item) => item.status === "active").length,
    [items],
  );

  return (
    <PlatformPage>
      <PageHeader
        actions={
          <PageActions>
            {projectId ? (
              <Button asChild variant="primary">
                <Link href="/workspace/assistants/new">Create assistant</Link>
              </Button>
            ) : (
              <Button disabled variant="primary">
                Create assistant
              </Button>
            )}
          </PageActions>
        }
        description="助手页已经进入真实迁移阶段。列表、详情、新建都会依赖当前项目上下文，后续图谱、线程和 runtime 也沿用这一套工作方式。"
        eyebrow="Workspace"
        title="Assistants"
      />

      <section className="grid gap-4 xl:grid-cols-4">
        {[
          ["Current Project", currentProject?.name || "未选择项目"],
          ["Visible Rows", String(items.length)],
          ["Active Assistants", String(activeCount)],
          ["Total", String(total)],
        ].map(([label, value]) => (
          <Card key={label} className="p-5">
            <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
              {label}
            </div>
            <div className="mt-4 text-4xl font-semibold tracking-tight text-[var(--foreground)]">
              {value}
            </div>
          </Card>
        ))}
      </section>

      {error ? <StateBanner message={error} variant="error" /> : null}

      {!projectId ? (
        <EmptyState
          description="当前没有选中项目，所以无法读取助手列表。请先到 Projects 页面选择一个当前项目，或在顶部项目选择器中直接切换。"
          title="No project selected"
        />
      ) : (
        <DataPanel
          description="这里先承接助手列表、搜索、同步状态和项目上下文。更复杂的编辑、resync 和 runtime 能力后续再逐步迁移。"
          title="Assistant Registry"
          toolbar={
            <>
              <Input
                className="min-w-[260px]"
                placeholder="Search by name, graph ID or description"
                value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
              />
              <Button
                onClick={() => {
                  setOffset(0);
                  setQuery(searchInput.trim());
                }}
                variant="ghost"
              >
                Search
              </Button>
              <Button
                onClick={() => {
                  setOffset(0);
                  setSearchInput("");
                  setQuery("");
                }}
                variant="ghost"
              >
                Clear
              </Button>
            </>
          }
        >
          {loading ? (
            <div className="text-sm text-[var(--muted-foreground)]">
              Loading assistants...
            </div>
          ) : null}

          {!loading && items.length === 0 ? (
            <EmptyState
              description="当前项目下还没有读取到助手。请先在旧平台或后续迁移完成后的新页面里创建助手。"
              title="No assistants found"
            />
          ) : null}

          {!loading && items.length > 0 ? (
            <>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[980px] border-collapse">
                  <thead>
                    <tr
                      className="border-b"
                      style={{ borderColor: "var(--border)" }}
                    >
                      {[
                        "Assistant",
                        "Graph",
                        "Status",
                        "Sync",
                        "Runtime",
                        "Updated",
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
                        key={item.id}
                        className="border-b last:border-b-0"
                        style={{ borderColor: "var(--border)" }}
                      >
                        <td className="px-4 py-4 align-top">
                          <div className="font-semibold text-[var(--foreground)]">
                            {item.name}
                          </div>
                          <div className="mt-1 text-sm text-[var(--muted-foreground)]">
                            {item.description || "No description"}
                          </div>
                        </td>
                        <td className="px-4 py-4 align-top text-sm text-[var(--muted-foreground)]">
                          {item.graph_id}
                        </td>
                        <td className="px-4 py-4 align-top">
                          <StatusPill
                            label={item.status}
                            variant={getAssistantStatusVariant(item.status)}
                          />
                        </td>
                        <td className="px-4 py-4 align-top">
                          <StatusPill
                            label={item.sync_status || "unknown"}
                            variant={getSyncStatusVariant(item.sync_status)}
                          />
                        </td>
                        <td className="px-4 py-4 align-top text-sm text-[var(--muted-foreground)]">
                          {item.runtime_base_url || "-"}
                        </td>
                        <td className="px-4 py-4 align-top text-sm text-[var(--muted-foreground)]">
                          {item.updated_at || item.last_synced_at || "-"}
                        </td>
                        <td className="px-4 py-4 align-top">
                          <Button asChild size="sm" variant="ghost">
                            <Link href={`/workspace/assistants/${item.id}`}>
                              Details
                            </Link>
                          </Button>
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
                    onClick={() =>
                      setOffset((prev) => Math.max(0, prev - pageSize))
                    }
                    variant="ghost"
                  >
                    Previous
                  </Button>
                  <Button
                    disabled={loading || offset + pageSize >= total}
                    onClick={() => setOffset((prev) => prev + pageSize)}
                    variant="ghost"
                  >
                    Next
                  </Button>
                </div>
              </div>
            </>
          ) : null}
        </DataPanel>
      )}
    </PlatformPage>
  );
}

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
  listProjectsPage,
  type ManagementProject,
} from "@/lib/management-api/projects";
import { cn } from "@/lib/utils/cn";
import { useWorkspaceContext } from "@/providers/WorkspaceProvider";

function getProjectStatusVariant(
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

export default function ProjectsPage() {
  const { currentProject, projectId, setProjectId } = useWorkspaceContext();
  const [items, setItems] = useState<ManagementProject[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [pageSize] = useState(20);
  const [query, setQuery] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function refresh() {
      setLoading(true);
      setError(null);
      try {
        const payload = await listProjectsPage({
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
              : "Failed to load projects",
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
  }, [offset, pageSize, query]);

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
            <Button asChild variant="primary">
              <Link href="/workspace/projects/new">New project</Link>
            </Button>
          </PageActions>
        }
        description="项目页已经接入读取、搜索、详情和当前项目切换。后续成员管理会继续沿着这套版式补齐，不会再回到旧平台那种散乱入口。"
        eyebrow="Workspace"
        title="Projects"
      />

      <section className="grid gap-4 xl:grid-cols-4">
        {[
          ["Current Project", currentProject?.name || "未选择项目"],
          ["Visible Rows", String(items.length)],
          ["Active Projects", String(activeCount)],
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

      {notice ? <StateBanner message={notice} variant="success" /> : null}
      {error ? <StateBanner message={error} variant="error" /> : null}

      <DataPanel
        description="搜索、切页和项目切换已经接到 v2。当前项目会直接进入全局 workspace context，供 assistants 等页面复用。"
        title="Project Registry"
        toolbar={
          <>
            <Input
              className="min-w-[280px]"
              placeholder="Search by project name or description"
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
            Loading projects...
          </div>
        ) : null}

        {!loading && items.length === 0 ? (
          <EmptyState
            description="当前没有读取到任何项目。请确认平台 API 已启动，或者先使用旧平台创建至少一个项目。"
            title="No projects found"
          />
        ) : null}

        {!loading && items.length > 0 ? (
          <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[860px] border-collapse">
                <thead>
                  <tr
                    className="border-b"
                    style={{ borderColor: "var(--border)" }}
                  >
                    {[
                      "Project",
                      "Description",
                      "Status",
                      "Context",
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
                  {items.map((item) => {
                    const isCurrent = item.id === projectId;
                    return (
                      <tr
                        key={item.id}
                        className="border-b last:border-b-0"
                        style={{ borderColor: "var(--border)" }}
                      >
                        <td className="px-4 py-4 align-top">
                          <div className="font-semibold text-[var(--foreground)]">
                            {item.name}
                          </div>
                          <div className="mt-1 text-xs text-[var(--muted-foreground)]">
                            {item.id}
                          </div>
                        </td>
                        <td className="px-4 py-4 align-top text-sm leading-7 text-[var(--muted-foreground)]">
                          {item.description || "No description"}
                        </td>
                        <td className="px-4 py-4 align-top">
                          <StatusPill
                            label={item.status}
                            variant={getProjectStatusVariant(item.status)}
                          />
                        </td>
                        <td className="px-4 py-4 align-top">
                          <span
                            className={cn(
                              "inline-flex min-h-7 items-center rounded-full px-3 text-xs font-bold tracking-[0.08em] uppercase",
                            )}
                            style={
                              isCurrent
                                ? {
                                    background:
                                      "var(--status-success-background)",
                                    color: "var(--status-success-foreground)",
                                  }
                                : {
                                    background:
                                      "var(--status-neutral-background)",
                                    color: "var(--status-neutral-foreground)",
                                  }
                            }
                          >
                            {isCurrent ? "current" : "available"}
                          </span>
                        </td>
                        <td className="px-4 py-4 align-top">
                          <div className="flex flex-wrap gap-2">
                            <Button
                              disabled={isCurrent}
                              onClick={() => {
                                setProjectId(item.id);
                                setNotice(
                                  `Switched current project to ${item.name}`,
                                );
                              }}
                              size="sm"
                              variant="ghost"
                            >
                              {isCurrent ? "Selected" : "Use project"}
                            </Button>
                            <Button asChild size="sm" variant="ghost">
                              <Link href={`/workspace/projects/${item.id}`}>
                                Details
                              </Link>
                            </Button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
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
    </PlatformPage>
  );
}

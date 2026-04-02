"use client";

import { useEffect, useMemo, useState } from "react";

import { DataPanel } from "@/components/platform/data-panel";
import { EmptyState } from "@/components/platform/empty-state";
import { ErrorState } from "@/components/platform/error-state";
import { PageHeader } from "@/components/platform/page-header";
import { PageActions } from "@/components/platform/page-actions";
import { PlatformPage } from "@/components/platform/platform-page";
import { StateBanner } from "@/components/platform/state-banner";
import { StatusPill } from "@/components/platform/status-pill";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { listAudit, type ManagementAuditRow } from "@/lib/management-api/audit";
import { useWorkspaceContext } from "@/providers/WorkspaceProvider";

function getStatusVariant(
  statusCode: number,
): "success" | "warning" | "danger" | "neutral" {
  if (statusCode >= 500) {
    return "danger";
  }
  if (statusCode >= 400) {
    return "warning";
  }
  if (statusCode >= 200 && statusCode < 400) {
    return "success";
  }
  return "neutral";
}

export default function AuditPage() {
  const { canAccessAudit, currentProject, currentProjectRole, projectId } =
    useWorkspaceContext();
  const [items, setItems] = useState<ManagementAuditRow[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [pageSize, setPageSize] = useState(50);
  const [scope, setScope] = useState<"project" | "global">(
    projectId ? "project" : "global",
  );
  const [actionInput, setActionInput] = useState("");
  const [targetTypeInput, setTargetTypeInput] = useState("");
  const [targetIdInput, setTargetIdInput] = useState("");
  const [methodInput, setMethodInput] = useState("");
  const [statusCodeInput, setStatusCodeInput] = useState("");
  const [actionFilter, setActionFilter] = useState("");
  const [targetTypeFilter, setTargetTypeFilter] = useState("");
  const [targetIdFilter, setTargetIdFilter] = useState("");
  const [methodFilter, setMethodFilter] = useState("");
  const [statusCodeFilter, setStatusCodeFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId) {
      setScope("global");
    }
  }, [projectId]);

  useEffect(() => {
    if (!canAccessAudit) {
      setItems([]);
      setTotal(0);
      setLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;

    async function loadAudit() {
      setLoading(true);
      setError(null);
      try {
        const payload = await listAudit(
          scope === "project" ? projectId || null : null,
          {
            limit: pageSize,
            offset,
            action: actionFilter,
            targetType: targetTypeFilter,
            targetId: targetIdFilter,
            method: methodFilter,
            statusCode: statusCodeFilter.trim()
              ? Number(statusCodeFilter)
              : null,
          },
        );
        if (!cancelled) {
          setItems(payload.items);
          setTotal(payload.total);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : "Failed to load audit logs",
          );
          setItems([]);
          setTotal(0);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadAudit();
    return () => {
      cancelled = true;
    };
  }, [
    actionFilter,
    methodFilter,
    offset,
    pageSize,
    projectId,
    scope,
    statusCodeFilter,
    targetIdFilter,
    targetTypeFilter,
    canAccessAudit,
  ]);

  const currentPage = Math.floor(offset / pageSize) + 1;
  const maxPage = Math.max(1, Math.ceil(total / pageSize));
  const errorCount = useMemo(
    () => items.filter((item) => item.status_code >= 400).length,
    [items],
  );

  if (!canAccessAudit) {
    return (
      <PlatformPage>
        <PageHeader
          description="审计页只对具备审计权限的账号开放。普通执行账号不再硬闯接口然后吃一脸 403。"
          eyebrow="Advanced"
          title="Audit"
        />

        <ErrorState
          description={`当前账号没有审计查看权限。请切换到管理员账号后再查看。当前项目角色：${currentProjectRole || "none"}`}
          title="Audit access required"
        />
      </PlatformPage>
    );
  }

  return (
    <PlatformPage>
      <PageHeader
        actions={
          <PageActions>
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                setOffset(0);
                setActionFilter(actionInput.trim());
                setTargetTypeFilter(targetTypeInput.trim());
                setTargetIdFilter(targetIdInput.trim());
                setMethodFilter(methodInput.trim());
                setStatusCodeFilter(statusCodeInput.trim());
              }}
            >
              Apply filters
            </Button>
          </PageActions>
        }
        description="审计页先承接 project/global 维度的日志查看、筛选和分页。后续更复杂的审计详情再继续补。"
        eyebrow="Advanced"
        title="Audit"
      />

      <section className="grid gap-4 xl:grid-cols-4">
        <Card className="p-5">
          <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
            Scope
          </div>
          <div className="mt-4 text-3xl font-semibold tracking-tight text-[var(--foreground)]">
            {scope === "project" ? "Project" : "Global"}
          </div>
        </Card>
        <Card className="p-5">
          <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
            Current Project
          </div>
          <div className="mt-4 text-3xl font-semibold tracking-tight text-[var(--foreground)]">
            {currentProject?.name || "None"}
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
            Errors
          </div>
          <div className="mt-4 text-3xl font-semibold tracking-tight text-[var(--foreground)]">
            {errorCount}
          </div>
        </Card>
      </section>

      {error ? <StateBanner message={error} variant="error" /> : null}

      <DataPanel
        description="项目日志默认跟随当前 workspace project，也可以切到全局视角。全局视角要求当前账号本身有管理员权限。"
        title="Audit Filters"
      >
        <div className="grid gap-4 xl:grid-cols-6">
          <label className="grid gap-2 text-sm font-medium text-[var(--foreground)]">
            Scope
            <Select
              disabled={!projectId}
              value={scope}
              onChange={(event) => {
                setOffset(0);
                setScope(event.target.value as "project" | "global");
              }}
            >
              <option value="project">Current project</option>
              <option value="global">Global</option>
            </Select>
          </label>
          <label className="grid gap-2 text-sm font-medium text-[var(--foreground)]">
            Action
            <Input
              value={actionInput}
              onChange={(event) => setActionInput(event.target.value)}
            />
          </label>
          <label className="grid gap-2 text-sm font-medium text-[var(--foreground)]">
            Target Type
            <Input
              value={targetTypeInput}
              onChange={(event) => setTargetTypeInput(event.target.value)}
            />
          </label>
          <label className="grid gap-2 text-sm font-medium text-[var(--foreground)]">
            Target ID
            <Input
              value={targetIdInput}
              onChange={(event) => setTargetIdInput(event.target.value)}
            />
          </label>
          <label className="grid gap-2 text-sm font-medium text-[var(--foreground)]">
            Method
            <Select
              value={methodInput}
              onChange={(event) => setMethodInput(event.target.value)}
            >
              <option value="">All</option>
              <option value="GET">GET</option>
              <option value="POST">POST</option>
              <option value="PATCH">PATCH</option>
              <option value="DELETE">DELETE</option>
              <option value="PUT">PUT</option>
            </Select>
          </label>
          <label className="grid gap-2 text-sm font-medium text-[var(--foreground)]">
            Status Code
            <Input
              value={statusCodeInput}
              onChange={(event) => setStatusCodeInput(event.target.value)}
            />
          </label>
        </div>

        <PageActions className="mt-5">
          <Button
            type="button"
            variant="primary"
            onClick={() => {
              setOffset(0);
              setActionFilter(actionInput.trim());
              setTargetTypeFilter(targetTypeInput.trim());
              setTargetIdFilter(targetIdInput.trim());
              setMethodFilter(methodInput.trim());
              setStatusCodeFilter(statusCodeInput.trim());
            }}
          >
            Apply filters
          </Button>
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              setOffset(0);
              setActionInput("");
              setTargetTypeInput("");
              setTargetIdInput("");
              setMethodInput("");
              setStatusCodeInput("");
              setActionFilter("");
              setTargetTypeFilter("");
              setTargetIdFilter("");
              setMethodFilter("");
              setStatusCodeFilter("");
            }}
          >
            Clear
          </Button>
          <label className="ml-auto grid gap-2 text-sm font-medium text-[var(--foreground)]">
            Page Size
            <Select
              value={String(pageSize)}
              onChange={(event) => {
                setOffset(0);
                setPageSize(Number(event.target.value));
              }}
            >
              {[20, 50, 100].map((size) => (
                <option key={size} value={String(size)}>
                  {size}
                </option>
              ))}
            </Select>
          </label>
        </PageActions>
      </DataPanel>

      <DataPanel
        description="当前先展示关键请求维度：时间、方法、路径、状态、动作和目标。"
        title="Audit Logs"
      >
        {loading ? (
          <div className="text-sm text-[var(--muted-foreground)]">
            Loading audit logs...
          </div>
        ) : null}

        {!loading && items.length === 0 ? (
          <EmptyState
            description="当前没有审计日志，或者当前过滤条件没有命中任何记录。"
            title="No audit logs found"
          />
        ) : null}

        {!loading && items.length > 0 ? (
          <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[1180px] border-collapse">
                <thead>
                  <tr
                    className="border-b"
                    style={{ borderColor: "var(--border)" }}
                  >
                    {[
                      "Time",
                      "Method",
                      "Path",
                      "Status",
                      "Action",
                      "Target",
                      "Request ID",
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
                  {items.map((row) => (
                    <tr
                      key={row.id}
                      className="border-b last:border-b-0"
                      style={{ borderColor: "var(--border)" }}
                    >
                      <td className="px-4 py-4 align-top text-sm text-[var(--muted-foreground)]">
                        {new Date(row.created_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-4 align-top">
                        <StatusPill label={row.method} variant="neutral" />
                      </td>
                      <td className="px-4 py-4 align-top font-mono text-xs text-[var(--muted-foreground)]">
                        {row.path}
                      </td>
                      <td className="px-4 py-4 align-top">
                        <StatusPill
                          label={String(row.status_code)}
                          variant={getStatusVariant(row.status_code)}
                        />
                      </td>
                      <td className="px-4 py-4 align-top text-sm text-[var(--foreground)]">
                        {row.action || "-"}
                      </td>
                      <td className="px-4 py-4 align-top text-sm text-[var(--muted-foreground)]">
                        {row.target_type
                          ? `${row.target_type}:${row.target_id ?? "-"}`
                          : "-"}
                      </td>
                      <td className="px-4 py-4 align-top font-mono text-xs text-[var(--muted-foreground)]">
                        {row.request_id}
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

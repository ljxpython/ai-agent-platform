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
import { listUsersPage, type ManagementUser } from "@/lib/management-api/users";

export default function UsersPage() {
  const [items, setItems] = useState<ManagementUser[]>([]);
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
      setLoading(true);
      setError(null);
      try {
        const payload = await listUsersPage({ limit: pageSize, offset, query });
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
              : "Failed to load users",
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
  const superAdminCount = useMemo(
    () => items.filter((item) => item.is_super_admin).length,
    [items],
  );

  return (
    <PlatformPage>
      <PageHeader
        actions={
          <PageActions>
            <Button asChild variant="primary">
              <Link href="/workspace/users/new">Create user</Link>
            </Button>
          </PageActions>
        }
        description="用户页现在不只是列表壳子，已经开始承接新建和详情入口。账号状态、管理员身份和密码更新会继续在 v2 里闭环。"
        eyebrow="Workspace"
        title="Users"
      />

      <section className="grid gap-4 xl:grid-cols-4">
        {[
          ["Visible Rows", String(items.length)],
          ["Active Users", String(activeCount)],
          ["Super Admins", String(superAdminCount)],
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

      <DataPanel
        description="当前先迁系统级用户列表、状态展示和搜索。页面母版、卡片层级和操作区都已切进 v2 的新视觉体系。"
        title="User Registry"
        toolbar={
          <>
            <Input
              className="min-w-[260px]"
              placeholder="Search by username"
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
            Loading users...
          </div>
        ) : null}

        {!loading && items.length === 0 ? (
          <EmptyState
            description="当前没有读取到任何用户数据。请先确认平台 API 与鉴权链路可用。"
            title="No users found"
          />
        ) : null}

        {!loading && items.length > 0 ? (
          <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] border-collapse">
                <thead>
                  <tr
                    className="border-b"
                    style={{ borderColor: "var(--border)" }}
                  >
                    {[
                      "Username",
                      "Status",
                      "Super Admin",
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
                          {item.username}
                        </div>
                        <div className="mt-1 text-xs text-[var(--muted-foreground)]">
                          {item.id}
                        </div>
                      </td>
                      <td className="px-4 py-4 align-top">
                        <StatusPill
                          label={item.status}
                          variant={
                            item.status === "active" ? "success" : "warning"
                          }
                        />
                      </td>
                      <td className="px-4 py-4 align-top">
                        <StatusPill
                          label={item.is_super_admin ? "yes" : "no"}
                          variant={item.is_super_admin ? "neutral" : "warning"}
                        />
                      </td>
                      <td className="px-4 py-4 align-top text-sm text-[var(--muted-foreground)]">
                        {item.updated_at || item.created_at || "-"}
                      </td>
                      <td className="px-4 py-4 align-top">
                        <Button asChild size="sm" variant="ghost">
                          <Link href={`/workspace/users/${item.id}`}>
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
    </PlatformPage>
  );
}

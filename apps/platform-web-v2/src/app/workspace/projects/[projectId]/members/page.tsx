"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { ConfirmDialog } from "@/components/platform/confirm-dialog";
import { DataPanel } from "@/components/platform/data-panel";
import { EmptyState } from "@/components/platform/empty-state";
import { FormSection } from "@/components/platform/form-section";
import { PageHeader } from "@/components/platform/page-header";
import { PageActions } from "@/components/platform/page-actions";
import { PlatformPage } from "@/components/platform/platform-page";
import { StateBanner } from "@/components/platform/state-banner";
import { StatusPill } from "@/components/platform/status-pill";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import {
  deleteMember,
  listMembers,
  upsertMember,
  type ManagementProjectMember,
} from "@/lib/management-api/members";
import { listUsersPage, type ManagementUser } from "@/lib/management-api/users";
import { useWorkspaceContext } from "@/providers/WorkspaceProvider";

export default function ProjectMembersPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = String(params.projectId || "");
  const {
    projectId: currentProjectId,
    projects,
    setProjectId,
  } = useWorkspaceContext();

  const project = projects.find((item) => item.id === projectId) ?? null;
  const isCurrentProject = projectId === currentProjectId;

  const [items, setItems] = useState<ManagementProjectMember[]>([]);
  const [memberQuery, setMemberQuery] = useState("");
  const [memberSearchInput, setMemberSearchInput] = useState("");
  const [userId, setUserId] = useState("");
  const [userSearch, setUserSearch] = useState("");
  const [userCandidates, setUserCandidates] = useState<ManagementUser[]>([]);
  const [searchingUsers, setSearchingUsers] = useState(false);
  const [role, setRole] = useState<"admin" | "editor" | "executor">("executor");
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [removingUserId, setRemovingUserId] = useState<string | null>(null);
  const [pendingDeleteMember, setPendingDeleteMember] =
    useState<ManagementProjectMember | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const existingMemberUserIds = useMemo(
    () => new Set(items.map((item) => item.user_id)),
    [items],
  );
  const adminCount = items.filter((item) => item.role === "admin").length;
  const targetExistingMember = items.find(
    (item) => item.user_id === userId.trim(),
  );
  const downgradeLastAdminBlocked =
    targetExistingMember?.role === "admin" &&
    role !== "admin" &&
    adminCount <= 1;

  const refreshMembers = useCallback(async () => {
    if (!projectId) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const rows = await listMembers(projectId, { query: memberQuery });
      setItems(rows);
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Failed to load members",
      );
    } finally {
      setLoading(false);
    }
  }, [memberQuery, projectId]);

  useEffect(() => {
    void refreshMembers();
  }, [refreshMembers]);

  useEffect(() => {
    let cancelled = false;

    if (!userSearch.trim()) {
      setUserCandidates([]);
      return () => {
        cancelled = true;
      };
    }

    const timerId = window.setTimeout(async () => {
      setSearchingUsers(true);
      try {
        const payload = await listUsersPage({
          limit: 20,
          offset: 0,
          query: userSearch,
          status: "active",
          excludeUserIds: Array.from(existingMemberUserIds),
        });
        if (!cancelled) {
          setUserCandidates(
            payload.items.filter(
              (candidate) => !existingMemberUserIds.has(candidate.id),
            ),
          );
        }
      } catch {
        if (!cancelled) {
          setUserCandidates([]);
        }
      } finally {
        if (!cancelled) {
          setSearchingUsers(false);
        }
      }
    }, 250);

    return () => {
      cancelled = true;
      window.clearTimeout(timerId);
    };
  }, [existingMemberUserIds, userSearch]);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!projectId || !userId.trim()) {
      setError("Project and user are required");
      return;
    }
    if (downgradeLastAdminBlocked) {
      setError("Cannot downgrade the last project admin");
      return;
    }

    setSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const row = await upsertMember({
        projectId,
        userId: userId.trim(),
        role,
      });
      setNotice(`Saved member: ${row.username}`);
      setUserId("");
      setUserSearch("");
      setRole("executor");
      setUserCandidates([]);
      await refreshMembers();
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Failed to save member",
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function onDelete(member: ManagementProjectMember) {
    setRemovingUserId(member.user_id);
    setError(null);
    setNotice(null);
    try {
      await deleteMember(projectId, member.user_id);
      setNotice(`Removed member: ${member.username}`);
      await refreshMembers();
    } catch (deleteError) {
      setError(
        deleteError instanceof Error
          ? deleteError.message
          : "Failed to remove member",
      );
    } finally {
      setRemovingUserId(null);
      setPendingDeleteMember((current) =>
        current?.user_id === member.user_id ? null : current,
      );
    }
  }

  return (
    <PlatformPage>
      <PageHeader
        actions={
          <PageActions>
            <Button asChild variant="ghost">
              <Link href={`/workspace/projects/${projectId}`}>
                Back to project
              </Link>
            </Button>
            {!isCurrentProject ? (
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  setProjectId(projectId);
                }}
              >
                Use as current project
              </Button>
            ) : null}
          </PageActions>
        }
        description="项目成员页负责把项目和用户管理真正串起来。这里可以搜索活跃用户、分配角色、调整成员并保护最后一个管理员。"
        eyebrow="Workspace"
        title={project?.name ? `${project.name} Members` : "Project Members"}
      />

      <section className="grid gap-4 xl:grid-cols-4">
        <Card className="p-5">
          <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
            Current Project
          </div>
          <div className="mt-4 text-3xl font-semibold tracking-tight text-[var(--foreground)]">
            {isCurrentProject ? "Current" : "Available"}
          </div>
        </Card>
        <Card className="p-5">
          <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
            Members
          </div>
          <div className="mt-4 text-3xl font-semibold tracking-tight text-[var(--foreground)]">
            {items.length}
          </div>
        </Card>
        <Card className="p-5">
          <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
            Admins
          </div>
          <div className="mt-4 text-3xl font-semibold tracking-tight text-[var(--foreground)]">
            {adminCount}
          </div>
        </Card>
        <Card className="p-5">
          <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
            Project ID
          </div>
          <div className="mt-4 font-mono text-sm leading-7 text-[var(--muted-foreground)]">
            {projectId}
          </div>
        </Card>
      </section>

      {loading ? <StateBanner message="Loading project members..." /> : null}
      {error ? <StateBanner message={error} variant="error" /> : null}
      {notice ? <StateBanner message={notice} variant="success" /> : null}

      <FormSection
        description="先搜用户再分配角色，也保留手动输入用户 ID 的兜底方式。选中已有成员后保存，可以直接更新角色。"
        title={
          targetExistingMember ? "Update Member Role" : "Add Project Member"
        }
      >
        <form className="grid gap-5" onSubmit={onSubmit}>
          <div className="grid gap-5 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_220px]">
            <div className="grid gap-3">
              <label className="grid gap-2 text-sm font-medium text-[var(--foreground)]">
                Search active user by username
                <Input
                  placeholder="Search by username"
                  value={userSearch}
                  onChange={(event) => setUserSearch(event.target.value)}
                />
              </label>

              {searchingUsers ? (
                <div className="text-sm text-[var(--muted-foreground)]">
                  Searching users...
                </div>
              ) : null}

              {!searchingUsers && userCandidates.length > 0 ? (
                <div
                  className="grid max-h-56 gap-2 overflow-auto rounded-2xl border p-3"
                  style={{
                    borderColor: "var(--border)",
                    background: "var(--surface-soft)",
                  }}
                >
                  {userCandidates.map((candidate) => (
                    <button
                      key={candidate.id}
                      className="flex items-center justify-between rounded-2xl border px-4 py-3 text-left transition hover:translate-x-[2px]"
                      style={{
                        borderColor: "var(--border)",
                        background: "var(--surface)",
                      }}
                      type="button"
                      onClick={() => {
                        setUserId(candidate.id);
                        setUserSearch(candidate.username);
                      }}
                    >
                      <span className="font-medium text-[var(--foreground)]">
                        {candidate.username}
                      </span>
                      <span className="font-mono text-xs text-[var(--muted-foreground)]">
                        {candidate.id}
                      </span>
                    </button>
                  ))}
                </div>
              ) : null}
            </div>

            <label className="grid gap-2 text-sm font-medium text-[var(--foreground)]">
              User ID
              <Input
                placeholder="Paste user UUID if needed"
                required
                value={userId}
                onChange={(event) => setUserId(event.target.value)}
              />
            </label>

            <label className="grid gap-2 text-sm font-medium text-[var(--foreground)]">
              Role
              <Select
                value={role}
                onChange={(event) =>
                  setRole(event.target.value as "admin" | "editor" | "executor")
                }
              >
                <option value="admin">admin</option>
                <option value="editor">editor</option>
                <option value="executor">executor</option>
              </Select>
            </label>
          </div>

          <PageActions>
            <Button
              disabled={submitting || !userId.trim()}
              type="submit"
              variant="primary"
            >
              {submitting
                ? "Saving..."
                : targetExistingMember
                  ? "Update member"
                  : "Add member"}
            </Button>
            <Button
              disabled={submitting}
              type="button"
              variant="ghost"
              onClick={() => {
                setUserId("");
                setUserSearch("");
                setRole("executor");
                setError(null);
              }}
            >
              Clear
            </Button>
          </PageActions>

          {adminCount <= 1 ? (
            <div className="text-sm text-[var(--status-warning-foreground)]">
              Last admin protection is active for this project.
            </div>
          ) : null}
        </form>
      </FormSection>

      <DataPanel
        description="成员列表支持搜索、预填编辑和移除。删除最后一个管理员会被禁止，避免把项目权限直接玩死。"
        title="Member Directory"
        toolbar={
          <>
            <Input
              className="min-w-[280px]"
              placeholder="Search by username"
              value={memberSearchInput}
              onChange={(event) => setMemberSearchInput(event.target.value)}
            />
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                setMemberQuery(memberSearchInput.trim());
              }}
            >
              Search
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                setMemberSearchInput("");
                setMemberQuery("");
              }}
            >
              Clear
            </Button>
          </>
        }
      >
        {!loading && items.length === 0 ? (
          <EmptyState
            description="当前项目还没有成员，或者搜索结果为空。先从上面的搜索框里拉一个活跃用户进来。"
            title="No members found"
          />
        ) : null}

        {!loading && items.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[920px] border-collapse">
              <thead>
                <tr
                  className="border-b"
                  style={{ borderColor: "var(--border)" }}
                >
                  {["Username", "User ID", "Role", "Quick Edit", "Action"].map(
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
                {items.map((member) => (
                  <tr
                    key={member.user_id}
                    className="border-b last:border-b-0"
                    style={{ borderColor: "var(--border)" }}
                  >
                    <td className="px-4 py-4 align-top">
                      <div className="font-semibold text-[var(--foreground)]">
                        {member.username}
                      </div>
                    </td>
                    <td className="px-4 py-4 align-top font-mono text-xs text-[var(--muted-foreground)]">
                      {member.user_id}
                    </td>
                    <td className="px-4 py-4 align-top">
                      <StatusPill
                        label={member.role}
                        variant={
                          member.role === "admin"
                            ? "success"
                            : member.role === "editor"
                              ? "neutral"
                              : "warning"
                        }
                      />
                    </td>
                    <td className="px-4 py-4 align-top">
                      <Button
                        size="sm"
                        type="button"
                        variant="ghost"
                        onClick={() => {
                          setUserId(member.user_id);
                          setUserSearch(member.username);
                          setRole(member.role);
                          setError(null);
                          setNotice(null);
                        }}
                      >
                        Edit role
                      </Button>
                    </td>
                    <td className="px-4 py-4 align-top">
                      <Button
                        disabled={
                          (member.role === "admin" && adminCount <= 1) ||
                          removingUserId === member.user_id
                        }
                        size="sm"
                        style={{
                          background:
                            member.role === "admin" && adminCount <= 1
                              ? "var(--status-neutral-background)"
                              : "var(--status-danger-background)",
                          color:
                            member.role === "admin" && adminCount <= 1
                              ? "var(--status-neutral-foreground)"
                              : "var(--status-danger-foreground)",
                          borderColor: "transparent",
                        }}
                        type="button"
                        variant="ghost"
                        onClick={() => setPendingDeleteMember(member)}
                      >
                        {member.role === "admin" && adminCount <= 1
                          ? "Last admin"
                          : removingUserId === member.user_id
                            ? "Removing..."
                            : "Remove"}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </DataPanel>

      <ConfirmDialog
        confirmLabel="Remove member"
        confirmLabelLoading="Removing..."
        description={
          pendingDeleteMember
            ? `Remove ${pendingDeleteMember.username} from this project?`
            : undefined
        }
        loading={
          pendingDeleteMember
            ? removingUserId === pendingDeleteMember.user_id
            : false
        }
        open={pendingDeleteMember !== null}
        title="Remove project member"
        onCancel={() => setPendingDeleteMember(null)}
        onConfirm={() => {
          if (!pendingDeleteMember) {
            return;
          }
          void onDelete(pendingDeleteMember);
        }}
      />
    </PlatformPage>
  );
}

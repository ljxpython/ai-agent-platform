"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

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
  listUserProjects,
  getUser,
  type ManagementUser,
  type ManagementUserProject,
  updateUser,
} from "@/lib/management-api/users";

export default function UserDetailPage() {
  const params = useParams<{ userId: string }>();
  const userId = String(params.userId || "");

  const [user, setUser] = useState<ManagementUser | null>(null);
  const [projects, setProjects] = useState<ManagementUserProject[]>([]);
  const [loading, setLoading] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);
  const [updatingPassword, setUpdatingPassword] = useState(false);
  const [username, setUsername] = useState("");
  const [status, setStatus] = useState<"active" | "disabled">("active");
  const [isSuperAdmin, setIsSuperAdmin] = useState(false);
  const [newPassword, setNewPassword] = useState("");
  const [confirmNewPassword, setConfirmNewPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!userId) {
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const [userRow, projectsPayload] = await Promise.all([
        getUser(userId),
        listUserProjects(userId),
      ]);
      setUser(userRow);
      setProjects(projectsPayload.items);
      setUsername(userRow.username);
      setStatus(userRow.status === "disabled" ? "disabled" : "active");
      setIsSuperAdmin(Boolean(userRow.is_super_admin));
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Failed to load user detail",
      );
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const projectCount = projects.length;
  const statusActionLabel = useMemo(() => {
    if (!user) {
      return "Update status";
    }
    return user.status === "active" ? "Disable user" : "Enable user";
  }, [user]);

  async function onSaveProfile(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!user) {
      return;
    }

    const normalizedUsername = username.trim();
    if (!normalizedUsername) {
      setError("Username is required");
      return;
    }

    setSavingProfile(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await updateUser(user.id, {
        username: normalizedUsername,
        status,
        is_super_admin: isSuperAdmin,
      });
      setUser(updated);
      setStatus(updated.status === "disabled" ? "disabled" : "active");
      setIsSuperAdmin(Boolean(updated.is_super_admin));
      setNotice("Profile updated");
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Failed to update user profile",
      );
    } finally {
      setSavingProfile(false);
    }
  }

  async function onUpdatePassword(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!user) {
      return;
    }
    if (newPassword.length < 8) {
      setError("New password must be at least 8 characters");
      return;
    }
    if (newPassword !== confirmNewPassword) {
      setError("Password confirmation does not match");
      return;
    }

    setUpdatingPassword(true);
    setError(null);
    setNotice(null);
    try {
      await updateUser(user.id, { password: newPassword });
      setNewPassword("");
      setConfirmNewPassword("");
      setNotice("Password updated");
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Failed to update password",
      );
    } finally {
      setUpdatingPassword(false);
    }
  }

  async function onToggleStatus() {
    if (!user) {
      return;
    }

    const nextStatus = user.status === "active" ? "disabled" : "active";
    setSavingProfile(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await updateUser(user.id, { status: nextStatus });
      setUser(updated);
      setStatus(updated.status === "disabled" ? "disabled" : "active");
      setNotice(nextStatus === "disabled" ? "User disabled" : "User enabled");
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Failed to update user status",
      );
    } finally {
      setSavingProfile(false);
    }
  }

  if (!loading && !user && !error) {
    return (
      <PlatformPage>
        <PageHeader
          actions={
            <PageActions>
              <Button asChild variant="ghost">
                <Link href="/workspace/users">Back to users</Link>
              </Button>
            </PageActions>
          }
          description="用户详情没有读取到目标记录。"
          eyebrow="Workspace"
          title="User Detail"
        />
        <EmptyState
          description="请返回用户列表重新选择一个账号。"
          title="User not found"
        />
      </PlatformPage>
    );
  }

  return (
    <PlatformPage>
      <PageHeader
        actions={
          <PageActions>
            <Button asChild variant="ghost">
              <Link href="/workspace/users">Back to users</Link>
            </Button>
            <Button
              disabled={!user || savingProfile}
              onClick={() => void onToggleStatus()}
              variant="ghost"
            >
              {statusActionLabel}
            </Button>
          </PageActions>
        }
        description="用户详情页先承接账号资料、状态控制、密码更新和项目归属。审计明细后续再迁，不在这里乱堆。"
        eyebrow="Workspace"
        title={user ? user.username : "User Detail"}
      />

      {loading ? <StateBanner message="Loading user detail..." /> : null}
      {error ? <StateBanner message={error} variant="error" /> : null}
      {notice ? <StateBanner message={notice} variant="success" /> : null}

      {user ? (
        <>
          <section className="grid gap-4 xl:grid-cols-4">
            <Card className="p-5">
              <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
                Status
              </div>
              <div className="mt-4">
                <StatusPill
                  label={user.status}
                  variant={user.status === "active" ? "success" : "warning"}
                />
              </div>
            </Card>
            <Card className="p-5">
              <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
                Super Admin
              </div>
              <div className="mt-4">
                <StatusPill
                  label={user.is_super_admin ? "yes" : "no"}
                  variant={user.is_super_admin ? "neutral" : "warning"}
                />
              </div>
            </Card>
            <Card className="p-5">
              <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
                Project Access
              </div>
              <div className="mt-4 text-3xl font-semibold tracking-tight text-[var(--foreground)]">
                {projectCount}
              </div>
            </Card>
            <Card className="p-5">
              <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
                Updated
              </div>
              <div className="mt-4 text-sm leading-7 text-[var(--muted-foreground)]">
                {user.updated_at || user.created_at || "-"}
              </div>
            </Card>
          </section>

          <FormSection
            description="这里统一处理用户名、状态和管理员身份。账号基础资料先做稳，不搞重复入口。"
            title="Profile"
          >
            <form className="grid gap-5" onSubmit={onSaveProfile}>
              <div className="grid gap-5 lg:grid-cols-2">
                <label className="grid gap-2 text-sm font-medium text-[var(--foreground)]">
                  Username
                  <Input
                    disabled={savingProfile || loading}
                    required
                    value={username}
                    onChange={(event) => setUsername(event.target.value)}
                  />
                </label>

                <label className="grid gap-2 text-sm font-medium text-[var(--foreground)]">
                  Status
                  <Select
                    disabled={savingProfile || loading}
                    value={status}
                    onChange={(event) =>
                      setStatus(event.target.value as "active" | "disabled")
                    }
                  >
                    <option value="active">active</option>
                    <option value="disabled">disabled</option>
                  </Select>
                </label>
              </div>

              <label
                className="flex items-center gap-3 rounded-2xl border px-4 py-3 text-sm text-[var(--foreground)]"
                style={{ borderColor: "var(--border)" }}
              >
                <input
                  checked={isSuperAdmin}
                  disabled={savingProfile || loading}
                  style={{ accentColor: "var(--primary)" }}
                  type="checkbox"
                  onChange={(event) => setIsSuperAdmin(event.target.checked)}
                />
                Super admin
              </label>

              <div className="grid gap-2 text-sm text-[var(--muted-foreground)]">
                <p>ID: {user.id}</p>
                <p>Email: {user.email || "-"}</p>
                <p>Created: {user.created_at || "-"}</p>
                <p>Updated: {user.updated_at || "-"}</p>
              </div>

              <PageActions>
                <Button
                  disabled={savingProfile || loading}
                  type="submit"
                  variant="primary"
                >
                  {savingProfile ? "Saving..." : "Save changes"}
                </Button>
              </PageActions>
            </form>
          </FormSection>

          <FormSection
            description="密码更新独立成一个块，避免资料保存和安全操作搅在一起。"
            title="Security"
          >
            <form
              autoComplete="off"
              className="grid gap-5"
              onSubmit={onUpdatePassword}
            >
              <div className="grid gap-5 lg:grid-cols-2">
                <label className="grid gap-2 text-sm font-medium text-[var(--foreground)]">
                  New password
                  <Input
                    autoComplete="new-password"
                    disabled={updatingPassword || loading}
                    minLength={8}
                    required
                    type="password"
                    value={newPassword}
                    onChange={(event) => setNewPassword(event.target.value)}
                  />
                </label>

                <label className="grid gap-2 text-sm font-medium text-[var(--foreground)]">
                  Confirm new password
                  <Input
                    autoComplete="new-password"
                    disabled={updatingPassword || loading}
                    minLength={8}
                    required
                    type="password"
                    value={confirmNewPassword}
                    onChange={(event) =>
                      setConfirmNewPassword(event.target.value)
                    }
                  />
                </label>
              </div>

              <PageActions>
                <Button
                  disabled={updatingPassword || loading}
                  type="submit"
                  variant="primary"
                >
                  {updatingPassword ? "Updating..." : "Update password"}
                </Button>
                <Button
                  disabled={updatingPassword}
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    setNewPassword("");
                    setConfirmNewPassword("");
                  }}
                >
                  Clear
                </Button>
              </PageActions>
            </form>
          </FormSection>

          <DataPanel
            description="这里先承接用户的项目归属关系，后续成员页和权限页会跟这块互相打通。"
            title="Project Access"
          >
            {projects.length === 0 ? (
              <EmptyState
                description="这个账号当前没有项目归属记录。成员管理迁入后，会从项目侧继续维护这些关系。"
                title="No project membership"
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[860px] border-collapse">
                  <thead>
                    <tr
                      className="border-b"
                      style={{ borderColor: "var(--border)" }}
                    >
                      {["Project", "Role", "Status", "Joined", "Action"].map(
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
                    {projects.map((item) => (
                      <tr
                        key={item.project_id}
                        className="border-b last:border-b-0"
                        style={{ borderColor: "var(--border)" }}
                      >
                        <td className="px-4 py-4 align-top">
                          <div className="font-semibold text-[var(--foreground)]">
                            {item.project_name}
                          </div>
                          <div className="mt-1 text-sm text-[var(--muted-foreground)]">
                            {item.project_description || "No description"}
                          </div>
                        </td>
                        <td className="px-4 py-4 align-top text-sm text-[var(--foreground)]">
                          {item.role}
                        </td>
                        <td className="px-4 py-4 align-top">
                          <StatusPill
                            label={item.project_status}
                            variant={
                              item.project_status === "active"
                                ? "success"
                                : "warning"
                            }
                          />
                        </td>
                        <td className="px-4 py-4 align-top text-sm text-[var(--muted-foreground)]">
                          {item.joined_at
                            ? new Date(item.joined_at).toLocaleString()
                            : "-"}
                        </td>
                        <td className="px-4 py-4 align-top">
                          <Button asChild size="sm" variant="ghost">
                            <Link
                              href={`/workspace/projects/${item.project_id}`}
                            >
                              View project
                            </Link>
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </DataPanel>
        </>
      ) : null}
    </PlatformPage>
  );
}

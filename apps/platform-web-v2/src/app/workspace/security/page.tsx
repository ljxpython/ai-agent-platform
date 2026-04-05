"use client";

import Link from "next/link";
import { useState } from "react";

import { FormSection } from "@/components/platform/form-section";
import { PageHeader } from "@/components/platform/page-header";
import { PageActions } from "@/components/platform/page-actions";
import { PlatformPage } from "@/components/platform/platform-page";
import { StateBanner } from "@/components/platform/state-banner";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { changePassword } from "@/lib/management-api/auth";

export default function SecurityPage() {
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (newPassword.length < 8) {
      setError("New password must be at least 8 characters");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("Password confirmation does not match");
      return;
    }
    if (oldPassword === newPassword) {
      setError("New password must be different from current password");
      return;
    }

    setLoading(true);
    setError(null);
    setNotice(null);
    try {
      await changePassword({ oldPassword, newPassword });
      setOldPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setNotice(
        "Password updated. Please re-login on other sessions if needed.",
      );
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Failed to change password",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <PlatformPage>
      <PageHeader
        actions={
          <PageActions>
            <Button asChild variant="ghost">
              <Link href="/workspace/me">Back to profile</Link>
            </Button>
          </PageActions>
        }
        description="安全页专门处理密码修改这类高风险动作。这样资料编辑和安全动作分层更清楚，维护起来也不容易乱。"
        eyebrow="Account"
        title="Security"
      />

      {error ? <StateBanner message={error} variant="error" /> : null}
      {notice ? <StateBanner message={notice} variant="success" /> : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
        <FormSection
          description="密码修改会走 `/_management/auth/change-password`，这里只保留必要校验，不加虚头巴脑的表单花活。"
          title="Change Password"
        >
          <form autoComplete="off" className="grid gap-5" onSubmit={onSubmit}>
            <label className="grid gap-2 text-sm font-medium text-[var(--foreground)]">
              Current password
              <Input
                autoComplete="current-password"
                required
                type="password"
                value={oldPassword}
                onChange={(event) => setOldPassword(event.target.value)}
              />
            </label>

            <label className="grid gap-2 text-sm font-medium text-[var(--foreground)]">
              New password
              <Input
                autoComplete="new-password"
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
                minLength={8}
                required
                type="password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
              />
            </label>

            <PageActions>
              <Button disabled={loading} type="submit" variant="primary">
                {loading ? "Updating..." : "Update password"}
              </Button>
            </PageActions>
          </form>
        </FormSection>

        <Card className="p-6">
          <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
            Security Notes
          </div>
          <div className="mt-4 space-y-4 text-sm leading-7 text-[var(--muted-foreground)]">
            <p>新密码至少 8 位，并且不能和当前密码相同。</p>
            <p>
              如果你在多端登录，改密后建议重新登录其他会话，别留一堆过期状态在那恶心人。
            </p>
          </div>
        </Card>
      </div>
    </PlatformPage>
  );
}

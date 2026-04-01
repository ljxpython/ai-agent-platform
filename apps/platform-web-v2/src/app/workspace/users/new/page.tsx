"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { FormSection } from "@/components/platform/form-section";
import { PageHeader } from "@/components/platform/page-header";
import { PageActions } from "@/components/platform/page-actions";
import { PlatformPage } from "@/components/platform/platform-page";
import { StateBanner } from "@/components/platform/state-banner";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { createUser } from "@/lib/management-api/users";

const FORM_ID = "create-user-form";

export default function CreateUserPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isSuperAdmin, setIsSuperAdmin] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!username.trim()) {
      setError("Username is required");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const created = await createUser({
        username: username.trim(),
        password,
        is_super_admin: isSuperAdmin,
      });
      router.replace(`/workspace/users/${created.id}`);
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Failed to create user",
      );
    } finally {
      setSubmitting(false);
    }
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
              disabled={submitting}
              form={FORM_ID}
              type="submit"
              variant="primary"
            >
              {submitting ? "Creating..." : "Create user"}
            </Button>
          </PageActions>
        }
        description="用户创建页先把账号、密码和管理员身份接进 v2，避免系统管理还停留在旧页面里。"
        eyebrow="Workspace"
        title="Create User"
      />

      {error ? <StateBanner message={error} variant="error" /> : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
        <FormSection
          description="这里只保留创建账号所需的必要字段。更复杂的权限和项目归属，会在详情页继续处理。"
          title="Account Setup"
        >
          <form
            autoComplete="off"
            className="grid gap-5"
            id={FORM_ID}
            onSubmit={onSubmit}
          >
            <label className="grid gap-2 text-sm font-medium text-[var(--foreground)]">
              Username
              <Input
                autoComplete="off"
                disabled={submitting}
                name="create-user-username"
                placeholder="platform-admin"
                required
                value={username}
                onChange={(event) => setUsername(event.target.value)}
              />
            </label>

            <label className="grid gap-2 text-sm font-medium text-[var(--foreground)]">
              Password
              <Input
                autoComplete="new-password"
                disabled={submitting}
                minLength={8}
                name="create-user-password"
                placeholder="At least 8 characters"
                required
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>

            <label
              className="flex items-center gap-3 rounded-2xl border px-4 py-3 text-sm text-[var(--foreground)]"
              style={{ borderColor: "var(--border)" }}
            >
              <input
                checked={isSuperAdmin}
                disabled={submitting}
                style={{ accentColor: "var(--primary)" }}
                type="checkbox"
                onChange={(event) => setIsSuperAdmin(event.target.checked)}
              />
              Grant super admin capability
            </label>
          </form>
        </FormSection>

        <Card className="p-6">
          <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
            Creation Notes
          </div>
          <div className="mt-4 space-y-4 text-sm leading-7 text-[var(--muted-foreground)]">
            <p>
              创建完成后会直接跳到用户详情页，方便立刻调整状态、密码和项目归属。
            </p>
            <p>管理员权限只该给真正需要的人，别把后台搞成人人都有万能钥匙。</p>
          </div>
        </Card>
      </div>
    </PlatformPage>
  );
}

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { ConfirmDialog } from "@/components/platform/confirm-dialog";
import { FormSection } from "@/components/platform/form-section";
import { PageHeader } from "@/components/platform/page-header";
import { PageActions } from "@/components/platform/page-actions";
import { PlatformPage } from "@/components/platform/platform-page";
import { StateBanner } from "@/components/platform/state-banner";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { clearOidcTokenSet } from "@/lib/oidc-storage";
import {
  getMe,
  updateMe,
  type ManagementUser,
} from "@/lib/management-api/users";

type LocalProfileExtras = {
  avatarUrl: string;
  signature: string;
};

function getProfileExtrasStorageKey(userId: string): string {
  return `platform-web-v2:profile:extras:${userId}`;
}

export default function MePage() {
  const router = useRouter();
  const [profile, setProfile] = useState<ManagementUser | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [confirmSignOutOpen, setConfirmSignOutOpen] = useState(false);

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [avatarUrl, setAvatarUrl] = useState("");
  const [signature, setSignature] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadProfile() {
      setLoading(true);
      setError(null);
      try {
        const me = await getMe();
        if (cancelled) {
          return;
        }
        setProfile(me);
        setUsername(me.username);
        setEmail(me.email || "");

        if (typeof window !== "undefined") {
          const raw = window.localStorage.getItem(
            getProfileExtrasStorageKey(me.id),
          );
          if (raw) {
            try {
              const parsed = JSON.parse(raw) as Partial<LocalProfileExtras>;
              setAvatarUrl(
                typeof parsed.avatarUrl === "string" ? parsed.avatarUrl : "",
              );
              setSignature(
                typeof parsed.signature === "string" ? parsed.signature : "",
              );
            } catch {
              window.localStorage.removeItem(getProfileExtrasStorageKey(me.id));
            }
          }
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : "Failed to load current profile",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadProfile();
    return () => {
      cancelled = true;
    };
  }, []);

  const avatarFallback = useMemo(() => {
    const normalized = username.trim();
    if (!normalized) {
      return "U";
    }
    return normalized.slice(0, 1).toUpperCase();
  }, [username]);

  async function onSaveProfile(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!profile) {
      return;
    }

    const normalizedUsername = username.trim();
    if (!normalizedUsername) {
      setError("Username is required");
      return;
    }

    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await updateMe({
        username: normalizedUsername,
        email: email.trim(),
      });
      setProfile(updated);
      if (typeof window !== "undefined") {
        const payload: LocalProfileExtras = {
          avatarUrl: avatarUrl.trim(),
          signature: signature.trim(),
        };
        window.localStorage.setItem(
          getProfileExtrasStorageKey(updated.id),
          JSON.stringify(payload),
        );
      }
      setNotice("Profile updated");
    } catch (saveError) {
      setError(
        saveError instanceof Error
          ? saveError.message
          : "Failed to update profile",
      );
    } finally {
      setSaving(false);
    }
  }

  function signOutNow() {
    clearOidcTokenSet();
    router.replace("/auth/login");
  }

  return (
    <PlatformPage>
      <PageHeader
        actions={
          <PageActions>
            <Button asChild variant="ghost">
              <Link href="/workspace/security">Open security</Link>
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => setConfirmSignOutOpen(true)}
            >
              Sign out
            </Button>
          </PageActions>
        }
        description="个人资料页承接当前登录用户的基础信息编辑和会话操作。密码修改单独放到 Security 页面，避免资料和安全动作搅在一起。"
        eyebrow="Account"
        title="My Profile"
      />

      {loading ? <StateBanner message="Loading profile..." /> : null}
      {error ? <StateBanner message={error} variant="error" /> : null}
      {notice ? <StateBanner message={notice} variant="success" /> : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
        <FormSection
          description="账号资料先支持用户名、邮箱和本地化的头像/签名扩展。后两项只保存在浏览器，不写回后端。"
          title="Profile"
        >
          <form className="grid gap-5" onSubmit={onSaveProfile}>
            <div
              className="flex items-center gap-4 rounded-2xl border px-4 py-4"
              style={{ borderColor: "var(--border)" }}
            >
              <Avatar
                className="h-14 w-14 border"
                style={{ borderColor: "var(--border)" }}
              >
                {avatarUrl.trim() ? (
                  <AvatarImage alt="avatar" src={avatarUrl.trim()} />
                ) : null}
                <AvatarFallback
                  style={{
                    background: "var(--brand-mark-background)",
                    color: "var(--brand-mark-foreground)",
                  }}
                >
                  {avatarFallback}
                </AvatarFallback>
              </Avatar>
              <div>
                <div className="text-sm font-semibold text-[var(--foreground)]">
                  {username || "Unnamed User"}
                </div>
                <div className="text-sm text-[var(--muted-foreground)]">
                  {email || "No email configured"}
                </div>
              </div>
            </div>

            <label className="grid gap-2 text-sm font-medium text-[var(--foreground)]">
              Avatar URL
              <Input
                placeholder="https://..."
                value={avatarUrl}
                onChange={(event) => setAvatarUrl(event.target.value)}
              />
            </label>

            <label className="grid gap-2 text-sm font-medium text-[var(--foreground)]">
              Username
              <Input
                required
                value={username}
                onChange={(event) => setUsername(event.target.value)}
              />
            </label>

            <label className="grid gap-2 text-sm font-medium text-[var(--foreground)]">
              Email
              <Input
                placeholder="optional"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>

            <label className="grid gap-2 text-sm font-medium text-[var(--foreground)]">
              Signature
              <Textarea
                maxLength={200}
                placeholder="Write your signature"
                value={signature}
                onChange={(event) => setSignature(event.target.value)}
              />
              <div className="text-xs text-[var(--muted-foreground)]">
                {signature.length}/200
              </div>
            </label>

            <PageActions>
              <Button
                disabled={saving || loading}
                type="submit"
                variant="primary"
              >
                {saving ? "Saving..." : "Save profile"}
              </Button>
            </PageActions>
          </form>
        </FormSection>

        <Card className="p-6">
          <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
            Account Summary
          </div>
          <div className="mt-4 space-y-3 text-sm leading-7 text-[var(--muted-foreground)]">
            <p>User ID: {profile?.id || "-"}</p>
            <p>Status: {profile?.status || "-"}</p>
            <p>Created: {profile?.created_at || "-"}</p>
            <p>Updated: {profile?.updated_at || "-"}</p>
          </div>
        </Card>
      </div>

      <ConfirmDialog
        confirmLabel="Sign out"
        confirmLabelLoading="Signing out..."
        description="Are you sure you want to sign out from the current session?"
        open={confirmSignOutOpen}
        title="Sign out"
        onCancel={() => setConfirmSignOutOpen(false)}
        onConfirm={signOutNow}
      />
    </PlatformPage>
  );
}

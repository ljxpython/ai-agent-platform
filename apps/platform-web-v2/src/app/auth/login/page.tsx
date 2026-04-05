"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ensureApiUrlSeeded, hasOidcSession, setOidcTokenSet } from "@/lib/oidc-storage";
import { login } from "@/lib/management-api/auth";

export default function LoginPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (hasOidcSession()) {
      router.replace("/workspace/overview");
    }
  }, [router]);

  return (
    <section className="mx-auto flex min-h-screen max-w-6xl items-center px-6 py-10">
      <div className="grid w-full gap-8 lg:grid-cols-[minmax(0,1.1fr)_420px]">
        <div className="flex flex-col justify-center">
          <div className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--muted-foreground)]">
            Platform Web V2
          </div>
          <h1 className="mt-4 text-5xl font-semibold tracking-tight text-[var(--foreground)]">
            管理平台的新一代工作台
          </h1>
          <p className="mt-5 max-w-2xl text-base leading-8 text-[var(--muted-foreground)]">
            先把平台管理页做成成熟企业后台的样子，再按模块逐步迁移旧能力。这里先接入最小可用登录链路，后续继续承接 Projects、Users、Assistants 等页面。
          </p>
          <div className="mt-8 grid gap-4 sm:grid-cols-3">
            {[
              ["Refine HR 系", "默认主题与工作台壳子"],
              ["Workspace Context", "统一项目上下文入口"],
              ["Management API", "后续管理页按模块迁移"],
            ].map(([title, desc]) => (
              <Card key={title} className="p-5">
                <div className="text-sm font-semibold text-[var(--foreground)]">{title}</div>
                <div className="mt-2 text-sm leading-7 text-[var(--muted-foreground)]">{desc}</div>
              </Card>
            ))}
          </div>
        </div>

        <Card className="p-6 lg:p-8">
          <div className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--muted-foreground)]">
            Sign in
          </div>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight text-[var(--foreground)]">
            登录平台管理工作台
          </h2>
          <p className="mt-3 text-sm leading-7 text-[var(--muted-foreground)]">
            使用现有平台账号登录。成功后将自动跳转到新的 v2 工作台。
          </p>

          <form
            className="mt-8 grid gap-4"
            onSubmit={async (event) => {
              event.preventDefault();
              setError(null);
              setLoading(true);

              const formData = new FormData(event.currentTarget);
              const username = String(formData.get("username") ?? "").trim();
              const password = String(formData.get("password") ?? "");

              try {
                const payload = await login({ username, password });
                if (!payload.access_token) {
                  throw new Error("Account login failed");
                }

                setOidcTokenSet({
                  access_token: payload.access_token,
                  refresh_token: payload.refresh_token,
                });
                ensureApiUrlSeeded();

                const redirectParam =
                  typeof window === "undefined"
                    ? ""
                    : new URLSearchParams(window.location.search).get("redirect") || "";
                const redirectTo = redirectParam.startsWith("/workspace")
                  ? redirectParam
                  : "/workspace/overview";
                router.replace(redirectTo);
              } catch (submitError) {
                setError(
                  submitError instanceof Error ? submitError.message : "Account login failed",
                );
              } finally {
                setLoading(false);
              }
            }}
          >
            <label className="grid gap-2 text-sm">
              <span className="font-medium text-[var(--foreground)]">Username</span>
              <Input id="username" name="username" placeholder="请输入用户名" required />
            </label>

            <label className="grid gap-2 text-sm">
              <span className="font-medium text-[var(--foreground)]">Password</span>
              <Input
                id="password"
                name="password"
                placeholder="请输入密码"
                required
                type="password"
              />
            </label>

            {error ? (
              <div
                className="rounded-xl px-4 py-3 text-sm"
                style={{
                  background: "var(--status-danger-background)",
                  color: "var(--status-danger-foreground)",
                }}
              >
                {error}
              </div>
            ) : null}

            <Button className="mt-2 w-full" disabled={loading} type="submit" variant="primary">
              {loading ? "Signing in..." : "Sign in"}
            </Button>
          </form>
        </Card>
      </div>
    </section>
  );
}

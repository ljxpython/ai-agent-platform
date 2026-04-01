"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { EmptyState } from "@/components/platform/empty-state";
import { FormSection } from "@/components/platform/form-section";
import { PageHeader } from "@/components/platform/page-header";
import { PageActions } from "@/components/platform/page-actions";
import { PlatformPage } from "@/components/platform/platform-page";
import { StateBanner } from "@/components/platform/state-banner";
import { StatusPill } from "@/components/platform/status-pill";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useWorkspaceContext } from "@/providers/WorkspaceProvider";

export default function ProjectDetailPage() {
  const params = useParams<{ projectId: string }>();
  const router = useRouter();
  const {
    loading,
    projectId: currentProjectId,
    projects,
    setProjectId,
  } = useWorkspaceContext();
  const projectId = String(params.projectId || "");
  const project = projects.find((item) => item.id === projectId) ?? null;
  const isCurrentProject = projectId === currentProjectId;

  if (!loading && !project) {
    return (
      <PlatformPage>
        <PageHeader
          actions={
            <PageActions>
              <Button asChild variant="ghost">
                <Link href="/workspace/projects">Back to projects</Link>
              </Button>
            </PageActions>
          }
          description="当前项目没有在已授权的项目列表里找到，可能是地址过期，也可能是你没有访问权限。"
          eyebrow="Workspace"
          title="Project Detail"
        />
        <EmptyState
          description="请返回项目列表重新选择一个可访问项目。"
          title="Project not found"
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
              <Link href="/workspace/projects">Back to projects</Link>
            </Button>
            <Button asChild variant="ghost">
              <Link href={`/workspace/projects/${projectId}/members`}>
                Manage members
              </Link>
            </Button>
            <Button
              disabled={!project}
              onClick={() => {
                if (!project) {
                  return;
                }
                if (!isCurrentProject) {
                  setProjectId(project.id);
                }
                router.push("/workspace/assistants");
              }}
              variant="primary"
            >
              Open assistants
            </Button>
          </PageActions>
        }
        description="项目详情页现在已经能承接成员管理入口。后续审计和策略页会继续沿着这套版式扩展，不会再散落到旧壳子里。"
        eyebrow="Workspace"
        title={project?.name || "Project Detail"}
      />

      <section className="grid gap-4 xl:grid-cols-4">
        <Card className="p-5">
          <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
            Status
          </div>
          <div className="mt-4">
            <StatusPill
              label={project?.status || "unknown"}
              variant={project?.status === "active" ? "success" : "warning"}
            />
          </div>
        </Card>
        <Card className="p-5">
          <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
            Workspace Context
          </div>
          <div className="mt-4 text-3xl font-semibold tracking-tight text-[var(--foreground)]">
            {isCurrentProject ? "Current" : "Available"}
          </div>
        </Card>
        <Card className="p-5">
          <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
            Accessible Projects
          </div>
          <div className="mt-4 text-3xl font-semibold tracking-tight text-[var(--foreground)]">
            {projects.length}
          </div>
        </Card>
        <Card className="p-5">
          <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
            Description
          </div>
          <div className="mt-4 text-3xl font-semibold tracking-tight text-[var(--foreground)]">
            {project?.description?.trim() ? "Set" : "Empty"}
          </div>
        </Card>
      </section>

      <FormSection
        actions={
          !isCurrentProject && project ? (
            <Button
              onClick={() => {
                setProjectId(project.id);
              }}
              variant="ghost"
            >
              Use as current project
            </Button>
          ) : undefined
        }
        description="这里承接项目范围、上下文和关键入口。成员管理已经并入 v2，其他项目级能力会继续挂在这个详情视图下面。"
        title="Project Scope"
      >
        <div className="grid gap-4 lg:grid-cols-2">
          <div
            className="rounded-2xl border px-4 py-4"
            style={{ borderColor: "var(--border)" }}
          >
            <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
              Project ID
            </div>
            <div className="mt-3 font-mono text-sm text-[var(--foreground)]">
              {project?.id || "-"}
            </div>
          </div>
          <div
            className="rounded-2xl border px-4 py-4"
            style={{ borderColor: "var(--border)" }}
          >
            <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
              Current Context
            </div>
            <div className="mt-3 text-sm text-[var(--foreground)]">
              {isCurrentProject
                ? "This project is already active in workspace context."
                : "You can switch to this project before opening assistants or threads."}
            </div>
          </div>
          <div
            className="rounded-2xl border px-4 py-4 lg:col-span-2"
            style={{ borderColor: "var(--border)" }}
          >
            <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
              Description
            </div>
            <div className="mt-3 text-sm leading-7 text-[var(--muted-foreground)]">
              {project?.description ||
                "No description has been set for this project yet."}
            </div>
          </div>
        </div>
      </FormSection>

      <StateBanner message="成员管理已经迁入 v2。下一阶段会继续补项目审计和更细粒度的策略管理。" />
    </PlatformPage>
  );
}

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
import { Textarea } from "@/components/ui/textarea";
import { createProject } from "@/lib/management-api/projects";
import { useWorkspaceContext } from "@/providers/WorkspaceProvider";

const FORM_ID = "create-project-form";

export default function CreateProjectPage() {
  const router = useRouter();
  const { refreshProjects, setProjectId } = useWorkspaceContext();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedName = name.trim();
    if (!normalizedName) {
      setError("Project name is required");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const created = await createProject({
        name: normalizedName,
        description: description.trim() || undefined,
      });
      setProjectId(created.id);
      await refreshProjects().catch(() => undefined);
      router.replace(`/workspace/projects/${created.id}`);
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Failed to create project",
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
              <Link href="/workspace/projects">Back to projects</Link>
            </Button>
            <Button
              disabled={submitting}
              form={FORM_ID}
              type="submit"
              variant="primary"
            >
              {submitting ? "Creating..." : "Create project"}
            </Button>
          </PageActions>
        }
        description="新项目创建页先把最小闭环接进 v2。创建成功后会自动设为当前项目，并跳到项目详情继续承接后续操作。"
        eyebrow="Workspace"
        title="Create Project"
      />

      {error ? <StateBanner message={error} variant="error" /> : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
        <FormSection
          description="项目是整个工作台的上下文入口。这里先保留必要字段，不做花里胡哨的伪能力。"
          title="Project Profile"
        >
          <form className="grid gap-5" id={FORM_ID} onSubmit={onSubmit}>
            <label className="grid gap-2 text-sm font-medium text-[var(--foreground)]">
              Project name
              <Input
                disabled={submitting}
                maxLength={128}
                minLength={1}
                placeholder="AI Test Platform"
                required
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </label>

            <label className="grid gap-2 text-sm font-medium text-[var(--foreground)]">
              Description
              <Textarea
                disabled={submitting}
                placeholder="Describe the business scope, runtime environment or delivery boundary of this project."
                value={description}
                onChange={(event) => setDescription(event.target.value)}
              />
            </label>
          </form>
        </FormSection>

        <Card className="p-6">
          <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
            Creation Notes
          </div>
          <div className="mt-4 space-y-4 text-sm leading-7 text-[var(--muted-foreground)]">
            <p>
              创建完成后，当前项目上下文会立即切换，助手和线程页都会继承这个选择。
            </p>
            <p>
              项目成员、审计和更细粒度策略会在下一阶段继续迁入，不会继续留在旧壳子里。
            </p>
          </div>
        </Card>
      </div>
    </PlatformPage>
  );
}

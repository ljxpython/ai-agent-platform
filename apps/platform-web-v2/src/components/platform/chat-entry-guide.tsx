"use client";

import Link from "next/link";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

function buildScopedHref(pathname: string, projectId: string) {
  const normalizedProjectId = projectId.trim();
  if (!normalizedProjectId) {
    return pathname;
  }

  const params = new URLSearchParams({ projectId: normalizedProjectId });
  return `${pathname}?${params.toString()}`;
}

export function ChatEntryGuide({ projectId }: { projectId: string }) {
  const assistantsHref = buildScopedHref("/workspace/assistants", projectId);
  const graphsHref = buildScopedHref("/workspace/graphs", projectId);

  return (
    <div className="flex min-h-0 flex-1 items-center justify-center">
      <Card className="w-full max-w-4xl border-border/80 bg-card/95 px-8 py-10 shadow-sm">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.5fr)_minmax(18rem,1fr)]">
          <div className="grid gap-4">
            <div className="grid gap-2">
              <div className="text-xs font-bold uppercase tracking-[0.18em] text-muted-foreground">
                Agent Chat
              </div>
              <h1 className="text-3xl font-semibold tracking-tight text-foreground">
                先选一个可用目标，再进入对话
              </h1>
              <p className="max-w-2xl text-sm leading-7 text-muted-foreground">
                当前项目还没有最近使用的聊天目标。先去 `Assistants` 选择一个 Agent，或者去
                `Graphs` 选择一个 Graph。选过一次之后，后面再打开 `/workspace/chat`
                会直接恢复到上次使用的目标。
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <Button asChild variant="primary">
                <Link href={assistantsHref}>前往 Assistants</Link>
              </Button>
              <Button asChild variant="outline">
                <Link href={graphsHref}>前往 Graphs</Link>
              </Button>
            </div>
          </div>

          <div className="grid gap-3 rounded-2xl border border-border/70 bg-muted/20 p-5">
            <div className="text-xs font-bold uppercase tracking-[0.18em] text-muted-foreground">
              进入规则
            </div>
            <div className="rounded-xl border border-border/70 bg-background/80 px-4 py-3">
              <div className="text-sm font-semibold text-foreground">首次打开</div>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">
                没有最近目标时，显示引导页，不再展示当前坏掉的 target 下拉。
              </p>
            </div>
            <div className="rounded-xl border border-border/70 bg-background/80 px-4 py-3">
              <div className="text-sm font-semibold text-foreground">从详情页进入</div>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">
                从 Assistants、Graphs、Threads 打开 Chat 时，会自动记住目标。
              </p>
            </div>
            <div className="rounded-xl border border-border/70 bg-background/80 px-4 py-3">
              <div className="text-sm font-semibold text-foreground">再次进入</div>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">
                有最近目标时直接进聊天，不再要求重复选择。
              </p>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}

import Link from "next/link";

import { DataPanel } from "@/components/platform/data-panel";
import { PageHeader } from "@/components/platform/page-header";
import { PlatformPage } from "@/components/platform/platform-page";
import { StatusPill } from "@/components/platform/status-pill";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

const FEATURE_CARDS = [
  { label: "P0", title: "Projects", href: "/workspace/projects", description: "项目管理页作为全局上下文入口，先承接列表、搜索和当前项目切换。" },
  { label: "P0", title: "Users", href: "/workspace/users", description: "系统级用户列表先迁入 v2，保证后台常用管理页开始进入新母版。" },
  { label: "P0", title: "Assistants", href: "/workspace/assistants", description: "基于当前项目读取助手列表，是后续图谱、线程、testcase 的关键前置页。" },
] as const;

export default function WorkspaceOverviewPage() {
  return (
    <PlatformPage>
      <PageHeader
        actions={
          <>
            <Button asChild variant="ghost">
              <Link href="/workspace/projects">See projects</Link>
            </Button>
            <Button asChild variant="primary">
              <Link href="/workspace/assistants">Open assistants</Link>
            </Button>
          </>
        }
        description="这里不再承担样板展示任务，而是作为 v2 工作台的实际入口页。后续所有管理页都会沿着这套布局、信息密度和主题系统继续迁移。"
        eyebrow="Home"
        title="Overview"
      />

      <section className="grid gap-4 xl:grid-cols-4">
        {[
          ["UI Base", "就绪", "新的工作台壳子、主题系统和 examples 样板已经落地。"],
          ["Auth Chain", "进行中", "账号登录和 token 存储已迁入 v2，后续继续补 guard 与更多会话能力。"],
          ["P0 Pages", "进行中", "Projects / Users / Assistants 首批页面已开始迁入。"],
          ["Migration", "规划中", "复杂工作区仍按 roadmap 分阶段迁移，不会一口气硬搬旧页面。"],
        ].map(([title, status, desc]) => (
          <Card key={title} className="p-5">
            <div className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--muted-foreground)]">
              {title}
            </div>
            <div className="mt-4 flex items-center gap-3">
              <div className="text-3xl font-semibold tracking-tight text-[var(--foreground)]">
                {status}
              </div>
            </div>
            <p className="mt-3 text-sm leading-7 text-[var(--muted-foreground)]">{desc}</p>
          </Card>
        ))}
      </section>

      <DataPanel
        description="这些页面是 v2 的第一批承接对象。先把常用后台管理页迁进去，后续再继续向 runtime/chat/testcase 扩展。"
        title="当前迁移焦点"
      >
        <div className="grid gap-4 xl:grid-cols-3">
          {FEATURE_CARDS.map((card) => (
            <Card key={card.href} className="p-5">
              <div className="flex items-center justify-between gap-3">
                <div className="text-lg font-semibold text-[var(--foreground)]">{card.title}</div>
                <StatusPill label={card.label} variant="neutral" />
              </div>
              <p className="mt-3 text-sm leading-7 text-[var(--muted-foreground)]">{card.description}</p>
              <div className="mt-5">
                <Button asChild variant="ghost">
                  <Link href={card.href}>Open page</Link>
                </Button>
              </div>
            </Card>
          ))}
        </div>
      </DataPanel>
    </PlatformPage>
  );
}

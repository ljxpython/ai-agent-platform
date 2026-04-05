import Link from "next/link";

import { DataPanel } from "@/components/platform/data-panel";
import { PageHeader } from "@/components/platform/page-header";
import { PlatformPage } from "@/components/platform/platform-page";
import { StatusPill } from "@/components/platform/status-pill";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export default function RuntimePage() {
  return (
    <PlatformPage>
      <PageHeader
        description="Runtime 不再是纯占位页。这里先承接模型和工具目录入口，后续更细的策略与联调也会继续挂在这个工作区下面。"
        eyebrow="Advanced"
        title="Runtime"
      />

      <section className="grid gap-4 xl:grid-cols-3">
        <Card className="p-5">
          <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
            Catalog
          </div>
          <div className="mt-4 text-3xl font-semibold tracking-tight text-[var(--foreground)]">
            Models
          </div>
          <p className="mt-3 text-sm leading-7 text-[var(--muted-foreground)]">
            查看 runtime 暴露的模型目录，确认默认模型和同步状态。
          </p>
          <div className="mt-5">
            <Button asChild variant="ghost">
              <Link href="/workspace/runtime/models">Open models</Link>
            </Button>
          </div>
        </Card>

        <Card className="p-5">
          <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
            Catalog
          </div>
          <div className="mt-4 text-3xl font-semibold tracking-tight text-[var(--foreground)]">
            Tools
          </div>
          <p className="mt-3 text-sm leading-7 text-[var(--muted-foreground)]">
            查看工具目录、来源和同步状态，供助手配置和排障使用。
          </p>
          <div className="mt-5">
            <Button asChild variant="ghost">
              <Link href="/workspace/runtime/tools">Open tools</Link>
            </Button>
          </div>
        </Card>

        <Card className="p-5">
          <div className="text-xs font-bold tracking-[0.14em] text-[var(--muted-foreground)] uppercase">
            Status
          </div>
          <div className="mt-4">
            <StatusPill label="catalog ready" variant="neutral" />
          </div>
          <p className="mt-3 text-sm leading-7 text-[var(--muted-foreground)]">
            当前这块先承接目录级能力，项目级策略页会在后面继续补齐。
          </p>
        </Card>
      </section>

      <DataPanel
        description="这一层先解决最常见的 runtime 可见性问题，别让模型和工具目录还躲在旧页面里。"
        title="Next Steps"
      >
        <div className="grid gap-4 xl:grid-cols-2">
          <Card className="p-5">
            <div className="text-lg font-semibold text-[var(--foreground)]">
              Model catalog
            </div>
            <p className="mt-3 text-sm leading-7 text-[var(--muted-foreground)]">
              核对
              `display_name`、`model_id`、默认模型和同步状态，避免助手挂错模型组。
            </p>
          </Card>
          <Card className="p-5">
            <div className="text-lg font-semibold text-[var(--foreground)]">
              Tool catalog
            </div>
            <p className="mt-3 text-sm leading-7 text-[var(--muted-foreground)]">
              核对工具来源、描述和同步状态，后续助手配置页会直接消费这些目录数据。
            </p>
          </Card>
        </div>
      </DataPanel>
    </PlatformPage>
  );
}

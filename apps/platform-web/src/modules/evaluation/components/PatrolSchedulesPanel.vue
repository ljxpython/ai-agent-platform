<script setup lang="ts">
import { computed } from "vue";
import BaseButton from "@/components/base/BaseButton.vue";
import SurfaceCard from "@/components/base/SurfaceCard.vue";
import EmptyState from "@/components/platform/EmptyState.vue";
import MetricCard from "@/components/platform/MetricCard.vue";
import StatusPill from "@/components/platform/StatusPill.vue";
import type {
  EvalRunItem,
  PatrolScheduleItem,
} from "@/services/evaluation/studio";

const props = defineProps<{
  patrols: PatrolScheduleItem[];
  runs: EvalRunItem[];
  canManage: boolean;
  busy?: boolean;
}>();

const emit = defineEmits<{
  create: [];
  edit: [item: PatrolScheduleItem];
  toggleEnabled: [item: PatrolScheduleItem];
  triggerNow: [item: PatrolScheduleItem];
  delete: [item: PatrolScheduleItem];
  viewRun: [runId: string];
}>();

const enabledCount = computed(
  () => props.patrols.filter((p) => p.enabled).length,
);

const alertCount = computed(
  () =>
    props.patrols.filter((p) =>
      ["degraded", "failed", "infra_error", "blocked"].includes(p.last_status),
    ).length,
);

const patrolRunCount = computed(
  () => props.runs.filter((r) => r.trigger_type === "patrol").length,
);

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    idle: "待首次触发",
    running: "巡检执行中",
    passed: "巡检通过",
    degraded: "质量退化预警",
    failed: "门禁未通过",
    infra_error: "基础设施异常",
    blocked: "预检阻塞",
    skipped_overlap: "防重入已跳过",
  };
  return map[status] || status;
}

function statusTone(status: string) {
  if (status === "passed") return "success";
  if (status === "running") return "info";
  if (status === "degraded" || status === "skipped_overlap") return "warning";
  if (status === "failed" || status === "infra_error" || status === "blocked")
    return "danger";
  return "neutral";
}

function formatTime(iso: string | null | undefined): string {
  if (!iso) return "-";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}
</script>

<template>
  <div class="space-y-4">
    <section class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <MetricCard
        label="巡检规则总数"
        :value="patrols.length"
        hint="无人值守质量回归"
        icon="activity"
        tone="primary"
      />
      <MetricCard
        label="已启用自动调度"
        :value="enabledCount"
        hint="Worker 周期安全领锁"
        icon="refresh"
        tone="info"
      />
      <MetricCard
        label="异常 / 退化规则"
        :value="alertCount"
        hint="自动推送站内信与通知渠道"
        icon="shield"
        tone="warning"
      />
      <MetricCard
        label="累计巡检场次"
        :value="patrolRunCount"
        hint="支持在大厅对比长周期走势"
        icon="overview"
        tone="success"
      />
    </section>

    <SurfaceCard class="p-4 space-y-4">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 class="text-sm font-semibold">定时巡检任务配置</h3>
          <p class="text-xs text-gray-500">
            支持 Cron 定时触发、Forbid
            防重入、相对基线退化检测，并直接复用平台站内信与飞书/Webhook
            渠道告警与自愈恢复通知。
          </p>
        </div>
        <BaseButton
          v-if="canManage"
          size="sm"
          variant="primary"
          :disabled="busy"
          @click="emit('create')"
        >
          + 新建定时巡检
        </BaseButton>
      </div>

      <EmptyState
        v-if="!patrols.length"
        title="暂未配置定时巡检规则"
        description="点击右上角“新建定时巡检”，为黄金回归集或核心冒烟集配置夜间/定时自动回归与退化告警。"
      />

      <div v-else class="space-y-3">
        <div
          v-for="item in patrols"
          :key="item.id"
          class="rounded-xl border border-gray-200 dark:border-dark-700 p-4 space-y-2.5 text-xs hover:border-primary-300 dark:hover:border-primary-700 transition-colors"
        >
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div class="space-y-1">
              <div class="flex flex-wrap items-center gap-2">
                <strong class="text-sm text-gray-900 dark:text-dark-100">
                  {{ item.name }}
                </strong>
                <StatusPill :tone="item.enabled ? 'info' : 'neutral'">
                  {{ item.enabled ? "调度已启用" : "已停用" }}
                </StatusPill>
                <StatusPill :tone="statusTone(item.last_status)">
                  {{ statusLabel(item.last_status) }}
                </StatusPill>
                <span
                  v-if="item.consecutive_failures > 0"
                  class="px-2 py-0.5 rounded bg-rose-50 dark:bg-rose-950/40 text-rose-700 dark:text-rose-300 font-semibold"
                >
                  连续异常 {{ item.consecutive_failures }} 次
                </span>
              </div>
              <div
                class="flex flex-wrap items-center gap-x-3 gap-y-1 text-gray-500"
              >
                <span>
                  题库：<strong class="text-gray-700 dark:text-dark-200">{{
                    item.suite_name || item.suite_id.slice(0, 8)
                  }}</strong>
                  ({{
                    item.version_policy === "pinned"
                      ? "锁定版本"
                      : "跟随最新冻结版"
                  }})
                </span>
                <span>
                  靶场：{{
                    item.target_project_name ||
                    item.target_project_id.slice(0, 8)
                  }}
                  · {{ item.target_agent_name || item.target_graph_id }}
                  <template v-if="item.target_model_name">
                    · {{ item.target_model_name }}</template
                  >
                </span>
                <span v-if="item.case_keys?.length">
                  冒烟范围：{{ item.case_keys.length }} 题
                </span>
              </div>
              <div
                class="flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[11px] text-gray-500"
              >
                <span>Cron: {{ item.cron_expr }} ({{ item.timezone }})</span>
                <span
                  >下次触发:
                  {{
                    item.enabled ? formatTime(item.next_run_at) : "已停用"
                  }}</span
                >
                <span>上次触发: {{ formatTime(item.last_triggered_at) }}</span>
              </div>
            </div>

            <div class="flex flex-wrap items-center gap-1.5">
              <BaseButton
                v-if="item.last_run_id"
                size="sm"
                variant="secondary"
                @click="emit('viewRun', item.last_run_id)"
              >
                最近结果
                <template
                  v-if="
                    item.last_run_score !== null &&
                    item.last_run_score !== undefined
                  "
                >
                  ({{ Math.round(item.last_run_score * 100) }}%)
                </template>
              </BaseButton>
              <BaseButton
                v-if="canManage"
                size="sm"
                variant="primary"
                :disabled="
                  busy || !item.target_agent_id || !item.target_model_id
                "
                @click="emit('triggerNow', item)"
              >
                ▶ 立即试跑
              </BaseButton>
              <BaseButton
                v-if="canManage"
                size="sm"
                variant="secondary"
                :disabled="busy"
                @click="emit('toggleEnabled', item)"
              >
                {{ item.enabled ? "停用" : "启用" }}
              </BaseButton>
              <BaseButton
                v-if="canManage"
                size="sm"
                variant="secondary"
                :disabled="busy"
                @click="emit('edit', item)"
              >
                编辑
              </BaseButton>
              <BaseButton
                v-if="canManage"
                size="sm"
                variant="danger"
                :disabled="busy"
                @click="emit('delete', item)"
              >
                删除
              </BaseButton>
            </div>
          </div>

          <div
            v-if="item.last_message"
            class="px-3 py-2 rounded-lg bg-gray-50 dark:bg-dark-800/70 text-[11px] text-gray-600 dark:text-dark-300"
          >
            最近调度回执：{{ item.last_message }}
          </div>
        </div>
      </div>
    </SurfaceCard>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRouter } from "vue-router";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseDrawer from "@/components/base/BaseDrawer.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import PaginationBar from "@/components/platform/PaginationBar.vue";
import StateBanner from "@/components/platform/StateBanner.vue";
import StatusPill from "@/components/platform/StatusPill.vue";
import { useScheduledTaskRuns } from "../composables/useScheduledTaskRuns";
import type { ScheduledTask } from "../types";
import { resolveTaskErrorInfo } from "../utils/error-mapping";
import { formatDisplayTime } from "../utils/timezone";

const props = defineProps<{
  show: boolean;
  projectId: string;
  task?: ScheduledTask | null;
}>();

const emit = defineEmits<{
  (e: "close"): void;
}>();

const router = useRouter();

const projIdRef = computed(() => props.projectId);
const taskIdRef = computed(() => props.task?.id || "");

const {
  items: runs,
  total,
  page,
  pageSize,
  loading,
  error,
  refresh,
} = useScheduledTaskRuns(projIdRef, taskIdRef);

const successCount = computed(
  () => runs.value.filter((r) => r.status === "success").length,
);
const errorCount = computed(
  () => runs.value.filter((r) => r.status === "error" || r.error_code).length,
);

function navigateToChat(threadId: string) {
  if (!threadId || !props.projectId) return;
  router.push(
    `/workspace/projects/${encodeURIComponent(props.projectId)}/chat/${encodeURIComponent(threadId)}`,
  );
}

function runStatusTone(status: string) {
  switch (status) {
    case "success":
      return "success";
    case "running":
      return "info";
    case "pending":
      return "warning";
    case "error":
    case "timeout":
    case "interrupted":
      return "danger";
    default:
      return "neutral";
  }
}
</script>

<template>
  <BaseDrawer
    :show="show"
    title="运行轨迹与执行历史"
    width="xl"
    @close="emit('close')"
  >
    <div class="space-y-4">
      <!-- 顶部工业级摘要看板 -->
      <div
        v-if="task"
        class="rounded-xl border border-border/70 bg-surface/90 p-4 shadow-xs dark:bg-dark-900/80 space-y-3"
      >
        <div class="flex items-start justify-between gap-3">
          <div>
            <div class="font-semibold text-sm text-foreground tracking-tight">
              {{ task.title }}
            </div>
            <div
              class="text-[11px] text-muted-foreground font-mono mt-0.5 flex items-center gap-2"
            >
              <span>Agent: {{ task.agent_key }}</span>
              <span>•</span>
              <span>时区: {{ task.timezone }}</span>
            </div>
          </div>
          <BaseButton
            variant="secondary"
            size="xs"
            :disabled="loading"
            class="rounded-lg shadow-xs"
            @click="refresh"
          >
            <BaseIcon name="refresh" size="xs" class="mr-1" />
            刷新记录
          </BaseButton>
        </div>

        <!-- 统计指标胶囊 -->
        <div
          class="flex items-center gap-2 pt-2 border-t border-border/40 text-xs"
        >
          <div
            class="px-2.5 py-1 rounded-lg bg-surface-subtle font-mono text-muted-foreground text-[11px]"
          >
            当前页记录:
            <span class="font-semibold text-foreground">{{ runs.length }}</span>
            / {{ total }}
          </div>
          <div
            class="px-2.5 py-1 rounded-lg bg-emerald-500/10 text-emerald-600 font-mono text-[11px] font-semibold"
          >
            成功: {{ successCount }}
          </div>
          <div
            v-if="errorCount > 0"
            class="px-2.5 py-1 rounded-lg bg-rose-500/10 text-rose-600 font-mono text-[11px] font-semibold"
          >
            失败: {{ errorCount }}
          </div>
        </div>
      </div>

      <StateBanner
        v-if="error"
        variant="danger"
        title="获取历史失败"
        :description="error"
      />

      <!-- 加载与空态 -->
      <div
        v-if="loading && runs.length === 0"
        class="py-16 text-center text-xs text-muted-foreground"
      >
        <BaseIcon
          name="refresh"
          size="md"
          class="mx-auto mb-2 animate-spin text-primary"
        />
        <span>加载执行历史轨迹中...</span>
      </div>

      <div
        v-else-if="runs.length === 0"
        class="py-16 text-center space-y-2 rounded-xl border border-dashed border-border/60 bg-surface-subtle"
      >
        <div class="text-xs font-medium text-foreground">暂无执行记录</div>
        <p class="text-[11px] text-muted-foreground">
          该定时任务尚未派发任何执行记录，可点击卡片上的【立即运行】进行测试验证。
        </p>
      </div>

      <!-- 时间线轨道 (Timeline Track) -->
      <div
        v-else
        class="relative pl-6 space-y-3 before:absolute before:left-2.5 before:top-3 before:bottom-3 before:w-0.5 before:bg-border/60"
      >
        <div
          v-for="run in runs"
          :key="run.run_id"
          class="relative rounded-xl border border-border/70 bg-surface/90 p-3.5 shadow-xs transition-all hover:border-border-hover dark:bg-dark-900/80 space-y-2.5"
        >
          <!-- 时间线打点 -->
          <span
            class="absolute -left-6 top-4 h-3 w-3 rounded-full border-2 border-surface"
            :class="
              run.status === 'success'
                ? 'bg-emerald-500 ring-2 ring-emerald-500/20'
                : run.status === 'running'
                  ? 'bg-primary ring-2 ring-primary/20 animate-pulse'
                  : 'bg-rose-500 ring-2 ring-rose-500/20'
            "
          />

          <!-- 头部：状态、触发方式与时间 -->
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <StatusPill :tone="runStatusTone(run.status)" class="font-medium">
                {{ run.status }}
              </StatusPill>
              <span
                class="px-2 py-0.5 text-[10px] rounded-md font-medium"
                :class="
                  run.trigger === 'manual'
                    ? 'bg-purple-500/10 text-purple-600'
                    : 'bg-blue-500/10 text-blue-600'
                "
              >
                {{ run.trigger === "manual" ? "手动触发" : "周期调度" }}
              </span>
            </div>
            <span class="text-[11px] text-muted-foreground font-mono">
              {{ formatDisplayTime(run.created_at, task?.timezone) }}
            </span>
          </div>

          <!-- 错误诊断告警卡片 -->
          <div
            v-if="run.status === 'error' || run.error_code"
            class="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/20 text-xs text-rose-600 dark:text-rose-400 space-y-1"
          >
            <div class="font-semibold text-xs flex items-center gap-1">
              <BaseIcon name="alert" size="xs" />
              <span>[{{ resolveTaskErrorInfo(run.error_code).label }}]</span>
            </div>
            <p class="text-[11px] leading-relaxed opacity-90">
              {{ resolveTaskErrorInfo(run.error_code).description }}
            </p>
          </div>

          <!-- 底部：Run ID 与直达会话链接 -->
          <div
            class="flex items-center justify-between pt-2 border-t border-border/30 text-[11px] text-muted-foreground"
          >
            <span class="font-mono truncate max-w-[220px]" :title="run.run_id">
              ID: {{ run.run_id }}
            </span>
            <button
              v-if="run.thread_id"
              type="button"
              class="group flex items-center gap-1 text-primary hover:text-primary-hover font-semibold transition-colors"
              @click="navigateToChat(run.thread_id)"
            >
              <span>查看会话</span>
              <span class="transition-transform group-hover:translate-x-0.5"
                >&rarr;</span
              >
            </button>
          </div>
        </div>
      </div>

      <!-- 分页控件 -->
      <PaginationBar
        v-if="total > pageSize"
        v-model:page="page"
        v-model:page-size="pageSize"
        :total="total"
        :disabled="loading"
      />
    </div>
  </BaseDrawer>
</template>

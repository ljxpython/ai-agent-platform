<script setup lang="ts">
import { computed, ref } from "vue";
import ChatTodoStatusBadge, {
  type TodoBadgeStatus,
} from "./ChatTodoStatusBadge.vue";

type ChatPlanTodo = { id: string; content: string; status: TodoBadgeStatus };
type ChatPlanView = {
  planTodos: ChatPlanTodo[];
  ephemeralTodos: ChatPlanTodo[];
  activeTask: ChatPlanTodo | null;
  totalTasks: number;
  completedTasks: number;
  allTasksCompleted: boolean;
  hasFrozenPlan: boolean;
};

const props = defineProps<{
  planView: ChatPlanView;
}>();

const emit = defineEmits<{
  openTasks: [];
}>();

const expanded = ref(false);

const percent = computed(() => {
  if (!props.planView.totalTasks) return 0;
  return Math.round(
    (props.planView.completedTasks / props.planView.totalTasks) * 100,
  );
});

const ringCircumference = 2 * Math.PI * 6;
const ringDashOffset = computed(() => {
  const ratio = Math.min(1, Math.max(0, percent.value / 100));
  return ringCircumference * (1 - ratio);
});

const statusSummary = computed(() => {
  if (props.planView.allTasksCompleted) {
    return `已完成全部 ${props.planView.totalTasks} 项待办任务`;
  }
  if (props.planView.activeTask) {
    return `正在执行：${props.planView.activeTask.content}`;
  }
  return "待办任务计划已就绪";
});

function formatStep(idx: number): string {
  const num = idx + 1;
  return `#${num < 10 ? "0" + num : num}`;
}
</script>

<template>
  <div
    v-if="planView.totalTasks > 0"
    data-testid="composer-task-tray"
    class="relative z-10 -mb-px overflow-hidden rounded-t-2xl border border-b-0 transition-all duration-200 backdrop-blur-md"
    :class="
      planView.allTasksCompleted
        ? 'border-emerald-200/80 bg-gradient-to-b from-emerald-50/30 to-white/95 shadow-[0_-2px_12px_rgba(16,185,129,0.04)] dark:border-emerald-900/40 dark:from-emerald-950/20 dark:to-dark-900/95'
        : 'border-gray-200/85 bg-white/95 shadow-[0_-2px_12px_rgba(0,0,0,0.03)] dark:border-dark-700/80 dark:bg-dark-900/95'
    "
  >
    <!-- 向上展开的待办清单详情面板 -->
    <div
      v-if="expanded"
      data-testid="task-tray-list"
      class="border-b border-gray-100/90 bg-white/70 px-4 py-3 dark:border-dark-700/70 dark:bg-dark-900/70"
    >
      <!-- 清单头部：标题、进度与跳转待办看板 -->
      <div class="mb-2.5 flex items-center justify-between">
        <div class="flex items-center gap-2">
          <span class="text-xs font-semibold text-gray-800 dark:text-dark-100">
            任务执行清单
          </span>
          <span
            class="rounded-full px-2 py-0.5 font-mono text-[10px] font-semibold"
            :class="
              planView.allTasksCompleted
                ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300'
                : 'bg-primary-50 text-primary-700 dark:bg-primary-950/50 dark:text-primary-300'
            "
          >
            {{ planView.completedTasks }}/{{ planView.totalTasks }}
          </span>
        </div>

        <button
          type="button"
          data-testid="open-task-drawer-btn"
          class="inline-flex cursor-pointer items-center gap-1 rounded-lg px-2 py-0.5 text-xs font-medium text-primary-600 transition-colors hover:bg-primary-50 hover:text-primary-700 dark:text-primary-400 dark:hover:bg-primary-950/40"
          @click.stop="emit('openTasks')"
        >
          <span>待办看板</span>
          <span class="text-[10px]" aria-hidden="true">↗</span>
        </button>
      </div>

      <!-- 任务项滚动列表 -->
      <div class="max-h-52 space-y-1.5 overflow-y-auto pr-1">
        <div
          v-for="(item, idx) in planView.planTodos"
          :key="item.id ?? idx"
          class="group flex items-center gap-2.5 rounded-xl border border-transparent px-2.5 py-1.5 text-xs transition-all"
          :class="
            item.status === 'in_progress'
              ? 'border-primary-200/80 bg-primary-50/40 text-gray-900 shadow-2xs dark:border-primary-900/50 dark:bg-primary-950/25 dark:text-white'
              : item.status === 'completed'
                ? 'bg-gray-50/50 hover:bg-gray-50 dark:bg-dark-800/30 dark:hover:bg-dark-800/50'
                : 'hover:bg-gray-50/70 dark:hover:bg-dark-800/40'
          "
        >
          <!-- 步骤编号微标 -->
          <span
            class="inline-flex shrink-0 items-center justify-center font-mono text-[10px] font-semibold text-gray-400 dark:text-dark-400"
          >
            {{ formatStep(idx) }}
          </span>

          <!-- 单项任务状态矢量微徽章 -->
          <ChatTodoStatusBadge
            :status="item.status"
            size="sm"
            class="shrink-0"
          />

          <!-- 任务内容文本（彻底去除粗暴的删除线，使用清晰优雅的灰阶层级） -->
          <span
            class="min-w-0 flex-1 truncate text-xs leading-relaxed"
            :class="{
              'font-semibold text-gray-900 dark:text-white':
                item.status === 'in_progress',
              'text-gray-500 dark:text-dark-400': item.status === 'completed',
              'text-gray-700 dark:text-dark-200': item.status === 'pending',
            }"
            :title="item.content"
          >
            {{ item.content }}
          </span>

          <!-- 状态轻量微标 -->
          <span
            v-if="item.status === 'in_progress'"
            class="inline-flex shrink-0 items-center gap-1 rounded-full bg-primary-100/80 px-2 py-0.5 text-[10px] font-medium text-primary-700 dark:bg-primary-950/70 dark:text-primary-300"
          >
            <span
              class="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-primary-500"
            />
            执行中
          </span>
          <span
            v-else-if="item.status === 'completed'"
            class="shrink-0 text-[10px] font-medium text-emerald-600/80 dark:text-emerald-400/80"
          >
            已完成
          </span>
          <span
            v-else
            class="shrink-0 text-[10px] font-medium text-gray-400 dark:text-dark-400"
          >
            待处理
          </span>
        </div>
      </div>
    </div>

    <!-- 底部托盘常驻控制条（整条可点击平滑展开/收起） -->
    <button
      type="button"
      data-testid="toggle-task-tray"
      class="flex w-full cursor-pointer items-center justify-between gap-3 px-4 py-2 text-left text-xs transition-colors hover:bg-gray-50/80 dark:hover:bg-dark-800/60"
      :title="expanded ? '收起任务清单' : '展开任务清单'"
      @click="expanded = !expanded"
    >
      <div class="flex min-w-0 flex-1 items-center gap-2.5">
        <!-- 完成态：翠绿小圆勾图标；执行态：SVG 环形进度圈 -->
        <svg
          v-if="planView.allTasksCompleted"
          data-testid="task-completed-icon"
          class="h-4 w-4 shrink-0 text-emerald-500"
          viewBox="0 0 16 16"
          fill="none"
        >
          <circle
            cx="8"
            cy="8"
            r="6.5"
            class="fill-emerald-500/15 stroke-emerald-500"
            stroke-width="1.5"
          />
          <path
            d="M5.2 8.1L7.1 10L11 6"
            stroke="currentColor"
            stroke-width="1.6"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
        <svg
          v-else
          data-testid="task-progress-ring"
          class="h-4 w-4 shrink-0 -rotate-90"
          viewBox="0 0 16 16"
          fill="none"
        >
          <circle
            cx="8"
            cy="8"
            r="6"
            class="stroke-gray-200 dark:stroke-dark-700"
            stroke-width="2"
          />
          <circle
            cx="8"
            cy="8"
            r="6"
            class="stroke-primary-600 transition-all duration-300 dark:stroke-primary-400"
            stroke-width="2"
            stroke-linecap="round"
            :stroke-dasharray="ringCircumference"
            :stroke-dashoffset="ringDashOffset"
          />
        </svg>

        <span
          class="truncate text-xs"
          :class="
            planView.allTasksCompleted
              ? 'font-medium text-emerald-700 dark:text-emerald-300'
              : 'font-medium text-gray-800 dark:text-gray-100'
          "
        >
          {{ statusSummary }}
        </span>
      </div>

      <div class="flex shrink-0 items-center gap-2">
        <span
          class="rounded-full px-2 py-0.5 font-mono text-[10px] font-semibold leading-none"
          :class="
            planView.allTasksCompleted
              ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300'
              : 'bg-gray-100 text-gray-700 dark:bg-dark-700 dark:text-dark-200'
          "
        >
          {{ planView.completedTasks }}/{{ planView.totalTasks }}
        </span>

        <!-- 顺滑旋转的 SVG 矢量 Chevron 箭头（彻底抛弃字符 ▾/▴） -->
        <svg
          class="h-3.5 w-3.5 text-gray-400 transition-transform duration-200 dark:text-dark-400"
          :class="{ 'rotate-180': expanded }"
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="M4 10l4-4 4 4" />
        </svg>
      </div>
    </button>
  </div>
</template>

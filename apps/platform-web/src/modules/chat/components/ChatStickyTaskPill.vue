<script setup lang="ts">
import { computed, ref } from "vue";

type ChatPlanTodo = { id: string; content: string; status: "pending" | "in_progress" | "completed" };
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
  return Math.round((props.planView.completedTasks / props.planView.totalTasks) * 100);
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
</script>

<template>
  <div
    v-if="planView.totalTasks > 0"
    data-testid="composer-task-tray"
    class="relative z-10 -mb-px overflow-hidden rounded-t-2xl border border-b-0 border-gray-200/85 bg-gray-50/95 shadow-[0_-2px_10px_rgba(0,0,0,0.02)] backdrop-blur-md transition-all dark:border-dark-700/80 dark:bg-dark-800/90"
  >
    <!-- 向上展开的待办清单详情面板 -->
    <div
      v-if="expanded"
      data-testid="task-tray-list"
      class="border-b border-gray-200/75 bg-white/90 px-3.5 py-2.5 dark:border-dark-700/75 dark:bg-dark-900/90"
    >
      <div class="mb-2 flex items-center justify-between text-[11px] text-gray-500 dark:text-dark-300">
        <span class="font-semibold text-gray-700 dark:text-gray-200">
          任务执行清单 ({{ planView.completedTasks }}/{{ planView.totalTasks }})
        </span>
        <button
          type="button"
          data-testid="open-task-drawer-btn"
          class="inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-medium text-primary-600 transition-colors hover:bg-primary-50 hover:text-primary-700 dark:text-primary-400 dark:hover:bg-primary-950/40"
          @click.stop="emit('openTasks')"
        >
          <span>待办看板</span>
          <span aria-hidden="true">↗</span>
        </button>
      </div>

      <div class="max-h-48 space-y-1.5 overflow-y-auto pr-1">
        <div
          v-for="(item, idx) in planView.planTodos"
          :key="item.id ?? idx"
          class="flex items-start gap-2 rounded-lg px-1.5 py-1 text-xs transition-colors"
          :class="item.status === 'in_progress' ? 'bg-blue-50/60 dark:bg-blue-950/25' : ''"
        >
          <!-- 单项任务状态图标 -->
          <span class="mt-0.5 flex h-3.5 w-3.5 shrink-0 items-center justify-center">
            <svg
              v-if="item.status === 'completed'"
              class="h-3.5 w-3.5 text-emerald-500"
              viewBox="0 0 16 16"
              fill="none"
            >
              <circle
                cx="8"
                cy="8"
                r="7"
                class="fill-emerald-500/15 stroke-emerald-500"
                stroke-width="1.5"
              />
              <path
                d="M5 8.2L7.1 10.3L11.2 6"
                stroke="currentColor"
                stroke-width="1.6"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
            <span
              v-else-if="item.status === 'in_progress'"
              class="relative flex h-2.5 w-2.5"
            >
              <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75" />
              <span class="relative inline-flex h-2.5 w-2.5 rounded-full bg-blue-500" />
            </span>
            <span
              v-else
              class="h-2.5 w-2.5 rounded-full border border-gray-300 dark:border-dark-500"
            />
          </span>

          <span
            class="flex-1 truncate leading-relaxed"
            :class="{
              'font-medium text-gray-900 dark:text-white': item.status === 'in_progress',
              'text-gray-400 line-through dark:text-gray-500': item.status === 'completed',
              'text-gray-600 dark:text-gray-300': item.status === 'pending'
            }"
          >
            {{ item.content }}
          </span>

          <span
            class="shrink-0 rounded px-1.5 py-0.5 text-[10px]"
            :class="{
              'bg-blue-100/80 text-blue-700 font-medium dark:bg-blue-950/60 dark:text-blue-300': item.status === 'in_progress',
              'text-emerald-600/80 dark:text-emerald-400/80': item.status === 'completed',
              'text-gray-400 dark:text-dark-400': item.status === 'pending'
            }"
          >
            {{ item.status === 'in_progress' ? '进行中' : item.status === 'completed' ? '已完成' : '待处理' }}
          </span>
        </div>
      </div>
    </div>

    <!-- 底部托盘常驻控制条（整条可点击展开/收起） -->
    <button
      type="button"
      data-testid="toggle-task-tray"
      class="flex w-full items-center justify-between gap-3 px-3.5 py-1.5 text-left text-xs transition-colors hover:bg-gray-100/80 dark:hover:bg-dark-800"
      :title="expanded ? '收起任务清单' : '展开任务清单'"
      @click="expanded = !expanded"
    >
      <div class="flex min-w-0 flex-1 items-center gap-2">
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
          class="truncate"
          :class="
            planView.allTasksCompleted
              ? 'text-gray-500 dark:text-dark-300'
              : 'font-medium text-gray-700 dark:text-gray-200'
          "
        >
          {{ statusSummary }}
        </span>
      </div>

      <div class="flex shrink-0 items-center gap-2">
        <span
          class="rounded-md px-1.5 py-0.5 font-mono text-[11px] font-medium"
          :class="
            planView.allTasksCompleted
              ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
              : 'bg-gray-200/75 text-gray-700 dark:bg-dark-700 dark:text-dark-200'
          "
        >
          {{ planView.completedTasks }}/{{ planView.totalTasks }}
        </span>
        <span
          aria-hidden="true"
          class="text-[11px] text-gray-400 transition-transform duration-200 dark:text-dark-400"
        >
          {{ expanded ? "▾" : "▴" }}
        </span>
      </div>
    </button>
  </div>
</template>

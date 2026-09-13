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
const isDismissed = ref(false);

const percent = computed(() => {
  if (!props.planView.totalTasks) return 0;
  return Math.round((props.planView.completedTasks / props.planView.totalTasks) * 100);
});

const statusSummary = computed(() => {
  if (props.planView.allTasksCompleted) return "所有待办任务已顺利完成";
  if (props.planView.activeTask) return `进行中: ${props.planView.activeTask.content}`;
  return "待办任务计划已就绪";
});
</script>

<template>
  <!-- 折叠/已关闭时的微型恢复胶囊，悬浮在右上角紧凑贴顶，不占用大边距，不遮挡正文 -->
  <div
    v-if="planView.totalTasks > 0 && isDismissed"
    class="sticky top-0 z-20 -mt-2 mb-1 flex justify-end md:-mt-3"
  >
    <button
      type="button"
      class="inline-flex items-center gap-1.5 rounded-full border border-gray-200/90 bg-white/95 px-3 py-1 text-xs font-medium text-gray-700 shadow-sm backdrop-blur transition-all hover:bg-gray-100 hover:text-gray-900 dark:border-dark-700 dark:bg-dark-900/95 dark:text-dark-200 dark:hover:bg-dark-800"
      title="点击重新展开任务进度条"
      data-testid="restore-task-pill"
      @click="isDismissed = false"
    >
      <span
        class="h-2 w-2 rounded-full"
        :class="{
          'bg-emerald-500': planView.allTasksCompleted,
          'bg-blue-500 animate-pulse': planView.activeTask,
          'bg-gray-400': !planView.allTasksCompleted && !planView.activeTask
        }"
      />
      <span>任务 {{ planView.completedTasks }}/{{ planView.totalTasks }}</span>
      <span class="text-gray-400">展开 ▾</span>
    </button>
  </div>

  <div
    v-else-if="planView.totalTasks > 0"
    class="sticky top-0 z-20 mb-3 rounded-xl border border-gray-200/90 bg-white/95 p-2.5 px-3.5 shadow-sm backdrop-blur-md transition-all dark:border-dark-700 dark:bg-dark-900/95"
  >
    <div class="flex items-center justify-between gap-3 text-xs">
      <div class="flex min-w-0 flex-1 items-center gap-2.5">
        <span
          class="inline-block h-2 w-2 shrink-0 rounded-full"
          :class="{
            'bg-emerald-500 ring-2 ring-emerald-100 dark:ring-emerald-950': planView.allTasksCompleted,
            'bg-blue-500 animate-pulse ring-2 ring-blue-100 dark:ring-blue-950': planView.activeTask,
            'bg-gray-400': !planView.allTasksCompleted && !planView.activeTask
          }"
        />
        <span class="font-medium text-gray-900 dark:text-white shrink-0">
          任务进度
        </span>
        <span class="truncate text-gray-600 dark:text-dark-200">
          {{ statusSummary }}
        </span>
      </div>

      <div class="flex shrink-0 items-center gap-2">
        <span class="rounded bg-gray-100 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-gray-700 dark:bg-dark-800 dark:text-dark-200">
          {{ planView.completedTasks }}/{{ planView.totalTasks }}
        </span>
        <button
          type="button"
          class="font-medium text-primary-600 hover:text-primary-700 hover:underline dark:text-primary-400"
          @click="emit('openTasks')"
        >
          查看待办看板 →
        </button>
        <button
          type="button"
          class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 p-0.5"
          :title="expanded ? '收起详情' : '展开微型列表'"
          @click="expanded = !expanded"
        >
          <span aria-hidden="true">{{ expanded ? "▴" : "▾" }}</span>
        </button>
        <button
          type="button"
          class="ml-1 rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-dark-800 dark:hover:text-gray-200"
          title="收起任务进度条"
          aria-label="收起任务进度"
          data-testid="dismiss-task-pill"
          @click="isDismissed = true"
        >
          <span
            aria-hidden="true"
            class="text-xs font-bold leading-none"
          >✕</span>
        </button>
      </div>
    </div>

    <!-- 微型进度条 -->
    <div class="mt-2 h-1 w-full overflow-hidden rounded-full bg-gray-100 dark:bg-dark-800">
      <div
        class="h-full transition-all duration-300"
        :class="planView.allTasksCompleted ? 'bg-emerald-500' : 'bg-primary-600 dark:bg-primary-500'"
        :style="{ width: `${percent}%` }"
      />
    </div>

    <!-- 内联快速展开的微型待办列表 -->
    <div
      v-if="expanded"
      class="mt-3 space-y-1.5 border-t border-gray-100 pt-2.5 dark:border-dark-800"
    >
      <div
        v-for="(item, idx) in planView.planTodos"
        :key="item.id ?? idx"
        class="flex items-start gap-2 text-xs"
      >
        <span
          class="mt-1 inline-block h-1.5 w-1.5 shrink-0 rounded-full"
          :class="{
            'bg-blue-500': item.status === 'in_progress',
            'bg-emerald-500': item.status === 'completed',
            'border border-gray-400 bg-transparent': item.status === 'pending'
          }"
        />
        <span
          class="flex-1 truncate"
          :class="{
            'font-medium text-gray-900 dark:text-white': item.status === 'in_progress',
            'text-gray-400 line-through dark:text-gray-500': item.status === 'completed',
            'text-gray-600 dark:text-gray-300': item.status === 'pending'
          }"
        >
          {{ item.content }}
        </span>
        <span
          class="shrink-0 text-[10px]"
          :class="{
            'text-blue-600 dark:text-blue-400 font-medium': item.status === 'in_progress',
            'text-emerald-600 dark:text-emerald-400': item.status === 'completed',
            'text-gray-400': item.status === 'pending'
          }"
        >
          {{ item.status === 'in_progress' ? '进行中' : item.status === 'completed' ? '已完成' : '待处理' }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, ref } from "vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import ConfirmDialog from "@/components/base/ConfirmDialog.vue";
import BackgroundTaskItem from "./BackgroundTaskItem.vue";
import BackgroundTaskLogViewer from "./BackgroundTaskLogViewer.vue";
import {
  useBackgroundTasks,
  type UseBackgroundTasksReturn,
} from "@/modules/chat/composables/useBackgroundTasks";

const props = defineProps<{
  projectId: string;
  threadId?: string;
}>();

// 优先从上层 ChatSession 注入单例状态机，若未提供则降级本地创建
const injectedTasks = inject<UseBackgroundTasksReturn | null>(
  "backgroundTasks",
  null,
);
const localTasks = injectedTasks
  ? null
  : useBackgroundTasks(
      computed(() => props.projectId),
      computed(() => props.threadId),
    );

const taskState = computed<UseBackgroundTasksReturn>(
  () => (injectedTasks || localTasks)!,
);

// 取消确认弹窗状态
const showCancelConfirm = ref(false);
const pendingCancelTaskId = ref<string | null>(null);

function requestCancel(taskId: string) {
  pendingCancelTaskId.value = taskId;
  showCancelConfirm.value = true;
}

async function handleConfirmCancel() {
  const tid = pendingCancelTaskId.value;
  showCancelConfirm.value = false;
  pendingCancelTaskId.value = null;
  if (!tid) return;

  try {
    await taskState.value.cancelTask(tid);
  } catch {
    // 错误在 service/composable 已更新
  }
}

const activeTask = computed(() => {
  if (!taskState.value.activeLogTaskId.value) return null;
  return (
    taskState.value.tasks.value.find(
      (t) => t.task_id === taskState.value.activeLogTaskId.value,
    ) || null
  );
});
</script>

<template>
  <div
    class="flex h-full min-h-0 flex-col overflow-hidden bg-gray-50/40 dark:bg-dark-950/40"
  >
    <!-- 头部工具栏 -->
    <div
      class="flex h-10 shrink-0 items-center justify-between border-b border-gray-200 bg-white px-3 dark:border-dark-800 dark:bg-dark-900"
    >
      <div
        class="flex items-center gap-2 text-xs font-semibold text-gray-700 dark:text-dark-200"
      >
        <span>后台任务</span>
        <span
          v-if="taskState.tasks.value.length > 0"
          class="rounded-full bg-gray-100 px-1.5 py-0.2 text-[10px] text-gray-600 dark:bg-dark-800 dark:text-dark-300"
        >
          {{ taskState.tasks.value.length }}
        </span>
      </div>
      <div class="flex items-center gap-1">
        <button
          type="button"
          class="rounded p-1 text-gray-500 hover:bg-gray-100 disabled:opacity-40 dark:text-dark-400 dark:hover:bg-dark-800 transition-colors"
          :disabled="taskState.loading.value || taskState.refreshing.value"
          title="刷新任务列表"
          @click="taskState.refresh()"
        >
          <BaseIcon
            name="refresh"
            class="h-3.5 w-3.5"
            :class="{
              'animate-spin':
                taskState.refreshing.value || taskState.loading.value,
            }"
          />
        </button>
      </div>
    </div>

    <!-- 列表容器 -->
    <div class="flex flex-1 min-h-0 flex-col overflow-hidden">
      <!-- 任务卡片滚动列表 -->
      <div class="flex-1 overflow-y-auto p-3 space-y-2.5">
        <div
          v-if="taskState.loading.value && taskState.tasks.value.length === 0"
          class="flex h-32 items-center justify-center text-xs text-gray-400"
        >
          <BaseIcon name="refresh" class="h-4 w-4 animate-spin mr-1.5" />
          正在获取任务...
        </div>

        <div
          v-else-if="taskState.error.value"
          class="rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-300"
        >
          {{ taskState.error.value }}
        </div>

        <div
          v-else-if="taskState.tasks.value.length === 0"
          data-testid="background-tasks-empty-state"
          class="flex h-48 flex-col items-center justify-center text-xs text-gray-400"
        >
          <BaseIcon
            name="runtime"
            class="h-8 w-8 text-gray-300 dark:text-dark-600 mb-2"
          />
          <span>暂无后台长任务</span>
        </div>

        <template v-else>
          <BackgroundTaskItem
            v-for="task in taskState.tasks.value"
            :key="task.task_id"
            :task="task"
            :is-selected="taskState.activeLogTaskId.value === task.task_id"
            :is-cancelling="taskState.cancellingTaskIds.value.has(task.task_id)"
            @view-logs="taskState.openTaskLog"
            @cancel="requestCancel"
          />
        </template>
      </div>

      <!-- 下半部分：内嵌日志抽屉 (展开时占据约 45% 高度) -->
      <div v-if="activeTask" class="h-56 shrink-0 shadow-lg transition-all">
        <BackgroundTaskLogViewer
          :task="activeTask"
          :output="taskState.logOutput.value"
          :loading="taskState.loadingLog.value"
          :error="taskState.logError.value"
          @refresh="taskState.fetchTaskLog(activeTask.task_id)"
          @close="taskState.closeTaskLog"
        />
      </div>
    </div>

    <!-- 取消二次确认弹窗 -->
    <ConfirmDialog
      :show="showCancelConfirm"
      title="取消后台任务确认"
      message="确认要取消该任务吗？系统将向运行中容器发送终止信号。注意：命令已经写入的文件或环境副作用不会自动回滚。"
      confirm-text="确认取消"
      danger
      @confirm="handleConfirmCancel"
      @cancel="showCancelConfirm = false"
    />
  </div>
</template>

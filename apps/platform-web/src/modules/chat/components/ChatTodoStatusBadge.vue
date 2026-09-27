<script setup lang="ts">
import { computed } from "vue";

export type TodoBadgeStatus =
  | "completed"
  | "in_progress"
  | "pending"
  | "failed"
  | "interrupted"
  | "skipped"
  | string;

const props = withDefaults(
  defineProps<{
    status: TodoBadgeStatus;
    size?: "sm" | "md";
  }>(),
  {
    size: "md",
  },
);

const statusMeta = computed(() => {
  switch (props.status) {
    case "completed":
      return {
        label: "已完成",
        color: "bg-emerald-500 text-white shadow-xs",
        type: "completed",
      };
    case "in_progress":
      return {
        label: "进行中",
        color: "text-blue-500",
        type: "in_progress",
      };
    case "failed":
      return {
        label: "执行失败",
        color: "bg-rose-500 text-white shadow-xs",
        type: "failed",
      };
    case "interrupted":
      return {
        label: "等待审批",
        color: "bg-amber-500 text-white shadow-xs",
        type: "interrupted",
      };
    case "skipped":
      return {
        label: "已跳过",
        color: "bg-gray-400 text-white",
        type: "skipped",
      };
    case "pending":
    default:
      return {
        label: "待处理",
        color:
          "border-2 border-gray-300 dark:border-dark-600 bg-white dark:bg-dark-900",
        type: "pending",
      };
  }
});
</script>

<template>
  <span
    class="inline-flex shrink-0 items-center justify-center select-none"
    :class="[
      size === 'sm' ? 'h-3.5 w-3.5' : 'h-[18px] w-[18px]',
      statusMeta.color,
      statusMeta.type !== 'in_progress' ? 'rounded-full' : '',
    ]"
    :title="statusMeta.label"
    :aria-label="statusMeta.label"
  >
    <!-- 已完成: 白色清晰小对勾 -->
    <svg
      v-if="statusMeta.type === 'completed'"
      class="h-3 w-3 stroke-[2.6]"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
    >
      <path
        d="M3.5 8.5L6.5 11.5L12.5 4.5"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
    </svg>

    <!-- 进行中: 高速旋转微转轮 (Spinner) -->
    <svg
      v-else-if="statusMeta.type === 'in_progress'"
      class="h-full w-full animate-spin"
      viewBox="0 0 24 24"
      fill="none"
    >
      <circle
        class="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        stroke-width="3"
      />
      <path
        class="opacity-90"
        fill="currentColor"
        d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
      />
    </svg>

    <!-- 失败: 白色小叉号 -->
    <svg
      v-else-if="statusMeta.type === 'failed'"
      class="h-2.5 w-2.5 stroke-[2.6]"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
    >
      <path d="M4 4L12 12M12 4L4 12" stroke-linecap="round" />
    </svg>

    <!-- 审批中断: 白色感叹号 -->
    <svg
      v-else-if="statusMeta.type === 'interrupted'"
      class="h-2.5 w-2.5 fill-current"
      viewBox="0 0 16 16"
    >
      <path
        d="M7.002 11a1 1 0 1 1 2 0 1 1 0 0 1-2 0zM7.1 4.995a.905.905 0 1 1 1.8 0l-.35 4.5a.55.55 0 0 1-1.1 0l-.35-4.5z"
      />
    </svg>

    <!-- 跳过: 白色横杠 -->
    <svg
      v-else-if="statusMeta.type === 'skipped'"
      class="h-2.5 w-2.5 stroke-[2.6]"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
    >
      <path d="M4 8H12" stroke-linecap="round" />
    </svg>

    <!-- 待处理: 内部精致微空心点缀 -->
    <span v-else class="h-1 w-1 rounded-full bg-gray-300 dark:bg-dark-600" />
  </span>
</template>

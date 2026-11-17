<script setup lang="ts">
export type TimeRangePreset = "1h" | "6h" | "24h" | "7d" | "30d";

interface Props {
  preset: TimeRangePreset;
  bucketSeconds: number;
  status: "all" | "ok" | "error";
  refreshInterval: number;
  loading?: boolean;
}

withDefaults(defineProps<Props>(), {
  preset: "24h",
  bucketSeconds: 300,
  status: "all",
  refreshInterval: 0,
  loading: false,
});

const emit = defineEmits<{
  (e: "update:preset", val: TimeRangePreset): void;
  (e: "update:bucketSeconds", val: number): void;
  (e: "update:status", val: "all" | "ok" | "error"): void;
  (e: "update:refreshInterval", val: number): void;
  (e: "refresh"): void;
}>();

const timePresets: {
  label: string;
  value: TimeRangePreset;
  defaultBucket: number;
}[] = [
  { label: "1小时", value: "1h", defaultBucket: 60 },
  { label: "6小时", value: "6h", defaultBucket: 300 },
  { label: "24小时", value: "24h", defaultBucket: 300 },
  { label: "7天", value: "7d", defaultBucket: 3600 },
  { label: "30天", value: "30d", defaultBucket: 86400 },
];

const bucketOptions = [
  { label: "自动 (Auto)", value: 0 },
  { label: "1 分钟", value: 60 },
  { label: "5 分钟", value: 300 },
  { label: "15 分钟", value: 900 },
  { label: "1 小时", value: 3600 },
  { label: "1 天", value: 86400 },
];

const statusOptions: { label: string; value: "all" | "ok" | "error" }[] = [
  { label: "全部状态", value: "all" },
  { label: "仅成功 (2xx)", value: "ok" },
  { label: "仅异常 (4xx/5xx)", value: "error" },
];

const refreshOptions = [
  { label: "刷新: 关闭", value: 0 },
  { label: "刷新: 30秒", value: 30000 },
  { label: "刷新: 60秒", value: 60000 },
];

function selectPreset(item: {
  label: string;
  value: TimeRangePreset;
  defaultBucket: number;
}) {
  emit("update:preset", item.value);
  // 如果是自动桶或跨度变动，切到该范围对应的最佳推荐桶
  emit("update:bucketSeconds", item.defaultBucket);
}
</script>

<template>
  <div
    class="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-gray-100 bg-white p-4 shadow-sm dark:border-dark-800 dark:bg-dark-900/90"
  >
    <!-- 左侧：时间预设 Pills -->
    <div class="flex flex-wrap items-center gap-2">
      <span class="text-xs font-semibold text-gray-400 dark:text-dark-500 mr-1"
        >时间跨度:</span
      >
      <div class="inline-flex rounded-xl bg-gray-100 p-1 dark:bg-dark-800">
        <button
          v-for="item in timePresets"
          :key="item.value"
          type="button"
          class="rounded-lg px-3 py-1.5 text-xs font-medium transition-all"
          :class="
            preset === item.value
              ? 'bg-white text-gray-900 shadow-sm dark:bg-dark-700 dark:text-white'
              : 'text-gray-600 hover:text-gray-900 dark:text-dark-300 dark:hover:text-white'
          "
          @click="selectPreset(item)"
        >
          {{ item.label }}
        </button>
      </div>

      <!-- 时间桶选择器 -->
      <div class="ml-2 flex items-center gap-1.5">
        <span class="text-xs text-gray-400 dark:text-dark-500">粒度:</span>
        <select
          :value="bucketSeconds"
          class="rounded-xl border border-gray-200 bg-white px-2.5 py-1.5 text-xs text-gray-700 focus:border-primary-500 focus:outline-none dark:border-dark-700 dark:bg-dark-800 dark:text-gray-200"
          @change="
            (e) =>
              emit(
                'update:bucketSeconds',
                Number((e.target as HTMLSelectElement).value),
              )
          "
        >
          <option
            v-for="opt in bucketOptions"
            :key="opt.value"
            :value="opt.value"
          >
            {{ opt.label }}
          </option>
        </select>
      </div>
    </div>

    <!-- 右侧：状态过滤与刷新控制 -->
    <div class="flex flex-wrap items-center gap-2.5">
      <!-- 状态过滤 -->
      <select
        :value="status"
        class="rounded-xl border border-gray-200 bg-white px-2.5 py-1.5 text-xs text-gray-700 focus:border-primary-500 focus:outline-none dark:border-dark-700 dark:bg-dark-800 dark:text-gray-200"
        @change="
          (e) =>
            emit('update:status', (e.target as HTMLSelectElement).value as any)
        "
      >
        <option v-for="s in statusOptions" :key="s.value" :value="s.value">
          {{ s.label }}
        </option>
      </select>

      <!-- 自动刷新下拉 -->
      <select
        :value="refreshInterval"
        class="rounded-xl border border-gray-200 bg-white px-2.5 py-1.5 text-xs text-gray-700 focus:border-primary-500 focus:outline-none dark:border-dark-700 dark:bg-dark-800 dark:text-gray-200"
        @change="
          (e) =>
            emit(
              'update:refreshInterval',
              Number((e.target as HTMLSelectElement).value),
            )
        "
      >
        <option v-for="r in refreshOptions" :key="r.value" :value="r.value">
          {{ r.label }}
        </option>
      </select>

      <!-- 手动立即刷新按钮 -->
      <button
        type="button"
        class="inline-flex items-center gap-1.5 rounded-xl border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 transition hover:bg-gray-50 active:scale-95 dark:border-dark-700 dark:bg-dark-800 dark:text-gray-200 dark:hover:bg-dark-700"
        :disabled="loading"
        @click="emit('refresh')"
      >
        <svg
          class="h-3.5 w-3.5 text-gray-500 dark:text-dark-400"
          :class="{ 'animate-spin text-primary-500': loading }"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.038 8.038 0 01-15.357-2m15.357 2H15"
          />
        </svg>
        <span>刷新</span>
      </button>
    </div>
  </div>
</template>

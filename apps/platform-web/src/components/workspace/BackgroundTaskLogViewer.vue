<script setup lang="ts">
import { computed, ref } from "vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import { stripAnsi } from "@/utils/ansi";
import { copyText } from "@/utils/clipboard";
import type { OutputV1, TaskV1 } from "@/modules/chat/background-tasks/types";

const props = defineProps<{
  task: TaskV1;
  output: OutputV1 | null;
  loading?: boolean;
  error?: string | null;
}>();

const emit = defineEmits<{
  close: [];
  refresh: [];
}>();

const copied = ref(false);

const cleanedText = computed(() => {
  const raw = props.output?.text || (props.output as any)?.output || "";
  if (!raw) return "";
  return stripAnsi(raw);
});

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

async function handleCopy() {
  if (!cleanedText.value) return;
  const ok = await copyText(cleanedText.value);
  if (ok) {
    copied.value = true;
    setTimeout(() => {
      copied.value = false;
    }, 2000);
  }
}
</script>

<template>
  <div
    class="flex h-full flex-col border-t border-gray-200 bg-gray-50/50 dark:border-dark-800 dark:bg-dark-950/60"
  >
    <!-- 日志操作顶栏 -->
    <div
      class="flex h-9 shrink-0 items-center justify-between border-b border-gray-200 px-3 bg-white dark:border-dark-800 dark:bg-dark-900"
    >
      <div
        class="flex items-center gap-2 text-xs font-medium text-gray-700 dark:text-dark-200"
      >
        <BaseIcon name="runtime" class="h-3.5 w-3.5 text-primary-500" />
        <span>日志快照 ({{ task.task_id.slice(0, 8) }})</span>
        <span
          v-if="task.status === 'running'"
          class="flex items-center gap-1 text-[11px] text-primary-600 dark:text-primary-400"
        >
          <span class="h-1.5 w-1.5 rounded-full bg-primary-500 animate-pulse" />
          运行中
        </span>
      </div>
      <div class="flex items-center gap-1">
        <button
          type="button"
          class="rounded p-1 text-gray-500 hover:bg-gray-100 dark:text-dark-400 dark:hover:bg-dark-800"
          :title="copied ? '已复制' : '复制日志'"
          :disabled="!cleanedText"
          @click="handleCopy"
        >
          <BaseIcon
            :name="copied ? 'check' : 'copy'"
            class="h-3.5 w-3.5"
            :class="{ 'text-emerald-500': copied }"
          />
        </button>
        <button
          type="button"
          class="rounded p-1 text-gray-500 hover:bg-gray-100 disabled:opacity-40 dark:text-dark-400 dark:hover:bg-dark-800"
          :disabled="loading"
          title="刷新日志"
          @click="emit('refresh')"
        >
          <BaseIcon
            name="refresh"
            class="h-3.5 w-3.5"
            :class="{ 'animate-spin': loading }"
          />
        </button>
        <button
          type="button"
          class="rounded p-1 text-gray-500 hover:bg-gray-100 dark:text-dark-400 dark:hover:bg-dark-800"
          title="关闭日志"
          @click="emit('close')"
        >
          <BaseIcon name="x" class="h-3.5 w-3.5" />
        </button>
      </div>
    </div>

    <!-- 截断或容量警告提示条 -->
    <div
      v-if="output && (output.truncated || output.omitted_bytes > 0)"
      class="flex items-center gap-2 border-b border-amber-200 bg-amber-50 px-3 py-1.5 text-xs text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-300"
    >
      <BaseIcon name="alert" class="h-3.5 w-3.5 shrink-0" />
      <span class="truncate">
        日志过长已截断，仅展示最近保留日志（保留
        {{ formatBytes(output.retained_bytes) }}，已省略
        {{ formatBytes(output.omitted_bytes) }}）。
      </span>
    </div>

    <!-- 日志展示主体 -->
    <div class="relative flex-1 overflow-auto p-3">
      <div
        v-if="loading && !output"
        class="flex h-full items-center justify-center text-xs text-gray-400"
      >
        <BaseIcon name="refresh" class="h-4 w-4 animate-spin mr-1.5" />
        正在读取日志...
      </div>
      <div
        v-else-if="error"
        class="flex h-full items-center justify-center text-xs text-rose-500"
      >
        {{ error }}
      </div>
      <div
        v-else-if="output && !output.available"
        class="flex h-full items-center justify-center text-xs text-gray-400"
      >
        日志源已释放或暂不可用
      </div>
      <div
        v-else-if="output && !cleanedText"
        class="flex h-full items-center justify-center text-xs text-gray-400"
      >
        暂无输出内容
      </div>
      <pre
        v-else-if="output"
        class="font-mono text-xs leading-relaxed text-gray-800 whitespace-pre-wrap select-text break-words dark:text-dark-100"
        >{{ cleanedText }}</pre
      >
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import type { AnyStream } from "@langchain/vue";
import { asObject, contentItems, type ToolItem } from "../transcript";
import MessageContent from "./MessageContent.vue";
import SubtaskDetail from "./SubtaskDetail.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";

const props = defineProps<{
  tool: ToolItem;
  stream?: AnyStream;
}>();

const emit = defineEmits<{ inspect: [tool: ToolItem] }>();

const expanded = ref(false);

const input = computed(() => asObject(props.tool.input));
const subagentType = computed(
  () =>
    (typeof input.value.subagent_type === "string" && input.value.subagent_type) ||
    (typeof input.value.name === "string" && input.value.name) ||
    "subagent",
);

const description = computed(() => {
  if (typeof input.value.description === "string") return input.value.description.trim();
  if (typeof input.value.prompt === "string") return input.value.prompt.trim();
  if (typeof input.value.task === "string") return input.value.task.trim();
  return "";
});

// Locate subagent discovery record to find its scoped execution namespace
const subagent = computed(() => {
  if (!props.stream?.subagents?.value) return undefined;
  const map = props.stream.subagents.value;
  return (
    map.get(props.tool.id) ||
    [...map.values()].find(
      (a) => a.id === props.tool.id || a.name === subagentType.value,
    )
  );
});

const namespace = computed(() => {
  if (subagent.value?.namespace && subagent.value.namespace.length > 0) {
    return subagent.value.namespace;
  }
  if (props.tool.id) {
    return [`tools:${props.tool.id}`];
  }
  return [];
});

const statusLabels: Record<string, string> = {
  running: "执行中",
  finished: "已返回",
  error: "失败",
  incomplete: "未完成 / 已中止",
};

/** Parse Python Command / ToolMessage string representation into clean Markdown */
function cleanOutputText(output: unknown): string {
  if (typeof output !== "string") return "";
  const raw = output.trim();
  // Check if output is a Python Command(...) or ToolMessage(...) repr string
  const match = /ToolMessage\([^)]*?content=(['"])([\s\S]*?)\1/i.exec(raw);
  if (match && match[2]) {
    return match[2]
      .replace(/\\n/g, "\n")
      .replace(/\\r/g, "\r")
      .replace(/\\t/g, "\t")
      .replace(/\\'/g, "'")
      .replace(/\\"/g, '"');
  }
  // Strip outer Command wrapper if present
  if (raw.startsWith("Command(") && raw.endsWith(")")) {
    return raw.slice(8, -1).trim();
  }
  return raw;
}

const cleanedOutput = computed(() => cleanOutputText(props.tool.output));
const outputBlocks = computed(() => {
  if (cleanedOutput.value) {
    return contentItems(cleanedOutput.value, `${props.tool.key}:output`);
  }
  if (props.tool.output !== undefined) {
    return contentItems(props.tool.output, `${props.tool.key}:output`);
  }
  return [];
});
</script>

<template>
  <div class="rounded-xl border border-gray-200 bg-gray-50/70 text-sm transition-colors dark:border-dark-700 dark:bg-dark-800/50">
    <button
      type="button"
      class="flex w-full items-center justify-between gap-3 p-3.5 text-left focus-visible:ring-2"
      :aria-expanded="expanded"
      @click="expanded = !expanded"
    >
      <div class="flex min-w-0 items-center gap-2.5">
        <span
          class="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg"
          :class="
            tool.status === 'running'
              ? 'bg-primary-100 text-primary-600 dark:bg-primary-950/50 dark:text-primary-400'
              : tool.status === 'error'
                ? 'bg-red-100 text-red-600 dark:bg-red-950/50 dark:text-red-400'
                : 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-400'
          "
        >
          <BaseIcon
            v-if="tool.status === 'running'"
            name="activity"
            class="h-4 w-4 animate-pulse"
          />
          <BaseIcon
            v-else-if="tool.status === 'error'"
            name="alert"
            class="h-4 w-4"
          />
          <BaseIcon
            v-else
            name="assistant"
            class="h-4 w-4"
          />
        </span>
        <div class="min-w-0">
          <div class="flex items-center gap-2">
            <span class="truncate font-semibold text-gray-900 dark:text-white">{{ subagentType }}</span>
            <span class="rounded bg-gray-200/80 px-1.5 py-0.5 text-[10px] font-medium text-gray-600 dark:bg-dark-700 dark:text-dark-300">
              子智能体
            </span>
          </div>
        </div>
      </div>

      <div class="flex items-center gap-2 shrink-0">
        <span
          class="text-xs font-medium"
          :class="
            tool.status === 'running'
              ? 'text-primary-600 dark:text-primary-400'
              : tool.status === 'error'
                ? 'text-red-600 dark:text-red-400'
                : 'text-emerald-600 dark:text-emerald-400'
          "
        >
          {{ statusLabels[tool.status] || tool.status }}
        </span>
        <span
          aria-hidden="true"
          class="text-gray-400 dark:text-dark-400"
        >{{ expanded ? "▾" : "▸" }}</span>
      </div>
    </button>

    <div
      v-if="description"
      class="px-3.5 pb-3 text-xs leading-relaxed text-gray-600 dark:text-dark-300"
      :class="{ 'line-clamp-3': !expanded }"
    >
      {{ description }}
    </div>

    <div
      v-if="expanded"
      class="space-y-3.5 border-t border-gray-200/80 p-3.5 dark:border-dark-700"
    >
      <div
        v-if="stream && namespace.length"
        class="rounded-lg border border-gray-200 bg-white p-3 dark:border-dark-700 dark:bg-dark-900"
      >
        <p class="mb-2 text-[11px] font-medium text-gray-500 dark:text-dark-400">
          子任务执行过程
        </p>
        <SubtaskDetail
          :stream="stream"
          :namespace="namespace"
          :running="tool.status === 'running'"
          @inspect="emit('inspect', $event)"
        />
      </div>

      <div
        v-if="outputBlocks.length"
        class="space-y-1.5"
      >
        <p class="text-[11px] font-medium text-gray-500 dark:text-dark-400">
          分析结果汇报
        </p>
        <div class="max-h-96 overflow-auto rounded-lg border border-gray-200 bg-white p-3.5 dark:border-dark-700 dark:bg-dark-900">
          <MessageContent :blocks="outputBlocks" />
        </div>
      </div>
      <p
        v-else-if="!stream || !namespace.length"
        class="text-xs text-gray-500 dark:text-dark-400"
      >
        {{ tool.status === 'running' ? '子任务正在运行中...' : '尚无公开汇报结果' }}
      </p>

      <button
        v-if="tool.artifact != null"
        type="button"
        class="pw-table-tool-button text-xs"
        @click="emit('inspect', tool)"
      >
        在详情面板查看构件
      </button>
    </div>
  </div>
</template>

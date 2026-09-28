<script setup lang="ts">
import { computed, ref } from "vue";
import type { AnyStream } from "@langchain/vue";
import {
  asObject,
  contentItems,
  extractChartWeakImageRefs,
  extractRuntimeImages,
  type ToolItem,
} from "../transcript";
import MessageContent from "./MessageContent.vue";
import SubtaskDetail from "./SubtaskDetail.vue";
import ThreadImage from "./ThreadImage.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";

const props = defineProps<{
  tool: ToolItem;
  stream?: AnyStream;
  projectId?: string;
  threadId?: string;
}>();

const emit = defineEmits<{ inspect: [tool: ToolItem] }>();

const expanded = ref(false);

const isPromptExpanded = ref(false);

const input = computed(() => asObject(props.tool.input));
const subagentType = computed(
  () =>
    (typeof input.value.subagent_type === "string" &&
      input.value.subagent_type) ||
    (typeof input.value.name === "string" && input.value.name) ||
    "subagent",
);

const description = computed(() => {
  if (typeof input.value.description === "string")
    return input.value.description.trim();
  if (typeof input.value.prompt === "string") return input.value.prompt.trim();
  if (typeof input.value.task === "string") return input.value.task.trim();
  return "";
});

const isLongDescription = computed(() => description.value.length > 110);

type IconName = InstanceType<typeof BaseIcon>["$props"]["name"];

interface SubagentConfig {
  label: string;
  badge: string;
  icon: IconName;
  badgeClass: string;
}

const SUBAGENT_TYPE_CONFIGS: Record<string, SubagentConfig> = {
  research: {
    label: "审查调研",
    badge: "子智能体",
    icon: "search",
    badgeClass:
      "bg-cyan-50 text-cyan-700 ring-1 ring-cyan-500/20 dark:bg-cyan-950/60 dark:text-cyan-300 dark:ring-cyan-500/30",
  },
  "general-purpose": {
    label: "全能执行",
    badge: "子智能体",
    icon: "assistant",
    badgeClass:
      "bg-indigo-50 text-indigo-700 ring-1 ring-indigo-500/20 dark:bg-indigo-950/60 dark:text-indigo-300 dark:ring-indigo-500/30",
  },
};

const subagentConfig = computed<SubagentConfig>(() => {
  const key = subagentType.value.toLowerCase();
  if (SUBAGENT_TYPE_CONFIGS[key]) {
    return SUBAGENT_TYPE_CONFIGS[key];
  }
  return {
    label: "子智能体",
    badge: "子智能体",
    icon: "assistant",
    badgeClass: "bg-gray-100 text-gray-700 dark:bg-dark-700 dark:text-dark-200",
  };
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

const runtimeImages = computed(() => {
  const explicit = extractRuntimeImages(props.tool.artifact);
  if (explicit.length > 0) {
    return explicit;
  }
  return extractChartWeakImageRefs(
    cleanedOutput.value ||
      (typeof props.tool.output === "string" ? props.tool.output : ""),
  );
});
</script>

<template>
  <div
    class="group rounded-2xl border transition-all duration-200 shadow-xs"
    :class="
      expanded
        ? 'border-primary-200/90 bg-white shadow-sm dark:border-primary-800/50 dark:bg-dark-900/90'
        : 'border-gray-200/80 bg-white/80 hover:border-gray-300/90 hover:bg-white hover:shadow-xs dark:border-dark-700/80 dark:bg-dark-900/60 dark:hover:border-dark-600 dark:hover:bg-dark-800/80'
    "
  >
    <button
      type="button"
      class="flex w-full cursor-pointer items-center justify-between gap-3 p-3.5 text-left focus-visible:ring-2"
      :aria-expanded="expanded"
      @click="expanded = !expanded"
    >
      <div class="flex min-w-0 items-center gap-2.5">
        <span
          class="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl transition-colors"
          :class="
            tool.status === 'running'
              ? 'bg-primary-50 text-primary-600 ring-1 ring-primary-500/20 dark:bg-primary-950/60 dark:text-primary-400 dark:ring-primary-500/30'
              : tool.status === 'error'
                ? 'bg-red-50 text-red-600 ring-1 ring-red-500/20 dark:bg-red-950/60 dark:text-red-400 dark:ring-red-500/30'
                : subagentType === 'research'
                  ? 'bg-cyan-50 text-cyan-600 ring-1 ring-cyan-500/20 dark:bg-cyan-950/60 dark:text-cyan-400 dark:ring-cyan-500/30'
                  : 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-500/20 dark:bg-emerald-950/60 dark:text-emerald-400 dark:ring-emerald-500/30'
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
          <BaseIcon v-else :name="subagentConfig.icon" class="h-4 w-4" />
        </span>
        <div class="min-w-0">
          <div class="flex items-center gap-2">
            <span class="truncate font-semibold text-gray-900 dark:text-white">
              {{ subagentType }}
            </span>
            <span
              class="rounded-md px-1.5 py-0.5 text-[10px] font-medium leading-none"
              :class="subagentConfig.badgeClass"
            >
              子智能体
            </span>
            <span
              v-if="subagentConfig.label !== '子智能体'"
              class="hidden text-[11px] font-medium text-gray-400 dark:text-dark-400 sm:inline"
            >
              · {{ subagentConfig.label }}
            </span>
          </div>
        </div>
      </div>

      <div class="flex shrink-0 items-center gap-2.5">
        <!-- 现代化微胶囊状态 Pill -->
        <span
          class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium"
          :class="
            tool.status === 'running'
              ? 'bg-primary-50 text-primary-700 ring-1 ring-primary-500/20 dark:bg-primary-950/60 dark:text-primary-300 dark:ring-primary-500/30'
              : tool.status === 'error'
                ? 'bg-red-50 text-red-700 ring-1 ring-red-500/20 dark:bg-red-950/60 dark:text-red-300 dark:ring-red-500/30'
                : 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-500/20 dark:bg-emerald-950/60 dark:text-emerald-300 dark:ring-emerald-500/30'
          "
        >
          <span
            class="h-1.5 w-1.5 rounded-full"
            :class="
              tool.status === 'running'
                ? 'bg-primary-500 animate-pulse'
                : tool.status === 'error'
                  ? 'bg-red-500'
                  : 'bg-emerald-500'
            "
          />
          <span>{{ statusLabels[tool.status] || tool.status }}</span>
        </span>

        <!-- 顺滑旋转 SVG Chevron 箭头 -->
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
          <path d="M4 6l4 4 4-4" />
        </svg>
      </div>
    </button>

    <!-- 委派任务指令展示区（修复 Webkit 截断腰斩 bug，提供单独展开与代码引用质感） -->
    <div
      v-if="description"
      class="mx-3.5 mb-3 rounded-xl border border-gray-100/90 bg-gray-50/70 p-3 transition-colors dark:border-dark-800/80 dark:bg-dark-900/50"
    >
      <div
        class="mb-1.5 flex items-center justify-between text-[11px] font-medium text-gray-500 dark:text-dark-400"
      >
        <span class="inline-flex items-center gap-1.5">
          <span class="h-1.5 w-1.5 rounded-full bg-primary-500/70" />
          <span>委派目标与指令</span>
        </span>
        <button
          v-if="isLongDescription"
          type="button"
          class="cursor-pointer text-[11px] font-medium text-primary-600 transition-colors hover:text-primary-700 dark:text-primary-400 dark:hover:text-primary-300"
          @click.stop="isPromptExpanded = !isPromptExpanded"
        >
          {{ isPromptExpanded ? "收起指令" : "展开完整指令" }}
        </button>
      </div>

      <div
        class="text-xs leading-5 text-gray-600 dark:text-dark-300 break-words whitespace-pre-wrap font-sans"
        :class="!isPromptExpanded && !expanded ? 'line-clamp-3' : ''"
      >
        {{ description }}
      </div>
    </div>

    <div
      v-if="expanded"
      class="space-y-3.5 border-t border-gray-200/80 p-3.5 dark:border-dark-700"
    >
      <div
        v-if="stream && namespace.length"
        class="rounded-lg border border-gray-200 bg-white p-3 dark:border-dark-700 dark:bg-dark-900"
      >
        <p
          class="mb-2 text-[11px] font-medium text-gray-500 dark:text-dark-400"
        >
          子任务执行过程
        </p>
        <SubtaskDetail
          :stream="stream"
          :namespace="namespace"
          :running="tool.status === 'running'"
          @inspect="emit('inspect', $event)"
        />
      </div>

      <div v-if="outputBlocks.length" class="space-y-1.5">
        <p class="text-[11px] font-medium text-gray-500 dark:text-dark-400">
          分析结果汇报
        </p>
        <div
          class="max-h-96 overflow-auto rounded-lg border border-gray-200 bg-white p-3.5 dark:border-dark-700 dark:bg-dark-900"
        >
          <MessageContent
            :blocks="outputBlocks"
            :project-id="projectId"
            :thread-id="threadId"
          />
        </div>
      </div>
      <div v-if="runtimeImages.length" class="space-y-1.5">
        <p class="text-[11px] font-medium text-gray-500 dark:text-dark-400">
          生成图表 / 产物图片
        </p>
        <div class="grid grid-cols-1 gap-2">
          <ThreadImage
            v-for="img in runtimeImages"
            :key="img.path"
            :image-ref="img"
            :project-id="projectId || ''"
            :thread-id="threadId || ''"
          />
        </div>
      </div>
      <p
        v-else-if="!stream || !namespace.length"
        class="text-xs text-gray-500 dark:text-dark-400"
      >
        {{
          tool.status === "running" ? "子任务正在运行中..." : "尚无公开汇报结果"
        }}
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

<script setup lang="ts">
import { computed, ref } from "vue";
import type { AnyStream } from "@langchain/vue";
import { asObject, contentItems, extractRuntimeImages, extractWorkspaceImageRefs, readable, type ToolItem } from "../transcript";
import MessageContent from "./MessageContent.vue";
import SubagentCard from "./SubagentCard.vue";
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
const input = computed(() => asObject(props.tool.input));
const result = computed(() => {
  if (typeof props.tool.output !== "string") return asObject(props.tool.output);
  try { return asObject(JSON.parse(props.tool.output)); } catch { return {}; }
});
const labels = {
  running: "执行中",
  finished: "已返回",
  error: "失败",
  incomplete: "未完成 / 已中止",
};
const fileTools = [
  "read_file",
  "write_file",
  "edit_file",
  "ls",
  "glob",
  "grep",
];
const path = computed(() =>
  fileTools.includes(props.tool.name)
    ? (input.value.file_path ?? input.value.path)
    : undefined,
);
const diff = computed(
  () =>
    props.tool.name === "edit_file" &&
    typeof input.value.old_string === "string" &&
    typeof input.value.new_string === "string",
);
const output = computed(() =>
  contentItems(props.tool.output, `${props.tool.key}:output`),
);
const todoItems = computed<Array<{ content: string; status: string }>>(() => {
  if (props.tool.name !== "write_todos") return [];
  let raw = props.tool.input;
  if (typeof raw === "string") {
    try {
      raw = JSON.parse(raw);
    } catch {
      return [];
    }
  }
  if (Array.isArray(raw)) {
    return raw.filter(
      (item): item is { content: string; status: string } =>
        Boolean(item && typeof item === "object" && "content" in item),
    );
  }
  const obj = asObject(raw);
  if (Array.isArray(obj.todos)) {
    return (obj.todos as unknown[]).filter(
      (item): item is { content: string; status: string } =>
        Boolean(item && typeof item === "object" && "content" in item),
    );
  }
  return [];
});
const activeTodo = computed(() =>
  todoItems.value.find((t) => t.status === "in_progress"),
);
const runtimeImages = computed(() => {
  const explicit = extractRuntimeImages(props.tool.artifact);
  if (explicit.length > 0) return explicit;
  return extractWorkspaceImageRefs(
    typeof props.tool.output === "string" ? props.tool.output : "",
  );
});
const displayTitle = computed(() => {
  if (props.tool.name === "write_todos") {
    return "更新任务清单";
  }
  if (props.tool.name === "generate_image") {
    return "文生图";
  }
  if (props.tool.name === "edit_image") {
    return "图像编辑/图生图";
  }
  if (props.tool.name === "analyze_image") {
    return "图像识别分析";
  }
  return props.tool.name;
});
const displaySubtitle = computed(() => {
  if (props.tool.name === "write_todos") {
    return todoItems.value.length ? ` · 共 ${todoItems.value.length} 项` : "";
  }
  if (runtimeImages.value.length) {
    return ` · 产物: ${runtimeImages.value[0]?.path}`;
  }
  return path.value ? ` · ${path.value}` : "";
});
</script>

<template>
  <SubagentCard
    v-if="tool.name === 'task'"
    :tool="tool"
    :stream="stream"
    :project-id="projectId"
    :thread-id="threadId"
    @inspect="emit('inspect', $event)"
  />
  <div
    v-else
    class="rounded-xl border border-gray-200/90 bg-white/95 text-sm shadow-2xs dark:border-dark-700/80 dark:bg-dark-900/90 overflow-hidden"
  >
    <button
      type="button"
      class="flex w-full items-center gap-2.5 p-3 text-left transition-colors hover:bg-gray-50/80 focus-visible:ring-2 dark:hover:bg-dark-800/60"
      :aria-expanded="expanded"
      @click="expanded = !expanded"
    >
      <BaseIcon
        name="chevron-down"
        size="xs"
        class="text-gray-400 transition-transform duration-200 shrink-0"
        :class="expanded ? 'rotate-0' : '-rotate-90'"
      />
      <span class="min-w-0 flex-1 truncate font-medium text-gray-800 dark:text-gray-200">{{ displayTitle }}
        <span
          v-if="displaySubtitle"
          class="font-normal text-gray-400 dark:text-dark-400"
        >{{ displaySubtitle }}</span></span>
      <span
        class="shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium"
        :class="{
          'bg-red-50 text-red-600 dark:bg-red-950/40 dark:text-red-400': tool.status === 'error',
          'bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-400': tool.status === 'finished',
          'bg-blue-50 text-blue-600 dark:bg-blue-950/40 dark:text-blue-400 animate-pulse': tool.status === 'running',
          'bg-gray-100 text-gray-600 dark:bg-dark-800 dark:text-dark-300': tool.status === 'incomplete'
        }"
      >{{ labels[tool.status] }}</span>
    </button>
    <p
      v-if="tool.status === 'error'"
      class="px-3 pb-2 text-xs text-red-600 dark:text-red-400"
    >
      {{ tool.error || "工具执行失败，展开查看结果" }}
    </p>
    <div
      v-if="expanded"
      class="space-y-3 border-t border-gray-100 p-3.5 dark:border-dark-800"
    >
      <template v-if="diff">
        <div class="space-y-2">
          <div class="flex items-center justify-between text-xs text-gray-500 dark:text-dark-400">
            <span>代码修改对比 (Diff)</span>
            <span class="font-mono text-[11px]">{{ path }}</span>
          </div>
          <div class="grid gap-2 overflow-hidden rounded-xl border border-gray-200 text-xs font-mono dark:border-dark-700 md:grid-cols-2">
            <div class="bg-red-50/50 p-2.5 dark:bg-red-950/20">
              <div class="mb-1.5 flex items-center gap-1.5 text-[10px] font-semibold text-red-600 dark:text-red-400">
                <span class="rounded bg-red-100 px-1 dark:bg-red-900/60">- 原内容</span>
              </div>
              <pre class="max-h-80 overflow-auto whitespace-pre-wrap text-red-900 dark:text-red-200">{{ input.old_string }}</pre>
            </div>
            <div class="bg-emerald-50/50 p-2.5 dark:bg-emerald-950/20">
              <div class="mb-1.5 flex items-center gap-1.5 text-[10px] font-semibold text-emerald-600 dark:text-emerald-400">
                <span class="rounded bg-emerald-100 px-1 dark:bg-emerald-900/60">+ 新内容</span>
              </div>
              <pre class="max-h-80 overflow-auto whitespace-pre-wrap text-emerald-900 dark:text-emerald-200">{{ input.new_string }}</pre>
            </div>
          </div>
        </div>
      </template>
      <template
        v-else-if="tool.name === 'execute' && typeof input.command === 'string'"
      >
        <div class="overflow-hidden rounded-xl border border-gray-800 bg-gray-950 text-xs text-gray-100 shadow-sm font-mono">
          <div class="flex items-center justify-between border-b border-gray-800/80 bg-gray-900/80 px-3 py-1.5 text-[11px] text-gray-400">
            <div class="flex items-center gap-1.5">
              <span class="h-2 w-2 rounded-full bg-red-500/80 inline-block" />
              <span class="h-2 w-2 rounded-full bg-amber-500/80 inline-block" />
              <span class="h-2 w-2 rounded-full bg-emerald-500/80 inline-block" />
              <span class="ml-2 text-gray-300 font-sans">Terminal</span>
            </div>
            <span
              v-if="typeof result.exit_code === 'number'"
              class="text-[10px]"
              :class="result.exit_code === 0 ? 'text-emerald-400' : 'text-red-400'"
            >
              退出码: {{ result.exit_code }}
            </span>
          </div>
          <pre class="max-h-48 overflow-auto p-3 text-gray-100 leading-relaxed">$ {{ input.command }}</pre>
        </div>
        <p class="text-[11px] text-gray-400 dark:text-dark-400">
          非交互命令 · 执行结束后返回<span
            v-if="typeof result.exit_code === 'number'"
          >
            · 退出码 {{ result.exit_code }}</span><span v-if="result.truncated === true"> · 输出已截断</span>
        </p>
      </template>
      <template v-else-if="tool.name === 'write_todos' && todoItems.length">
        <div class="space-y-2.5">
          <div class="flex items-center justify-between text-xs text-gray-500 dark:text-dark-400">
            <span>待办计划 · 共 {{ todoItems.length }} 项</span>
            <span
              v-if="activeTodo"
              class="max-w-[60%] truncate font-medium text-blue-600 dark:text-blue-400"
            >
              进行中: {{ activeTodo.content }}
            </span>
          </div>
          <div class="space-y-1.5 rounded-lg border border-gray-100 bg-gray-50/70 p-3 dark:border-dark-700 dark:bg-dark-800/60">
            <div
              v-for="(item, idx) in todoItems"
              :key="idx"
              class="flex items-start gap-2.5 text-xs"
            >
              <span
                class="mt-1 inline-block h-2 w-2 shrink-0 rounded-full"
                :class="{
                  'bg-blue-500 ring-2 ring-blue-100 dark:ring-blue-900/40': item.status === 'in_progress',
                  'bg-emerald-500': item.status === 'completed',
                  'border border-gray-400 bg-transparent dark:border-gray-500': item.status === 'pending'
                }"
              />
              <span
                class="min-w-0 flex-1 break-words"
                :class="{
                  'font-medium text-gray-900 dark:text-white': item.status === 'in_progress',
                  'text-gray-400 line-through dark:text-gray-500': item.status === 'completed',
                  'text-gray-700 dark:text-gray-300': item.status === 'pending'
                }"
              >
                {{ item.content }}
              </span>
              <span
                class="shrink-0 text-[11px]"
                :class="{
                  'font-medium text-blue-600 dark:text-blue-400': item.status === 'in_progress',
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
      <template v-else>
        <p class="text-xs text-gray-500">
          参数
        </p>
        <pre class="max-h-80 overflow-auto whitespace-pre-wrap text-xs">{{
          readable(tool.input)
        }}</pre>
      </template>
      <div
        v-if="tool.output !== undefined && tool.name !== 'write_todos'"
        class="max-h-96 overflow-auto"
      >
        <p class="mb-2 text-xs text-gray-500">
          结果
        </p>
        <MessageContent :blocks="output" :project-id="projectId" :thread-id="threadId" />
        <div v-if="runtimeImages.length" class="space-y-2 mt-2">
          <ThreadImage
            v-for="img in runtimeImages"
            :key="img.path"
            :project-id="projectId || ''"
            :thread-id="threadId || ''"
            :image-ref="img"
          />
        </div>
      </div>
      <p
        v-else-if="tool.name !== 'write_todos'"
        class="text-xs text-gray-500"
      >
        尚无公开结果
      </p>
      <button
        v-if="tool.artifact != null || path || tool.name === 'write_todos'"
        type="button"
        class="pw-table-tool-button h-8 rounded-lg px-3 text-xs"
        @click="emit('inspect', tool)"
      >
        {{ tool.name === 'write_todos' ? '在详情面板查看任务看板 →' : '在详情面板查看' }}
      </button>
    </div>
  </div>
</template>

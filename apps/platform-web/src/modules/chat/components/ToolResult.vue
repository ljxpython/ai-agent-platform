<script setup lang="ts">
import { computed, ref } from "vue";
import type { AnyStream } from "@langchain/vue";
import { asObject, contentItems, readable, type ToolItem } from "../transcript";
import MessageContent from "./MessageContent.vue";
import SubagentCard from "./SubagentCard.vue";

const props = defineProps<{
  tool: ToolItem;
  stream?: AnyStream;
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
const displayTitle = computed(() => {
  if (props.tool.name === "write_todos") {
    return "更新任务清单";
  }
  return props.tool.name;
});
const displaySubtitle = computed(() => {
  if (props.tool.name === "write_todos") {
    return todoItems.value.length ? ` · 共 ${todoItems.value.length} 项` : "";
  }
  return path.value ? ` · ${path.value}` : "";
});
</script>

<template>
  <SubagentCard
    v-if="tool.name === 'task'"
    :tool="tool"
    :stream="stream"
    @inspect="emit('inspect', $event)"
  />
  <div
    v-else
    class="rounded-lg border border-gray-200 text-sm dark:border-dark-700"
  >
    <button
      type="button"
      class="flex w-full items-center gap-3 p-3 text-left focus-visible:ring-2"
      :aria-expanded="expanded"
      @click="expanded = !expanded"
    >
      <span aria-hidden="true">{{ expanded ? "▾" : "▸" }}</span>
      <span class="min-w-0 flex-1 truncate font-medium">{{ displayTitle }}
        <span
          v-if="displaySubtitle"
          class="font-normal text-gray-500"
        >{{ displaySubtitle }}</span></span>
      <span
        class="shrink-0 text-xs"
        :class="tool.status === 'error' ? 'text-red-600' : 'text-gray-500'"
      >{{ labels[tool.status] }}</span>
    </button>
    <p
      v-if="tool.status === 'error'"
      class="px-3 pb-2 text-red-600"
    >
      {{ tool.error || "工具执行失败，展开查看结果" }}
    </p>
    <div
      v-if="expanded"
      class="space-y-3 border-t border-gray-200 p-3 dark:border-dark-700"
    >
      <template v-if="diff">
        <p class="text-xs text-gray-500">
          修改片段 ·
          {{
            tool.status === "finished"
              ? "工具已返回，请结合结果确认"
              : "拟修改，尚未确认执行"
          }}
        </p>
        <div class="grid gap-2 md:grid-cols-2">
          <pre
            class="max-h-80 overflow-auto rounded bg-red-50 p-2 text-xs text-gray-900"
          >{{ input.old_string }}</pre>
          <pre
            class="max-h-80 overflow-auto rounded bg-green-50 p-2 text-xs text-gray-900"
          >{{ input.new_string }}</pre>
        </div>
      </template>
      <template
        v-else-if="tool.name === 'execute' && typeof input.command === 'string'"
      >
        <pre
          class="max-h-40 overflow-auto rounded bg-gray-950 p-3 text-xs text-gray-100"
        >{{ input.command }}</pre>
        <p class="text-xs text-gray-500">
          非交互命令 · 执行结束后返回<span
            v-if="typeof result.exit_code === 'number'"
          >
            · 退出码 {{ result.exit_code }}</span><span v-if="result.truncated === true"> · 输出已截断</span>
        </p>
      </template>
      <template v-else-if="tool.name === 'write_todos' && todoItems.length">
        <div class="space-y-2.5">
          <div class="flex items-center justify-between text-xs text-gray-500">
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
        <MessageContent :blocks="output" />
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
        class="pw-table-tool-button"
        @click="emit('inspect', tool)"
      >
        {{ tool.name === 'write_todos' ? '在详情面板查看任务看板 →' : '在详情面板查看' }}
      </button>
    </div>
  </div>
</template>

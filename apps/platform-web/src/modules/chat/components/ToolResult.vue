<script setup lang="ts">
import { computed, ref } from "vue";
import { asObject, contentItems, readable, type ToolItem } from "../transcript";
import MessageContent from "./MessageContent.vue";

const props = defineProps<{ tool: ToolItem }>();
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
</script>

<template>
  <div class="rounded-lg border border-gray-200 text-sm dark:border-dark-700">
    <button
      type="button"
      class="flex w-full items-center gap-3 p-3 text-left focus-visible:ring-2"
      :aria-expanded="expanded"
      @click="expanded = !expanded"
    >
      <span aria-hidden="true">{{ expanded ? "▾" : "▸" }}</span>
      <span class="min-w-0 flex-1 truncate font-medium">{{ tool.name }}
        <span
          v-if="path"
          class="font-normal text-gray-500"
        >{{
          path
        }}</span></span>
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
      <template v-else>
        <p class="text-xs text-gray-500">
          参数
        </p>
        <pre class="max-h-80 overflow-auto whitespace-pre-wrap text-xs">{{
          readable(tool.input)
        }}</pre>
      </template>
      <div
        v-if="tool.output !== undefined"
        class="max-h-96 overflow-auto"
      >
        <p class="mb-2 text-xs text-gray-500">
          结果
        </p>
        <MessageContent :blocks="output" />
      </div>
      <p
        v-else
        class="text-xs text-gray-500"
      >
        尚无公开结果
      </p>
      <button
        v-if="tool.artifact != null || path"
        type="button"
        class="pw-table-tool-button"
        @click="emit('inspect', tool)"
      >
        在详情面板查看
      </button>
    </div>
  </div>
</template>

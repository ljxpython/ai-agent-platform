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
const isAwaitingReview = computed(() => {
  if (props.tool.status !== "running" && props.tool.status !== "incomplete") return false;
  const interrupts = props.stream?.interrupts?.value;
  if (!Array.isArray(interrupts) || interrupts.length === 0) return false;
  return interrupts.some((int: unknown) => {
    const val = int && typeof int === "object" && "value" in int ? (int as Record<string, unknown>).value : int;
    if (!val || typeof val !== "object") return false;
    const reqs = (val as Record<string, unknown>).action_requests;
    if (Array.isArray(reqs)) {
      return (
        reqs.length === 0 ||
        reqs.some((r) => r && typeof r === "object" && (r as Record<string, unknown>).name === props.tool.name)
      );
    }
    return true;
  });
});

function formatStreamingChars(chars?: number): string {
  if (!chars || chars <= 0) return "";
  return chars >= 1000
    ? ` · 已生成 ${(chars / 1000).toFixed(1)}k 字符`
    : ` · 已生成 ${chars} 字符`;
}

const isStreamingInput = computed(
  () =>
    props.tool.status === "running" &&
    !isAwaitingReview.value &&
    props.tool.name !== "request_information" &&
    Boolean(props.tool.streamingInput),
);

const labels = computed(() => {
  if (props.tool.name === "request_information") {
    return {
      running: "等待补充信息",
      finished: "已补充信息",
      error: "失败",
      incomplete: "未完成 / 已中止",
    };
  }
  const runningLabel = isAwaitingReview.value
    ? "等待审批"
    : isStreamingInput.value
      ? `正在生成参数${formatStreamingChars(props.tool.streamingChars)}`
      : "执行中";
  return {
    running: runningLabel,
    finished: "已返回",
    error: "失败",
    incomplete: isAwaitingReview.value ? "等待审批" : "未完成 / 已中止",
  };
});
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
  const fromOutput = extractRuntimeImages(props.tool.output);
  if (fromOutput.length > 0) return fromOutput;
  return extractWorkspaceImageRefs(
    typeof props.tool.output === "string" ? props.tool.output : "",
  );
});
const unrenderedRuntimeImages = computed(() => {
  const renderedPaths = new Set(
    output.value
      .filter((b) => b.kind === "image" && b.imageRef?.path)
      .map((b) => b.imageRef!.path),
  );
  return runtimeImages.value.filter((img) => !renderedPaths.has(img.path));
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
  if (props.tool.name === "parse_document") {
    return "解析文档";
  }
  if (props.tool.name === "chart_visualization" || props.tool.name === "render_chart") {
    return "数据图表可视化";
  }
  if (props.tool.name === "ppt_generation" || props.tool.name === "generate_ppt") {
    return "制作演示文稿 (PPTX)";
  }
  return props.tool.name;
});
const displaySubtitle = computed(() => {
  if (props.tool.name === "write_todos") {
    return todoItems.value.length ? ` · 共 ${todoItems.value.length} 项` : "";
  }
  if (props.tool.name === "parse_document") {
    const filePath = typeof input.value.file_path === "string" ? input.value.file_path : "";
    const fileName = filePath.split("/").pop() || filePath;
    const pages = Array.isArray(result.value.matched_pages) ? result.value.matched_pages : [];
    if (pages.length > 0) {
      return ` · ${fileName} (第 ${pages.join("、")} 页)`;
    }
    return fileName ? ` · ${fileName}` : "";
  }
  if (runtimeImages.value.length) {
    return ` · 产物: ${runtimeImages.value[0]?.path}`;
  }
  return path.value ? ` · ${path.value}` : "";
});

function formatDocumentWarning(w: string, query?: unknown): string {
  if (w === "no_query_match_in_selected_range") {
    return query && typeof query === "string"
      ? `在指定页码范围内未匹配到关键词 "${query}"`
      : "在指定页码范围内未匹配到关键词内容";
  }
  if (w === "csv_row_limit_2000") {
    return "CSV 达到 2000 行上限，超出部分已受控截断";
  }
  const match = /^page_(\d+)_no_text_layer_ocr_required$/.exec(w);
  if (match) {
    return `第 ${match[1]} 页无文本层（纯扫描页），需要 OCR 识别`;
  }
  return w;
}

export type EvidenceSourceItem = {
  source_url?: string;
  title?: string;
  kind?: string;
  content_hash?: string;
  path?: string;
  observed_at?: string;
  searched_at?: string;
  preview?: string;
  truncated?: boolean;
  read_scope?: string;
};

const evidenceSources = computed<EvidenceSourceItem[]>(() => {
  const list: EvidenceSourceItem[] = [];
  const artifactObj = asObject(props.tool.artifact);
  if (Array.isArray(artifactObj.sources)) {
    for (const s of artifactObj.sources) {
      if (s && typeof s === "object") list.push(s as EvidenceSourceItem);
    }
  }
  const res = result.value;
  if (Array.isArray(res.sources)) {
    for (const s of res.sources) {
      if (
        s &&
        typeof s === "object" &&
        !list.some(
          (existing) =>
            existing.content_hash &&
            existing.content_hash === (s as Record<string, unknown>).content_hash,
        )
      ) {
        list.push(s as EvidenceSourceItem);
      }
    }
  }
  if (res.evidence && typeof res.evidence === "object") {
    const s = res.evidence as EvidenceSourceItem;
    if (
      !list.some(
        (existing) =>
          existing.content_hash && existing.content_hash === s.content_hash,
      )
    ) {
      list.push(s);
    }
  }
  return list;
});

const sourcesExpanded = ref(false);

function getSourceKindBadge(source: EvidenceSourceItem): {
  label: string;
  class: string;
} {
  const kind = source.kind || source.read_scope || "";
  if (kind.includes("page_text") || kind === "full_text") {
    return {
      label: "正文证据",
      class:
        "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800",
    };
  }
  if (
    kind.includes("arxiv") ||
    kind.includes("academic") ||
    kind === "abstract_only"
  ) {
    return {
      label: "论文摘要",
      class:
        "bg-purple-50 text-purple-700 dark:bg-purple-950/40 dark:text-purple-300 border-purple-200 dark:border-purple-800",
    };
  }
  if (kind.includes("snippet") || kind.includes("search")) {
    return {
      label: "搜索摘要",
      class:
        "bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300 border-blue-200 dark:border-blue-800",
    };
  }
  return {
    label: "证据来源",
    class:
      "bg-gray-50 text-gray-700 dark:bg-gray-800 dark:text-gray-300 border-gray-200 dark:border-gray-700",
  };
}
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
          'bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300 border border-amber-200 dark:border-amber-800 animate-pulse': isAwaitingReview,
          'bg-indigo-50 text-indigo-600 dark:bg-indigo-950/40 dark:text-indigo-400 animate-pulse': isStreamingInput,
          'bg-blue-50 text-blue-600 dark:bg-blue-950/40 dark:text-blue-400 animate-pulse': tool.status === 'running' && !isAwaitingReview && !isStreamingInput,
          'bg-gray-100 text-gray-600 dark:bg-dark-800 dark:text-dark-300': tool.status === 'incomplete' && !isAwaitingReview
        }"
      >{{ labels[tool.status] }}</span>
    </button>
    <p
      v-if="tool.status === 'error' && tool.error && !tool.error.includes('Interrupt(')"
      class="px-3 pb-2 text-xs text-red-600 dark:text-red-400"
    >
      {{ tool.error }}
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
        v-else-if="tool.name === 'write_file' && typeof input.content === 'string'"
      >
        <div class="space-y-2">
          <div class="flex items-center justify-between text-xs text-gray-500 dark:text-dark-400">
            <span>{{ isStreamingInput ? "正在流式生成写入内容" : "写入文件内容" }} ({{ input.content.length.toLocaleString() }} 字符)</span>
            <span class="font-mono text-[11px]">{{ path }}</span>
          </div>
          <pre class="max-h-80 overflow-auto rounded-xl border border-gray-200 bg-gray-50/80 p-3 text-xs font-mono whitespace-pre-wrap text-gray-800 dark:border-dark-700 dark:bg-dark-800/70 dark:text-gray-200">{{ input.content }}</pre>
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
      <template v-else-if="tool.name === 'parse_document'">
        <div class="space-y-3">
          <div class="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 bg-slate-50/80 px-3 py-2 text-xs dark:border-dark-700 dark:bg-dark-800/60">
            <div class="flex items-center gap-2">
              <BaseIcon
                name="file"
                size="xs"
                class="text-primary-600 dark:text-primary-400"
              />
              <span class="font-medium text-slate-900 dark:text-white">
                {{ input.file_path ? String(input.file_path).split('/').pop() : '文档' }}
              </span>
              <span
                v-if="result.format"
                class="rounded bg-slate-200/80 px-1.5 py-0.5 text-[10px] uppercase text-slate-700 dark:bg-dark-700 dark:text-dark-300"
              >
                {{ result.format }}
              </span>
            </div>
            <div class="flex items-center gap-3 text-slate-500 dark:text-dark-300">
              <span v-if="typeof result.pages === 'number'">共 {{ result.pages }} 页</span>
              <span
                v-if="Array.isArray(result.matched_pages) && result.matched_pages.length"
                class="text-primary-600 dark:text-primary-400 font-medium"
              >
                已命中第 {{ result.matched_pages.join('、') }} 页
              </span>
            </div>
          </div>

          <div
            v-if="result.truncated"
            class="rounded-lg border border-amber-200 bg-amber-50/80 px-3 py-2 text-xs text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-300 flex items-center gap-1.5"
          >
            <BaseIcon
              name="alert"
              size="xs"
            />
            <span>内容已截断，可继续指定 page_start 和 page_end 查询后续页码</span>
          </div>

          <div
            v-if="Array.isArray(result.warnings) && result.warnings.length"
            class="space-y-1.5"
          >
            <div
              v-for="(w, idx) in result.warnings"
              :key="idx"
              class="flex items-center gap-1.5 rounded-md border border-amber-200/80 bg-amber-50/70 px-2.5 py-1.5 text-xs text-amber-800 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-300"
            >
              <BaseIcon
                name="alert"
                size="xs"
                class="shrink-0 text-amber-600 dark:text-amber-400"
              />
              <span>{{ formatDocumentWarning(w, input.query) }}</span>
            </div>
          </div>

          <div
            v-if="Array.isArray(result.chunks) && result.chunks.length"
            class="space-y-2"
          >
            <div
              v-for="(chunk, idx) in result.chunks"
              :key="idx"
              class="rounded-lg border border-gray-100 bg-gray-50/50 p-2.5 text-xs dark:border-dark-700 dark:bg-dark-800/40"
            >
              <div class="mb-1 flex items-center justify-between font-mono text-[10px] text-gray-500 dark:text-dark-400">
                <span v-if="typeof chunk.page === 'number'">第 {{ chunk.page }} 页</span>
              </div>
              <div class="whitespace-pre-wrap leading-relaxed text-gray-800 dark:text-dark-200">
                {{ chunk.text }}
              </div>
            </div>
          </div>
          <div
            v-else-if="result.text"
            class="rounded-lg border border-gray-100 bg-gray-50/50 p-3 text-xs whitespace-pre-wrap leading-relaxed dark:border-dark-700 dark:bg-dark-800/40 text-gray-800 dark:text-dark-200 max-h-80 overflow-auto"
          >
            {{ result.text }}
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
        v-if="tool.output !== undefined && !['write_todos', 'parse_document'].includes(tool.name)"
        class="max-h-96 overflow-auto"
      >
        <p class="mb-2 text-xs text-gray-500">
          结果
        </p>
        <MessageContent
          :blocks="output"
          :project-id="projectId"
          :thread-id="threadId"
        />
        <!-- 生图/生成任务 unknown 状态告警防御 -->
        <div
          v-if="result.status === 'unknown' && !runtimeImages.length"
          class="mb-3 rounded-lg border border-amber-300 bg-amber-50/80 p-3 text-xs text-amber-900 dark:border-amber-700/60 dark:bg-amber-950/30 dark:text-amber-200"
        >
          <div class="flex items-center gap-1.5 font-medium text-xs">
            <BaseIcon
              name="alert"
              size="xs"
              class="text-amber-600 dark:text-amber-400 shrink-0"
            />
            <span>生成任务终态未知 (unknown)</span>
          </div>
          <p class="mt-1 text-[11px] leading-relaxed text-amber-800/90 dark:text-amber-300/90">
            由于远程供应商响应超时，当前生成任务终态尚未确认。<span v-if="result.task_id">任务凭据 ID: <code class="font-mono">{{ result.task_id }}</code>。</span>
            请先刷新会话历史或核对账单，<strong>切勿盲目重复点击生成</strong>，避免重复计费！
          </p>
        </div>

        <div
          v-if="unrenderedRuntimeImages.length"
          class="space-y-2 mt-2"
        >
          <ThreadImage
            v-for="(img, imgIdx) in unrenderedRuntimeImages"
            :key="img.path"
            :project-id="projectId || ''"
            :thread-id="threadId || ''"
            :image-ref="img"
            :kind="tool.name === 'ppt_generation' ? 'slide' : (tool.name === 'edit_image' && imgIdx === 0 && unrenderedRuntimeImages.length > 1 ? 'reference' : 'generated')"
            :status="typeof result.status === 'string' ? (result.status as any) : undefined"
            :task-id="typeof result.task_id === 'string' ? result.task_id : undefined"
            :slide-index="tool.name === 'ppt_generation' ? imgIdx + 1 : undefined"
            :slide-total="tool.name === 'ppt_generation' ? unrenderedRuntimeImages.length : undefined"
          />
        </div>

        <!-- 结构化证据来源层级展示 (Evidence Sources) -->
        <div
          v-if="evidenceSources.length"
          class="mt-3 rounded-lg border border-primary-100/90 bg-primary-50/30 p-3 dark:border-primary-950/50 dark:bg-primary-950/20"
        >
          <div
            class="flex cursor-pointer items-center justify-between text-xs"
            @click="sourcesExpanded = !sourcesExpanded"
          >
            <div class="flex items-center gap-2 font-medium text-primary-800 dark:text-primary-300">
              <BaseIcon
                name="sparkle"
                size="xs"
              />
              <span>核实的证据来源 · 共 {{ evidenceSources.length }} 条</span>
            </div>
            <div class="flex items-center gap-1.5 text-[11px] text-primary-600 dark:text-primary-400">
              <span>{{ sourcesExpanded ? '收起' : '展开查看来源' }}</span>
              <BaseIcon
                name="chevron-down"
                size="xs"
                class="transition-transform duration-200"
                :class="sourcesExpanded ? 'rotate-180' : 'rotate-0'"
              />
            </div>
          </div>

          <div
            v-if="sourcesExpanded"
            class="mt-2.5 space-y-2.5 border-t border-primary-100/60 pt-2.5 dark:border-primary-900/40"
          >
            <div
              v-for="(src, sIdx) in evidenceSources"
              :key="src.content_hash || sIdx"
              class="rounded-md border border-gray-200/80 bg-white p-2.5 text-xs shadow-2xs dark:border-dark-700 dark:bg-dark-800"
            >
              <div class="flex flex-wrap items-center justify-between gap-1.5 mb-1.5">
                <div class="flex items-center gap-1.5">
                  <span
                    class="rounded border px-1.5 py-0.5 text-[10px] font-medium"
                    :class="getSourceKindBadge(src).class"
                  >
                    {{ getSourceKindBadge(src).label }}
                  </span>
                  <a
                    v-if="src.source_url"
                    :href="src.source_url"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="font-medium text-blue-600 hover:underline dark:text-blue-400 truncate max-w-[280px] sm:max-w-md inline-flex items-center gap-1"
                    :title="src.title || src.source_url"
                  >
                    <span>{{ src.title || src.source_url }}</span>
                    <svg
                      class="h-3 w-3 shrink-0 opacity-70 fill-none stroke-current stroke-2"
                      viewBox="0 0 24 24"
                    >
                      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                      <polyline points="15 3 21 3 21 9" />
                      <line
                        x1="10"
                        y1="14"
                        x2="21"
                        y2="3"
                      />
                    </svg>
                  </a>
                  <span
                    v-else
                    class="font-medium text-gray-800 dark:text-gray-200"
                  >
                    {{ src.title || "未知来源" }}
                  </span>
                </div>
                <div class="flex items-center gap-2 text-[10px] text-gray-400 dark:text-dark-400 font-mono">
                  <span v-if="src.observed_at || src.searched_at">
                    {{ (src.observed_at || src.searched_at)?.slice(0, 19).replace('T', ' ') }}
                  </span>
                  <span
                    v-if="src.content_hash"
                    :title="src.content_hash"
                  >
                    #{{ src.content_hash.slice(0, 8) }}
                  </span>
                </div>
              </div>

              <!-- 摘要 / 正文预览 -->
              <p
                v-if="src.preview"
                class="leading-relaxed text-gray-600 dark:text-dark-300 line-clamp-4 whitespace-pre-wrap bg-gray-50/70 dark:bg-dark-900/60 p-2 rounded text-[11px]"
              >
                {{ src.preview }}
              </p>

              <!-- 底部状态指示（明确标注为只读证据，绝不放置下载按钮） -->
              <div class="mt-1.5 flex items-center justify-between text-[10px] text-gray-400 dark:text-dark-400">
                <span>
                  {{ src.truncated ? "⚠️ 内容已达单源阈值受控截断" : "✅ 完整凭据已登记" }}
                </span>
                <span class="font-mono text-[10px] text-gray-400">
                  来源凭据不可下载 · 仅供正文引用核实
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
      <p
        v-else-if="!['write_todos', 'parse_document'].includes(tool.name)"
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

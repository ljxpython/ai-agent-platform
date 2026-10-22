<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type {
  TrajectoryRecord,
  TrajectoryRecordKind,
} from "../../trajectory/types";
import BaseIcon from "@/components/base/BaseIcon.vue";
import MarkdownContent from "@/components/platform/MarkdownContent.vue";
import { copyDiagnosticPacket } from "@/services/observability/diagnostic-packet";

const props = defineProps<{
  record: TrajectoryRecord | null;
}>();

const emit = defineEmits<{
  close: [];
  "inspect-diagnostic": [];
}>();

const copiedDiagnostic = ref(false);

async function handleCopyDiagnostic() {
  const msg = props.record?.error || props.record?.summary || "";
  const res = await copyDiagnosticPacket({
    customMessage: msg,
    error: props.record?.error,
  });
  if (res.success) {
    copiedDiagnostic.value = true;
    setTimeout(() => {
      copiedDiagnostic.value = false;
    }, 2000);
  }
}

type DetailTab = "summary" | "preview" | "raw";

const activeTab = ref<DetailTab>("summary");
const copied = ref(false);

// 切换 record 时默认回切到 summary
watch(
  () => props.record?.id,
  () => {
    activeTab.value = "summary";
  },
);

function getBadgeStyle(kind: TrajectoryRecordKind) {
  switch (kind) {
    case "system":
      return "bg-gray-100 text-gray-700 dark:bg-dark-800 dark:text-gray-300 border-gray-200 dark:border-dark-700";
    case "context":
      return "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border-emerald-200 dark:border-emerald-900";
    case "user":
      return "bg-blue-50 text-blue-600 dark:bg-blue-950/60 dark:text-blue-300 border-blue-200 dark:border-blue-900";
    case "assistant":
      return "bg-purple-50 text-purple-700 dark:bg-purple-950/60 dark:text-purple-300 border-purple-200 dark:border-purple-900";
    case "reasoning":
      return "bg-indigo-50 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300 border-indigo-200 dark:border-indigo-900";
    case "tool":
    case "subagent":
    default:
      return "bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border-amber-200 dark:border-amber-900";
  }
}

function formatJson(value: unknown): string {
  if (value === undefined) return "—";
  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value);
      return JSON.stringify(parsed, null, 2);
    } catch {
      return value;
    }
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

const previewText = computed<string>(() => {
  if (!props.record) return "";
  if (props.record.kind === "reasoning" && props.record.reasoning) {
    return props.record.reasoning;
  }
  if (typeof props.record.output === "string") {
    return props.record.output;
  }
  if (typeof props.record.input === "string") {
    return props.record.input;
  }
  if (props.record.output !== undefined) {
    return formatJson(props.record.output);
  }
  if (props.record.input !== undefined) {
    return formatJson(props.record.input);
  }
  return props.record.summary || "";
});

async function handleCopy(text: string) {
  try {
    await navigator.clipboard.writeText(text);
    copied.value = true;
    setTimeout(() => {
      copied.value = false;
    }, 1600);
  } catch {
    // 静默降级
  }
}
</script>

<template>
  <aside
    v-if="record"
    class="flex h-full flex-col border-l border-gray-200 bg-white font-sans select-text dark:border-dark-800 dark:bg-dark-900"
    data-testid="trajectory-inspector"
  >
    <!-- Header -->
    <header
      class="flex h-11 items-center justify-between border-b border-gray-200 px-3.5 dark:border-dark-800"
    >
      <div class="flex items-center gap-2 min-w-0">
        <span
          class="inline-block rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider border leading-none font-mono"
          :class="getBadgeStyle(record.kind)"
        >
          {{ record.kind }}
        </span>
        <span
          class="truncate text-xs font-semibold text-gray-900 dark:text-white"
        >
          {{ record.name }}
        </span>
        <span class="text-[11px] font-mono text-gray-400 dark:text-dark-400">
          Turn {{ record.turnIndex }} · Step {{ record.stepIndex }}
        </span>
      </div>
      <button
        type="button"
        class="inline-flex h-6 w-6 items-center justify-center rounded text-gray-400 hover:bg-gray-100 hover:text-gray-700 dark:hover:bg-dark-800 dark:hover:text-gray-200 transition-colors"
        aria-label="关闭检查器"
        @click="emit('close')"
      >
        <BaseIcon name="x" size="xs" />
      </button>
    </header>

    <!-- Tab Bar -->
    <nav
      class="flex border-b border-gray-200 bg-gray-50/60 px-3.5 text-xs dark:border-dark-800 dark:bg-dark-950/40"
    >
      <button
        type="button"
        class="border-b-2 px-3 py-1.5 font-medium transition-colors"
        :class="
          activeTab === 'summary'
            ? 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400'
            : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-dark-400 dark:hover:text-dark-200'
        "
        @click="activeTab = 'summary'"
      >
        Summary
      </button>
      <button
        type="button"
        class="border-b-2 px-3 py-1.5 font-medium transition-colors"
        :class="
          activeTab === 'preview'
            ? 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400'
            : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-dark-400 dark:hover:text-dark-200'
        "
        @click="activeTab = 'preview'"
      >
        Preview
      </button>
      <button
        type="button"
        class="border-b-2 px-3 py-1.5 font-medium transition-colors"
        :class="
          activeTab === 'raw'
            ? 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400'
            : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-dark-400 dark:hover:text-dark-200'
        "
        @click="activeTab = 'raw'"
      >
        Raw
      </button>
    </nav>

    <!-- Content Panel -->
    <div class="relative flex-1 overflow-y-auto p-4 text-xs">
      <!-- 1. Summary Tab -->
      <div v-if="activeTab === 'summary'" class="space-y-4">
        <!-- 极简属性列表 (对齐原版) -->
        <dl
          class="space-y-1.5 border-b border-gray-100 pb-3.5 text-xs dark:border-dark-800"
        >
          <div class="grid grid-cols-[80px_1fr] items-baseline">
            <dt class="text-gray-400 dark:text-dark-400">Source</dt>
            <dd class="font-medium text-gray-800 dark:text-gray-200">
              {{ record.name }}
            </dd>
          </div>
          <div class="grid grid-cols-[80px_1fr] items-baseline">
            <dt class="text-gray-400 dark:text-dark-400">Status</dt>
            <dd
              class="font-semibold"
              :class="{
                'text-emerald-600 dark:text-emerald-400':
                  record.status === 'completed',
                'text-blue-600 dark:text-blue-400': record.status === 'running',
                'text-red-600 dark:text-red-400': record.status === 'error',
                'text-amber-600 dark:text-amber-400':
                  record.status === 'interrupted',
              }"
            >
              {{
                record.status === "completed"
                  ? "Completed"
                  : record.status === "running"
                    ? "Running"
                    : record.status === "interrupted"
                      ? "Interrupted"
                      : "Error"
              }}
            </dd>
          </div>
          <div class="grid grid-cols-[80px_1fr] items-baseline">
            <dt class="text-gray-400 dark:text-dark-400">Duration</dt>
            <dd class="font-mono text-gray-700 dark:text-gray-300">
              {{ record.durationMs ? `${record.durationMs} ms` : "0 ms" }}
            </dd>
          </div>
          <div
            v-if="record.tokens"
            class="grid grid-cols-[80px_1fr] items-baseline"
          >
            <dt class="text-gray-400 dark:text-dark-400">Tokens</dt>
            <dd class="font-mono text-gray-700 dark:text-gray-300">
              In: {{ record.tokens.input ?? 0 }} · Out:
              {{ record.tokens.output ?? 0 }}
            </dd>
          </div>
        </dl>

        <!-- 错误提示与就地排障卡片 -->
        <div
          v-if="record.error || record.status === 'error'"
          class="rounded-lg border border-red-200 bg-red-50/80 p-3.5 text-red-700 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-300 space-y-2.5 shadow-xs"
        >
          <div class="flex items-center justify-between">
            <span class="font-semibold text-xs flex items-center gap-1.5">
              <BaseIcon name="alert" class="h-4 w-4 text-red-500" />
              <span>执行异常诊断 (Execution Error)</span>
            </span>
            <span
              class="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-red-100 text-red-800 dark:bg-red-900/60 dark:text-red-200 font-semibold"
            >
              Error
            </span>
          </div>

          <div
            class="font-mono text-xs text-red-800 dark:text-red-200 whitespace-pre-wrap break-words leading-relaxed bg-white/70 dark:bg-dark-900/60 p-2.5 rounded border border-red-100 dark:border-red-900/40"
          >
            {{ record.error || record.summary }}
          </div>

          <div class="flex items-center gap-2 pt-1">
            <button
              type="button"
              class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-white bg-rose-600 rounded-md hover:bg-rose-700 transition-colors shadow-xs cursor-pointer focus:outline-none focus:ring-2 focus:ring-rose-500/30"
              data-testid="inspector-view-diagnostic-btn"
              @click="emit('inspect-diagnostic')"
            >
              <BaseIcon name="info" class="h-3.5 w-3.5" />
              查看排障详情
            </button>
            <button
              type="button"
              class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-rose-700 bg-white border border-rose-300 rounded-md hover:bg-rose-50 dark:bg-dark-800 dark:border-rose-900/60 dark:text-rose-300 transition-colors shadow-xs cursor-pointer focus:outline-none focus:ring-2 focus:ring-rose-500/20"
              data-testid="inspector-copy-diagnostic-btn"
              @click="handleCopyDiagnostic"
            >
              <BaseIcon
                :name="copiedDiagnostic ? 'check' : 'copy'"
                class="h-3.5 w-3.5"
                :class="copiedDiagnostic ? 'text-emerald-500' : ''"
              />
              {{ copiedDiagnostic ? "已复制" : "复制排障信息" }}
            </button>
          </div>
        </div>

        <!-- 思考过程折叠展示 (若有) -->
        <div
          v-if="record.reasoning"
          class="rounded-lg border border-indigo-100 bg-indigo-50/40 p-3 dark:border-indigo-950 dark:bg-indigo-950/20"
        >
          <div
            class="font-semibold text-indigo-700 dark:text-indigo-300 text-xs mb-1.5 flex items-center gap-1.5"
          >
            <span>深度思考 (Thinking)</span>
          </div>
          <p
            class="font-mono text-[11px] text-gray-700 whitespace-pre-wrap dark:text-gray-300 leading-relaxed"
          >
            {{ record.reasoning }}
          </p>
        </div>

        <!-- 内联 Preview 预览区 -->
        <div>
          <div class="flex items-center justify-between mb-2">
            <span
              class="font-semibold text-gray-500 uppercase tracking-wider text-[11px] dark:text-dark-400"
            >
              Preview
            </span>
            <button
              type="button"
              class="text-blue-600 hover:text-blue-700 text-[11px] font-medium dark:text-blue-400"
              @click="activeTab = 'preview'"
            >
              全屏查看 &gt;
            </button>
          </div>
          <div
            class="rounded-lg border border-gray-100 bg-gray-50/60 p-3 dark:border-dark-800 dark:bg-dark-950/50"
          >
            <MarkdownContent
              v-if="
                typeof record.output === 'string' ||
                typeof record.input === 'string'
              "
              :content="previewText"
            />
            <pre
              v-else
              class="font-mono text-[11px] text-gray-800 overflow-x-auto whitespace-pre-wrap break-all dark:text-gray-200"
              >{{ previewText }}</pre
            >
          </div>
        </div>

        <!-- 工具入参与结果 (若是工具) -->
        <div
          v-if="record.kind === 'tool' && record.input !== undefined"
          class="space-y-3"
        >
          <div>
            <span
              class="font-semibold text-gray-500 uppercase tracking-wider text-[11px] dark:text-dark-400 block mb-1"
            >
              Input Payload
            </span>
            <pre
              class="rounded-lg border border-gray-200 bg-gray-50 p-2.5 font-mono text-[11px] text-gray-800 overflow-x-auto dark:border-dark-800 dark:bg-dark-950 dark:text-gray-200"
              >{{ formatJson(record.input) }}</pre
            >
          </div>
          <div v-if="record.output !== undefined">
            <span
              class="font-semibold text-gray-500 uppercase tracking-wider text-[11px] dark:text-dark-400 block mb-1"
            >
              Output Result
            </span>
            <pre
              class="rounded-lg border border-gray-200 bg-gray-50 p-2.5 font-mono text-[11px] text-gray-800 overflow-x-auto dark:border-dark-800 dark:bg-dark-950 dark:text-gray-200"
              >{{ formatJson(record.output) }}</pre
            >
          </div>
        </div>
      </div>

      <!-- 2. Preview Tab (全幅富文本) -->
      <div v-else-if="activeTab === 'preview'" class="space-y-3">
        <!-- 错误态顶置诊断卡片 -->
        <div
          v-if="record.error || record.status === 'error'"
          class="rounded-lg border border-red-200 bg-red-50/80 p-3 text-red-700 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-300 space-y-2 mb-3"
        >
          <div class="flex items-center justify-between text-xs font-semibold">
            <span class="flex items-center gap-1.5">
              <BaseIcon name="alert" class="h-4 w-4 text-red-500" />
              <span>检测到执行异常</span>
            </span>
            <button
              type="button"
              class="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-white bg-rose-600 rounded hover:bg-rose-700 transition-colors cursor-pointer"
              data-testid="preview-view-diagnostic-btn"
              @click="emit('inspect-diagnostic')"
            >
              <BaseIcon name="info" class="h-3.5 w-3.5" />
              查看排障详情
            </button>
          </div>
        </div>

        <div
          class="flex items-center justify-between pb-2 border-b border-gray-100 dark:border-dark-800"
        >
          <span class="font-semibold text-gray-700 dark:text-gray-300">
            富文本渲染视图
          </span>
          <button
            type="button"
            class="text-xs text-gray-500 hover:text-gray-700 dark:text-dark-400"
            @click="handleCopy(previewText)"
          >
            {{ copied ? "已复制" : "复制内容" }}
          </button>
        </div>
        <div class="prose prose-sm max-w-none dark:prose-invert">
          <MarkdownContent :content="previewText" />
        </div>
      </div>

      <!-- 3. Raw Tab (JSON 视图) -->
      <div
        v-else-if="activeTab === 'raw'"
        class="h-full flex flex-col space-y-2"
      >
        <div class="flex items-center justify-between pb-1">
          <span class="font-mono text-[11px] text-gray-400">JSON Payload</span>
          <button
            type="button"
            class="inline-flex items-center gap-1 rounded border border-gray-200 bg-white px-2 py-0.5 text-[11px] text-gray-600 hover:bg-gray-50 dark:border-dark-700 dark:bg-dark-800 dark:text-gray-300"
            @click="handleCopy(formatJson(record.raw ?? record))"
          >
            <BaseIcon name="copy" size="xs" />
            <span>{{ copied ? "已复制" : "复制" }}</span>
          </button>
        </div>
        <pre
          class="flex-1 overflow-auto rounded-lg border border-gray-200 bg-gray-900 p-3 font-mono text-[11px] text-gray-100 dark:border-dark-800 dark:bg-black/80"
          >{{ formatJson(record.raw ?? record) }}</pre
        >
      </div>
    </div>
  </aside>
</template>

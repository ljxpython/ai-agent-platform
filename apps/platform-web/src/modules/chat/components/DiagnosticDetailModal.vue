<script setup lang="ts">
import { computed, ref, shallowRef, watch } from "vue";
import {
  copyDiagnosticPacket,
  copyToClipboard,
  resolveReasonDetails,
  type DiagnosticContext,
} from "@/services/observability/diagnostic-packet";
import { errorRingBuffer } from "@/services/observability/error-buffer";
import { buildLangfuseTraceUrl } from "@/services/observability/langfuse-url";
import { getRunDiagnostics } from "@/services/threads/diagnostics.service";
import type { RunDiagnosticsV1 } from "../diagnostics/types";

const props = withDefaults(
  defineProps<{
    show: boolean;
    projectId?: string;
    threadId?: string;
    runId?: string | null;
    requestId?: string;
    errorCode?: string;
    error?: unknown;
    canViewTrajectory?: boolean;
  }>(),
  {
    projectId: undefined,
    threadId: undefined,
    runId: null,
    requestId: undefined,
    errorCode: undefined,
    error: undefined,
    canViewTrajectory: true,
  },
);

const emit = defineEmits<{
  "update:show": [value: boolean];
  close: [];
  "open-trajectory": [];
}>();

const copiedPacket = ref(false);
const copiedRequestId = ref(false);
const copiedTraceId = ref(false);
const backendDiagnostics = shallowRef<RunDiagnosticsV1 | null>(null);
const loadingDiagnostics = ref(false);

// 异步加载后端安全诊断快照
async function loadDiagnostics() {
  if (!props.threadId || !props.runId) {
    backendDiagnostics.value = null;
    return;
  }
  loadingDiagnostics.value = true;
  try {
    const res = await getRunDiagnostics(props.threadId, props.runId, {
      projectId: props.projectId,
    });
    backendDiagnostics.value = res;
  } catch {
    // 静默降级，不中断弹窗显示
  } finally {
    loadingDiagnostics.value = false;
  }
}

watch(
  () => [props.show, props.threadId, props.runId],
  ([show]) => {
    if (show && props.threadId && props.runId) {
      loadDiagnostics();
    }
  },
  { immediate: true },
);

// 提取原始错误消息 (结合前端内存与后端安全诊断)
const rawErrorMessage = computed(() => {
  if (typeof props.error === "string" && props.error.trim()) return props.error;
  if (props.error instanceof Error && props.error.message.trim())
    return props.error.message;
  if (props.error && typeof props.error === "object") {
    const errObj = props.error as Record<string, unknown>;
    if (typeof errObj.message === "string" && errObj.message.trim())
      return errObj.message;
    if (typeof errObj.detail === "string" && errObj.detail.trim())
      return errObj.detail;
  }

  // 兜底提取后端真实诊断报错
  const diag = backendDiagnostics.value;
  if (diag) {
    if (diag.model_errors && diag.model_errors.length > 0) {
      return diag.model_errors
        .map(
          (m) =>
            `[Model Failure] Code: ${m.code}, Scope: ${m.scope}${m.provider_status ? `, HTTP: ${m.provider_status}` : ""}${m.error_type ? `, Type: ${m.error_type}` : ""}`,
        )
        .join("\n");
    }
    const failedGraphs = (diag.graph_executions || []).filter(
      (g) => g.outcome !== "success",
    );
    if (failedGraphs.length > 0) {
      return failedGraphs
        .map(
          (g) =>
            `[Graph Execution Failed] Outcome: ${g.outcome}, Code: ${g.error_code || "N/A"}`,
        )
        .join("\n");
    }
    const failedPhases = (diag.startup?.phases || []).filter(
      (p) => p.outcome === "failed",
    );
    if (failedPhases.length > 0) {
      return failedPhases
        .map(
          (p) =>
            `[Startup Phase Failed] Phase: ${p.name}, Code: ${p.error_code || "N/A"}`,
        )
        .join("\n");
    }
    if (diag.run_status === "error") {
      return `[Runtime Error] Run ID ${diag.run_id} 处于失败终态，请查阅轨迹详情。`;
    }
  }

  // 若前端判定为 error 但后端 run 已完成，提示流中断
  if (props.error) {
    try {
      return JSON.stringify(props.error);
    } catch {
      return String(props.error);
    }
  }
  return "";
});

// 提取堆栈
const rawErrorStack = computed(() => {
  if (props.error instanceof Error && props.error.stack) {
    return props.error.stack;
  }
  return "";
});

// 解析错误机器码、人话解释与可操作建议 (借鉴 open-swe)
const reasonInfo = computed(() => {
  const diag = backendDiagnostics.value;
  let code = props.errorCode;
  if (!code && diag?.model_errors?.[0]?.code) {
    code = diag.model_errors[0].code;
  }
  return resolveReasonDetails(code, rawErrorMessage.value);
});

// 关联的最优 Request ID (对账凭据)
const resolvedRequestId = computed(() => {
  const diag = backendDiagnostics.value;
  if (diag?.correlation?.execution_request_id) {
    return diag.correlation.execution_request_id;
  }
  if (diag?.correlation?.platform_trace_id) {
    return diag.correlation.platform_trace_id;
  }
  if (diag?.request_id) {
    return diag.request_id;
  }
  if (props.requestId) return props.requestId;
  const record = errorRingBuffer.getLatest();
  return record?.requestId || "";
});

// 提取 Trace ID 与 Trace URL (对标 open-swe Open Trace)
const traceId = computed(() => {
  return backendDiagnostics.value?.trace?.trace_id || "";
});

const traceUrl = computed(() => {
  if (!traceId.value) return "";
  return buildLangfuseTraceUrl(traceId.value);
});

const handleClose = () => {
  emit("update:show", false);
  emit("close");
};

// 复制 Request ID
const handleCopyRequestId = async () => {
  if (!resolvedRequestId.value) return;
  const ok = await copyToClipboard(resolvedRequestId.value);
  if (ok) {
    copiedRequestId.value = true;
    setTimeout(() => {
      copiedRequestId.value = false;
    }, 2000);
  }
};

// 复制 Trace ID
const handleCopyTraceId = async () => {
  if (!traceId.value) return;
  const ok = await copyToClipboard(traceId.value);
  if (ok) {
    copiedTraceId.value = true;
    setTimeout(() => {
      copiedTraceId.value = false;
    }, 2000);
  }
};

// 一键复制排障诊断包
const handleCopyPacket = async () => {
  const context: DiagnosticContext = {
    projectId: props.projectId,
    threadId: props.threadId,
    runId: props.runId || undefined,
    requestId: resolvedRequestId.value || undefined,
    traceId: traceId.value || undefined,
    traceUrl: traceUrl.value || undefined,
    error: props.error,
    customMessage: reasonInfo.value.reasonText,
    backendDiagnostics:
      (backendDiagnostics.value as unknown as Record<string, unknown>) ||
      undefined,
  };
  const res = await copyDiagnosticPacket(context);
  if (res.success) {
    copiedPacket.value = true;
    setTimeout(() => {
      copiedPacket.value = false;
    }, 2000);
  }
};

// 前往完整轨迹
const handleGoToTrajectory = () => {
  handleClose();
  emit("open-trajectory");
};
</script>

<template>
  <div
    v-if="show"
    class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs animate-in fade-in duration-150"
    role="dialog"
    aria-modal="true"
    aria-labelledby="diagnostic-modal-title"
    @click.self="handleClose"
    @keydown.esc="handleClose"
  >
    <div
      class="flex flex-col w-full max-w-2xl max-h-[85vh] overflow-hidden bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl shadow-2xl"
    >
      <!-- Modal Header -->
      <div
        class="flex items-center justify-between px-6 py-4 border-b border-zinc-100 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-900/50"
      >
        <div class="flex items-center gap-2.5">
          <div
            class="flex items-center justify-center size-8 rounded-lg bg-red-100 text-red-600 dark:bg-red-950/60 dark:text-red-400"
          >
            <svg
              class="size-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>
          <div>
            <h3
              id="diagnostic-modal-title"
              class="text-base font-semibold text-zinc-900 dark:text-zinc-100"
            >
              运行排障诊断详情 (Diagnostic Inspection)
            </h3>
            <p class="text-xs text-zinc-500 dark:text-zinc-400">
              结构化分析 Agent 运行失败根因、链路追踪与恢复建议
            </p>
          </div>
        </div>
        <button
          type="button"
          class="p-1.5 text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 rounded-md transition-colors"
          aria-label="关闭"
          @click="handleClose"
        >
          <svg
            class="size-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>

      <!-- Modal Body -->
      <div class="flex-1 overflow-y-auto p-6 space-y-5 text-sm">
        <!-- Actionable Recovery Card (open-swe 核心模式) -->
        <div
          class="p-4 rounded-lg border border-amber-200 bg-amber-50/70 dark:border-amber-900/50 dark:bg-amber-950/20"
        >
          <div class="flex items-start gap-3">
            <div
              class="mt-0.5 size-5 shrink-0 text-amber-600 dark:text-amber-400"
            >
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            </div>
            <div class="space-y-1.5 flex-1">
              <h4 class="font-medium text-amber-900 dark:text-amber-200">
                操作恢复建议 (Actionable Follow-up)
              </h4>
              <p
                class="text-xs leading-relaxed text-amber-800 dark:text-amber-300"
                data-testid="diagnostic-follow-up"
              >
                {{ reasonInfo.followUp }}
              </p>
            </div>
          </div>
        </div>

        <!-- 分布式链路追踪条目 (对标 open-swe Open Trace) -->
        <div
          v-if="traceId || loadingDiagnostics"
          class="p-3.5 rounded-lg border border-indigo-100 bg-indigo-50/60 dark:border-indigo-900/40 dark:bg-indigo-950/20 flex flex-wrap items-center justify-between gap-3 text-xs"
        >
          <div class="flex items-center gap-2">
            <div class="size-2 rounded-full bg-indigo-500 animate-pulse"></div>
            <span class="font-medium text-indigo-900 dark:text-indigo-200">
              分布式链路追踪 (Langfuse Tracing):
            </span>
            <span
              v-if="traceId"
              class="font-mono text-[11px] text-indigo-700 dark:text-indigo-300 bg-indigo-100/70 dark:bg-indigo-900/60 px-1.5 py-0.5 rounded"
              data-testid="diagnostic-trace-id"
            >
              {{ traceId }}
            </span>
            <button
              v-if="traceId"
              type="button"
              class="p-1 text-indigo-500 hover:text-indigo-700 dark:hover:text-indigo-200 rounded"
              title="复制 Trace ID"
              @click="handleCopyTraceId"
            >
              <span
                v-if="copiedTraceId"
                class="text-[10px] text-green-600 font-sans"
                >已复制</span
              >
              <svg
                v-else
                class="size-3.5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                />
              </svg>
            </button>
            <span
              v-else-if="loadingDiagnostics"
              class="text-zinc-400 italic text-[11px]"
              >正在解析链路信息...</span
            >
          </div>

          <div class="flex items-center gap-2">
            <a
              v-if="traceUrl"
              :href="traceUrl"
              target="_blank"
              rel="noopener noreferrer"
              class="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-indigo-700 bg-white border border-indigo-200 rounded-md shadow-2xs hover:bg-indigo-50 dark:bg-indigo-900/50 dark:text-indigo-200 dark:border-indigo-800 transition-colors"
              data-testid="diagnostic-open-trace-btn"
            >
              <span>Langfuse 追踪</span>
              <svg
                class="size-3"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                />
              </svg>
            </a>
            <router-link
              v-if="traceId || resolvedRequestId"
              :to="{
                path: '/workspace/trace-diagnostics',
                query: { traceId: traceId || resolvedRequestId },
              }"
              target="_blank"
              class="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-emerald-700 bg-white border border-emerald-200 rounded-md shadow-2xs hover:bg-emerald-50 dark:bg-emerald-900/50 dark:text-emerald-200 dark:border-emerald-800 transition-colors"
              data-testid="diagnostic-open-logs-btn"
            >
              <span>微服务全链路日志</span>
              <svg
                class="size-3"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
            </router-link>
          </div>
        </div>

        <!-- 诊断元数据表格 -->
        <div
          class="grid grid-cols-1 md:grid-cols-2 gap-3 p-4 rounded-lg bg-zinc-50 dark:bg-zinc-800/40 border border-zinc-200/80 dark:border-zinc-800"
        >
          <div>
            <span class="text-xs text-zinc-500 dark:text-zinc-400 block mb-0.5">
              原因机器码 (Reason Code)
            </span>
            <span
              class="inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium bg-red-50 text-red-700 dark:bg-red-950/80 dark:text-red-300 border border-red-200 dark:border-red-900"
              data-testid="diagnostic-reason-code"
            >
              {{ reasonInfo.reasonCode }}
            </span>
          </div>

          <div>
            <span class="text-xs text-zinc-500 dark:text-zinc-400 block mb-0.5">
              关联 Request ID (对账凭据)
            </span>
            <div
              class="flex items-center gap-1.5 font-mono text-xs text-zinc-800 dark:text-zinc-200"
            >
              <span
                class="truncate max-w-[200px]"
                data-testid="diagnostic-request-id"
              >
                {{
                  resolvedRequestId ||
                  (loadingDiagnostics ? "解析对账凭据中..." : "未关联或流中断")
                }}
              </span>
              <button
                v-if="resolvedRequestId"
                type="button"
                class="p-1 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 rounded"
                title="复制 Request ID"
                @click="handleCopyRequestId"
              >
                <span
                  v-if="copiedRequestId"
                  class="text-[10px] text-green-600 font-sans"
                  >已复制</span
                >
                <svg
                  v-else
                  class="size-3.5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                  />
                </svg>
              </button>
            </div>
          </div>

          <div>
            <span class="text-xs text-zinc-500 dark:text-zinc-400 block mb-0.5"
              >根因概述</span
            >
            <span
              class="text-xs font-medium text-zinc-700 dark:text-zinc-300"
              data-testid="diagnostic-reason-text"
            >
              {{ reasonInfo.reasonText }}
            </span>
          </div>

          <div>
            <span class="text-xs text-zinc-500 dark:text-zinc-400 block mb-0.5"
              >Run ID</span
            >
            <span class="font-mono text-xs text-zinc-600 dark:text-zinc-400">
              {{ props.runId || "N/A" }}
            </span>
          </div>
        </div>

        <!-- 详细原始错误与调用栈折叠面板 -->
        <div class="space-y-2">
          <details
            class="group rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-800/20"
            open
          >
            <summary
              class="flex items-center justify-between p-3 text-xs font-medium text-zinc-700 dark:text-zinc-300 cursor-pointer select-none"
            >
              <span>查看原始报错详情与堆栈 (Raw Error & Stack)</span>
              <svg
                class="size-4 text-zinc-400 transition-transform group-open:rotate-180"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M19 9l-7 7-7-7"
                />
              </svg>
            </summary>
            <div
              class="p-3 pt-0 space-y-2.5 border-t border-zinc-200/50 dark:border-zinc-800/50 text-xs font-mono"
            >
              <div v-if="rawErrorMessage" class="space-y-1">
                <span class="text-zinc-500 text-[11px] block"
                  >Error Message:</span
                >
                <div
                  class="p-2.5 rounded bg-zinc-100 dark:bg-zinc-950 text-red-600 dark:text-red-400 break-all select-all whitespace-pre-wrap font-mono"
                >
                  {{ rawErrorMessage }}
                </div>
              </div>

              <div v-if="rawErrorStack" class="space-y-1">
                <span class="text-zinc-500 text-[11px] block"
                  >Stack Trace:</span
                >
                <pre
                  class="p-2.5 rounded bg-zinc-100 dark:bg-zinc-950 text-zinc-700 dark:text-zinc-300 text-[11px] max-h-40 overflow-y-auto whitespace-pre-wrap select-all"
                  >{{ rawErrorStack }}</pre
                >
              </div>

              <div
                v-if="!rawErrorMessage && !rawErrorStack"
                class="text-zinc-400 italic py-1"
              >
                {{
                  loadingDiagnostics
                    ? "正在调取服务端诊断信息..."
                    : "无可用原始堆栈信息"
                }}
              </div>
            </div>
          </details>
        </div>
      </div>

      <!-- Modal Footer -->
      <div
        class="flex flex-wrap items-center justify-between gap-3 px-6 py-3.5 border-t border-zinc-100 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-900/50"
      >
        <button
          v-if="canViewTrajectory"
          type="button"
          class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-indigo-700 bg-indigo-50 border border-indigo-200 rounded-lg hover:bg-indigo-100 dark:bg-indigo-950/50 dark:text-indigo-300 dark:border-indigo-900 transition-colors"
          data-testid="go-to-trajectory-btn"
          @click="handleGoToTrajectory"
        >
          <span>前往完整轨迹诊断 (Trajectory)</span>
          <svg
            class="size-3.5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M13 7l5 5m0 0l-5 5m5-5H6"
            />
          </svg>
        </button>
        <div v-else></div>

        <div class="flex items-center gap-2">
          <button
            type="button"
            class="px-3 py-1.5 text-xs font-medium text-zinc-700 dark:text-zinc-300 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg hover:bg-zinc-50 dark:hover:bg-zinc-700 transition-colors"
            @click="handleClose"
          >
            关闭
          </button>
          <button
            type="button"
            class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-white bg-zinc-900 dark:bg-zinc-100 dark:text-zinc-900 rounded-lg hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-colors"
            data-testid="copy-diagnostic-packet-btn"
            @click="handleCopyPacket"
          >
            <svg
              class="size-3.5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3"
              />
            </svg>
            <span>{{
              copiedPacket ? "排障信息已复制" : "复制排障诊断包"
            }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

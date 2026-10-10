<script setup lang="ts">
import { computed, ref, toRef } from "vue";
import { useRunDiagnostics } from "../../composables/useRunDiagnostics";
import { useRunCompletion } from "../../composables/useRunCompletion";
import { formatNotificationTime } from "../../completion/presentation";
import {
  formatDuration,
  getAvailabilityBadge,
  getModelErrorCodeLabel,
  getModelErrorSeverity,
  getPhaseOutcomeLabel,
  getRunStatusBadge,
  truncateIdentifier,
} from "../../diagnostics/view-model";
import BaseIcon from "@/components/base/BaseIcon.vue";
import RunPreparationsSection from "./RunPreparationsSection.vue";
import RunRetriesSection from "./RunRetriesSection.vue";

const props = withDefaults(
  defineProps<{
    projectId?: string;
    threadId: string;
    runId: string | null;
    runs?: Array<{ run_id: string; status: string; created_at?: string }>;
    runsLoading?: boolean;
    canRead?: boolean;
  }>(),
  {
    projectId: undefined,
    runs: () => [],
    runsLoading: false,
    canRead: true,
  },
);

const emit = defineEmits<{
  "select-run": [runId: string];
  close: [];
}>();

const { data, loading, isRefreshing, error, refresh } = useRunDiagnostics({
  projectId: toRef(props, "projectId"),
  threadId: toRef(props, "threadId"),
  runId: toRef(props, "runId"),
  canRead: toRef(props, "canRead"),
  enabled: computed(() => true),
});

const currentRunStatus = computed(() => {
  if (data.value?.run_status) return data.value.run_status;
  const match = props.runs.find((r) => r.run_id === props.runId);
  return match?.status ?? null;
});

const { completion, failurePresentation } = useRunCompletion({
  projectId: toRef(props, "projectId"),
  threadId: toRef(props, "threadId"),
  runId: toRef(props, "runId"),
  canRead: toRef(props, "canRead"),
  isRunning: computed(() => currentRunStatus.value === "running"),
});

const copiedKey = ref<string | null>(null);

async function copyText(key: string, text: string | null | undefined) {
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    copiedKey.value = key;
    setTimeout(() => {
      if (copiedKey.value === key) copiedKey.value = null;
    }, 1500);
  } catch {
    // 静默降级
  }
}

const statusBadge = computed(() => getRunStatusBadge(currentRunStatus.value));
const availBadge = computed(() =>
  getAvailabilityBadge(
    data.value?.availability || "unavailable",
    data.value?.unavailable_reason,
  ),
);
const modelErrorSeverity = computed(() =>
  getModelErrorSeverity(currentRunStatus.value),
);
</script>

<template>
  <aside
    class="flex h-full flex-col border-l border-gray-200 bg-white font-sans select-text dark:border-dark-800 dark:bg-dark-900"
    data-testid="run-diagnostics-panel"
  >
    <!-- Header -->
    <header
      class="flex h-11 items-center justify-between border-b border-gray-200 px-3.5 dark:border-dark-800"
    >
      <div class="flex items-center gap-2 min-w-0">
        <span
          class="inline-block rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider border leading-none font-mono"
          :class="{
            'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border-emerald-200 dark:border-emerald-900':
              statusBadge.variant === 'success',
            'bg-blue-50 text-blue-600 dark:bg-blue-950/60 dark:text-blue-300 border-blue-200 dark:border-blue-900':
              statusBadge.variant === 'running',
            'bg-red-50 text-red-700 dark:bg-red-950/60 dark:text-red-300 border-red-200 dark:border-red-900':
              statusBadge.variant === 'error',
            'bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border-amber-200 dark:border-amber-900':
              statusBadge.variant === 'warning',
            'bg-gray-100 text-gray-700 dark:bg-dark-800 dark:text-gray-300 border-gray-200 dark:border-dark-700':
              statusBadge.variant === 'muted',
          }"
        >
          {{ statusBadge.label }}
        </span>
        <span
          class="text-xs font-semibold text-gray-900 dark:text-white truncate"
        >
          运行诊断
        </span>
        <span
          v-if="runId"
          class="text-[11px] font-mono text-gray-400 dark:text-dark-400 truncate cursor-pointer hover:text-blue-600"
          :title="`点击复制完整 Run ID: ${runId}`"
          @click="copyText('run_id_header', runId)"
        >
          {{ truncateIdentifier(runId) }}
          <span
            v-if="copiedKey === 'run_id_header'"
            class="text-[10px] text-emerald-600"
            >已复制</span
          >
        </span>
      </div>

      <div class="flex items-center gap-1">
        <!-- 切换 Run 下拉框 (若有多条 Run) -->
        <select
          v-if="runs.length > 1"
          :value="runId"
          class="h-6 rounded border border-gray-200 bg-white px-1.5 text-[11px] font-mono text-gray-700 dark:border-dark-700 dark:bg-dark-800 dark:text-gray-200 focus:outline-none"
          aria-label="选择运行目标"
          @change="
            emit('select-run', ($event.target as HTMLSelectElement).value)
          "
        >
          <option v-for="r in runs" :key="r.run_id" :value="r.run_id">
            {{ truncateIdentifier(r.run_id, 6) }} ({{ r.status }})
          </option>
        </select>

        <!-- 刷新按钮 -->
        <button
          type="button"
          data-testid="refresh-diagnostics-btn"
          class="inline-flex h-6 w-6 items-center justify-center rounded text-gray-400 hover:bg-gray-100 hover:text-gray-700 dark:hover:bg-dark-800 dark:hover:text-gray-200 transition-colors"
          :class="{ 'animate-spin text-blue-600': loading || isRefreshing }"
          :disabled="loading || isRefreshing || !runId"
          title="刷新诊断"
          aria-label="刷新诊断"
          @click="refresh"
        >
          <BaseIcon name="refresh" size="xs" />
        </button>

        <!-- 关闭按钮 -->
        <button
          type="button"
          class="inline-flex h-6 w-6 items-center justify-center rounded text-gray-400 hover:bg-gray-100 hover:text-gray-700 dark:hover:bg-dark-800 dark:hover:text-gray-200 transition-colors"
          aria-label="关闭诊断面板"
          @click="emit('close')"
        >
          <BaseIcon name="x" size="xs" />
        </button>
      </div>
    </header>

    <!-- Main Content Area -->
    <div class="flex-1 overflow-y-auto p-4 text-xs space-y-4">
      <!-- 1. 无 Run 状态 -->
      <div
        v-if="!runId"
        class="rounded-lg border border-gray-200 bg-gray-50/60 p-6 text-center text-gray-500 dark:border-dark-800 dark:bg-dark-950/40"
      >
        <p class="font-medium text-xs">未选择运行目标</p>
        <p class="text-[11px] text-gray-400 mt-1">
          当前会话暂无生效的 Run ID，请发起对话或选择历史运行
        </p>
      </div>

      <!-- 2. 加载中骨架 -->
      <div v-else-if="loading && !data" class="space-y-3 animate-pulse">
        <div class="h-12 bg-gray-100 rounded dark:bg-dark-800" />
        <div class="h-24 bg-gray-100 rounded dark:bg-dark-800" />
        <div class="h-20 bg-gray-100 rounded dark:bg-dark-800" />
      </div>

      <!-- 3. 错误态提示卡片 -->
      <div
        v-else-if="error && !data"
        class="rounded-lg border border-red-200 bg-red-50/80 p-3.5 text-red-700 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-300 space-y-2"
      >
        <div class="flex items-center gap-1.5 font-semibold text-xs">
          <BaseIcon name="alert" size="xs" />
          <span>查询诊断失败</span>
        </div>
        <p class="font-mono text-[11px] break-all">
          {{ error.message }}
        </p>
        <button
          type="button"
          class="rounded bg-white px-2.5 py-1 text-[11px] font-medium text-red-700 border border-red-300 hover:bg-red-50 dark:bg-dark-900 dark:border-red-800 dark:text-red-300"
          @click="refresh"
        >
          重试查询
        </button>
      </div>

      <!-- 4. 正常诊断数据展示 -->
      <template v-else-if="data">
        <!-- 终态安全失败摘要卡片 (来自受管 completion) -->
        <div
          v-if="failurePresentation"
          data-testid="completion-failure-summary-card"
          class="rounded-lg border border-rose-200 bg-rose-50/80 p-3 text-rose-800 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-200 space-y-1.5 shadow-2xs"
        >
          <div class="flex items-center justify-between">
            <div
              class="flex items-center gap-1.5 font-semibold text-xs text-rose-700 dark:text-rose-300"
            >
              <BaseIcon name="alert" size="xs" />
              <span>终态原因：{{ failurePresentation.title }}</span>
            </div>
            <span
              v-if="completion?.occurred_at"
              class="text-[10px] text-rose-500/80 dark:text-rose-400/80 font-mono"
            >
              {{ formatNotificationTime(completion.occurred_at) }}
            </span>
          </div>
          <p class="text-[11px] text-rose-700/90 dark:text-rose-300/90">
            {{ failurePresentation.detail }}
          </p>
          <div
            class="flex items-center justify-between pt-1 text-[11px] border-t border-rose-200/60 dark:border-rose-900/40"
          >
            <span class="text-rose-600/90 dark:text-rose-400">
              建议：{{ failurePresentation.suggestedAction }}
            </span>
          </div>
        </div>

        <!-- Running 状态提示横幅 -->
        <div
          v-if="data.run_status === 'running'"
          class="rounded-lg border border-blue-200 bg-blue-50/60 p-2.5 text-blue-700 dark:border-blue-900/40 dark:bg-blue-950/30 dark:text-blue-300 flex items-center justify-between"
        >
          <span class="text-[11px]"
            >任务正在执行中，完整诊断数据将在运行结束后导出。</span
          >
          <button
            type="button"
            class="text-[11px] font-medium underline"
            @click="refresh"
          >
            刷新
          </button>
        </div>

        <!-- 极简摘要卡片 -->
        <dl
          class="grid grid-cols-2 gap-2 rounded-lg border border-gray-100 bg-gray-50/60 p-3 text-xs dark:border-dark-800 dark:bg-dark-950/50"
        >
          <div>
            <dt class="text-[11px] text-gray-400 dark:text-dark-400">
              数据可用性
            </dt>
            <dd class="font-medium text-gray-800 dark:text-gray-200 mt-0.5">
              {{ availBadge.label }}
            </dd>
          </div>
          <div>
            <dt class="text-[11px] text-gray-400 dark:text-dark-400">
              启动总耗时
            </dt>
            <dd
              class="font-mono font-medium text-gray-800 dark:text-gray-200 mt-0.5"
            >
              {{ formatDuration(data.startup?.duration_ms) }}
            </dd>
          </div>
          <div>
            <dt class="text-[11px] text-gray-400 dark:text-dark-400">
              图观察执行数
            </dt>
            <dd
              class="font-mono font-medium text-gray-800 dark:text-gray-200 mt-0.5"
            >
              {{ data.graph_executions.length }} 次
            </dd>
          </div>
          <div>
            <dt class="text-[11px] text-gray-400 dark:text-dark-400">
              模型失败记录
            </dt>
            <dd
              class="font-mono font-medium mt-0.5"
              :class="
                data.model_errors.length > 0
                  ? modelErrorSeverity === 'warning'
                    ? 'text-amber-600 dark:text-amber-400'
                    : 'text-red-600 dark:text-red-400'
                  : 'text-gray-700 dark:text-gray-300'
              "
            >
              {{ data.model_errors.length }} 次
            </dd>
          </div>
        </dl>

        <!-- 模型失败记录区域 -->
        <div class="space-y-2">
          <div class="flex items-center justify-between">
            <span
              class="font-semibold text-gray-700 dark:text-gray-300 text-[11px] uppercase tracking-wider"
            >
              模型调用记录
            </span>
            <span
              v-if="
                data.model_errors.length > 0 && modelErrorSeverity === 'warning'
              "
              class="text-[10px] text-amber-600 dark:text-amber-400"
            >
              已通过重试或备选模型恢复
            </span>
          </div>

          <div
            v-if="data.model_errors.length === 0"
            class="rounded-lg border border-gray-100 bg-gray-50/40 p-2.5 text-center text-gray-400 text-[11px] dark:border-dark-800 dark:bg-dark-950/30"
          >
            无模型调用失败记录
          </div>

          <div v-else class="space-y-2">
            <div
              v-for="err in data.model_errors"
              :key="err.observation_id"
              class="rounded-lg border p-2.5 space-y-1 font-mono text-[11px]"
              :class="
                modelErrorSeverity === 'warning'
                  ? 'border-amber-200 bg-amber-50/60 text-amber-800 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-300'
                  : 'border-red-200 bg-red-50/60 text-red-800 dark:border-red-900/40 dark:bg-red-950/30 dark:text-red-300'
              "
            >
              <div class="flex items-center justify-between">
                <span class="font-semibold">{{
                  getModelErrorCodeLabel(err.code)
                }}</span>
                <span
                  v-if="err.provider_status"
                  class="rounded bg-white/80 px-1 py-0.2 text-[10px] dark:bg-black/40"
                  >HTTP {{ err.provider_status }}</span
                >
              </div>
              <div
                class="text-[10px] text-gray-500 dark:text-dark-400 flex items-center gap-2"
              >
                <span>Scope: {{ err.scope }}</span>
                <span v-if="err.duration_ms !== null"
                  >耗时: {{ formatDuration(err.duration_ms) }}</span
                >
                <span v-if="err.error_type">类型: {{ err.error_type }}</span>
              </div>
              <div
                v-if="err.namespace.length > 0"
                class="text-[10px] text-gray-400 truncate"
              >
                Namespace: {{ err.namespace.join(" / ") }}
              </div>
            </div>
          </div>
        </div>

        <!-- 启动阶段流水 (Startup Phases) -->
        <div
          v-if="data.startup && data.startup.phases.length > 0"
          class="space-y-2"
        >
          <span
            class="font-semibold text-gray-700 dark:text-gray-300 text-[11px] uppercase tracking-wider block"
          >
            启动阶段流水
          </span>
          <div
            class="rounded-lg border border-gray-100 bg-gray-50/40 divide-y divide-gray-100 dark:border-dark-800 dark:bg-dark-950/30 dark:divide-dark-800"
          >
            <div
              v-for="phase in data.startup.phases"
              :key="phase.ordinal"
              class="flex items-center justify-between p-2 text-[11px]"
            >
              <div class="flex items-center gap-2 min-w-0">
                <span
                  class="text-gray-400 font-mono text-[10px] w-4 text-center"
                  >{{ phase.ordinal }}</span
                >
                <span
                  class="font-medium text-gray-800 dark:text-gray-200 truncate"
                  >{{ phase.name }}</span
                >
              </div>
              <div
                class="flex items-center gap-2 font-mono text-[10px] text-gray-500 dark:text-dark-400 shrink-0"
              >
                <span>{{ formatDuration(phase.duration_ms) }}</span>
                <span
                  class="rounded px-1 py-0.5 leading-none text-[9px]"
                  :class="
                    phase.outcome === 'completed'
                      ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
                      : 'bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300'
                  "
                >
                  {{ getPhaseOutcomeLabel(phase.outcome) }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- 运行准备记录 (Preparations) -->
        <RunPreparationsSection
          v-if="data.preparations && data.preparations.length > 0"
          :preparations="data.preparations"
        />

        <!-- 调用尝试与重试 (Retries) -->
        <RunRetriesSection
          v-if="data.retries && data.retries.length > 0"
          :retries="data.retries"
          :run-status="currentRunStatus"
        />

        <!-- 关联标识卡片 (可复制 ID 矩阵，绝不开通配 Raw JSON) -->
        <div
          class="space-y-2 pt-2 border-t border-gray-100 dark:border-dark-800"
        >
          <span
            class="font-semibold text-gray-700 dark:text-gray-300 text-[11px] uppercase tracking-wider block"
          >
            关联信息编号 (Correlation IDs)
          </span>
          <div class="space-y-1.5 font-mono text-[11px]">
            <div
              class="flex items-center justify-between bg-gray-50 p-1.5 rounded dark:bg-dark-950"
            >
              <span class="text-gray-400 text-[10px]">Run ID:</span>
              <div class="flex items-center gap-1 min-w-0">
                <span
                  class="truncate max-w-[170px] text-gray-700 dark:text-gray-300"
                  >{{ data.run_id }}</span
                >
                <button
                  type="button"
                  class="text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
                  title="复制 Run ID"
                  @click="copyText('run_id', data.run_id)"
                >
                  <BaseIcon
                    :name="copiedKey === 'run_id' ? 'check' : 'copy'"
                    size="xs"
                  />
                </button>
              </div>
            </div>

            <div
              v-if="data.correlation.execution_request_id"
              class="flex items-center justify-between bg-gray-50 p-1.5 rounded dark:bg-dark-950"
            >
              <span class="text-gray-400 text-[10px]"
                >Execution Request ID:</span
              >
              <div class="flex items-center gap-1 min-w-0">
                <span
                  class="truncate max-w-[170px] text-gray-700 dark:text-gray-300"
                  >{{ data.correlation.execution_request_id }}</span
                >
                <button
                  type="button"
                  class="text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
                  title="复制 Execution Request ID"
                  @click="
                    copyText('exec_id', data.correlation.execution_request_id)
                  "
                >
                  <BaseIcon
                    :name="copiedKey === 'exec_id' ? 'check' : 'copy'"
                    size="xs"
                  />
                </button>
              </div>
            </div>

            <div
              v-if="data.trace?.trace_id"
              class="flex items-center justify-between bg-gray-50 p-1.5 rounded dark:bg-dark-950"
            >
              <span class="text-gray-400 text-[10px]"
                >Trace ID (Langfuse):</span
              >
              <div class="flex items-center gap-1 min-w-0">
                <span
                  class="truncate max-w-[170px] text-gray-700 dark:text-gray-300"
                  >{{ data.trace.trace_id }}</span
                >
                <button
                  type="button"
                  class="text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
                  title="复制 Trace ID"
                  @click="copyText('trace_id', data.trace.trace_id)"
                >
                  <BaseIcon
                    :name="copiedKey === 'trace_id' ? 'check' : 'copy'"
                    size="xs"
                  />
                </button>
              </div>
            </div>

            <div
              class="flex items-center justify-between bg-gray-50 p-1.5 rounded dark:bg-dark-950"
            >
              <span class="text-gray-400 text-[10px]">Query Request ID:</span>
              <div class="flex items-center gap-1 min-w-0">
                <span
                  class="truncate max-w-[170px] text-gray-700 dark:text-gray-300"
                  >{{ data.request_id }}</span
                >
                <button
                  type="button"
                  class="text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
                  title="复制 Query Request ID"
                  @click="copyText('req_id', data.request_id)"
                >
                  <BaseIcon
                    :name="copiedKey === 'req_id' ? 'check' : 'copy'"
                    size="xs"
                  />
                </button>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>
  </aside>
</template>

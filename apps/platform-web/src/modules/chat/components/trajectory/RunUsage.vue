<script setup lang="ts">
import { computed, toRef } from "vue";
import { useRunUsage } from "../../composables/useRunUsage";
import {
  formatTokenCount,
  formatTokenCompact,
  formatCostUsd,
  formatCallDuration,
  calculateCacheHitRate,
  getUsageAvailabilityBadge,
  getCallScopeBadge,
  getCallPurposeLabel,
  getCallOutcomeBadge,
  getCallQualityBadge,
} from "../../usage/view-model";
import BaseIcon from "@/components/base/BaseIcon.vue";

const props = withDefaults(
  defineProps<{
    projectId?: string;
    threadId: string;
    runId: string | null;
    runs?: Array<{ run_id: string; status: string; created_at?: string }>;
    runsLoading?: boolean;
    canRead?: boolean;
    runStatus?: string | null;
  }>(),
  {
    projectId: undefined,
    runs: () => [],
    runsLoading: false,
    canRead: true,
    runStatus: null,
  },
);

const emit = defineEmits<{
  "select-run": [runId: string];
  close: [];
}>();

const {
  runData,
  runLoading,
  isRunRefreshing,
  runError,
  calls,
  nextCursor,
  loadingMore,
  loadMoreError,
  loadMoreCalls,
  threadData,
  refresh,
} = useRunUsage({
  projectId: toRef(props, "projectId"),
  threadId: toRef(props, "threadId"),
  runId: toRef(props, "runId"),
  runStatus: toRef(props, "runStatus"),
  canRead: toRef(props, "canRead"),
  enabled: computed(() => true),
});

const currentRun = computed(() =>
  props.runs.find((r) => r.run_id === props.runId),
);

// 优先使用完整 tokens，若完整不可用则使用 known_tokens
const displayTokens = computed(() => {
  if (runData.value?.tokens && runData.value.tokens.total_tokens !== null) {
    return { tokens: runData.value.tokens, isPartial: false };
  }
  return {
    tokens: runData.value?.known_tokens ?? null,
    isPartial: true,
  };
});

// Run 成本展示 (分流 disabled、unavailable 与 unknown)
const runCost = computed(() =>
  formatCostUsd(
    runData.value?.cost.status === "partial"
      ? runData.value?.cost.known_cost_usd
      : runData.value?.cost.estimated_cost_usd,
    runData.value?.cost.status,
    runData.value?.availability,
    runData.value?.unavailable_reason,
  ),
);

// Thread 成本展示
const threadCost = computed(() =>
  formatCostUsd(
    threadData.value?.cost.status === "partial"
      ? threadData.value?.cost.known_cost_usd
      : threadData.value?.cost.estimated_cost_usd,
    threadData.value?.cost.status,
    threadData.value?.availability,
    threadData.value?.unavailable_reason,
  ),
);

const availBadge = computed(() =>
  getUsageAvailabilityBadge(
    runData.value?.availability || "unavailable",
    runData.value?.unavailable_reason,
  ),
);

const cacheHitRate = computed(() => {
  const toks = displayTokens.value.tokens;
  return calculateCacheHitRate(toks?.input_tokens, toks?.cache_read_tokens);
});

const cacheHitPercentage = computed(() => {
  const toks = displayTokens.value.tokens;
  if (
    !toks?.input_tokens ||
    !toks?.cache_read_tokens ||
    toks.input_tokens <= 0
  ) {
    return 0;
  }
  return Math.min(
    Math.round((toks.cache_read_tokens / toks.input_tokens) * 100),
    100,
  );
});

const tokenBudget = computed(() => runData.value?.token_budget ?? null);

const budgetUsagePercentage = computed(() => {
  if (!tokenBudget.value) return 0;
  const used = tokenBudget.value.known_used_tokens ?? 0;
  const max = tokenBudget.value.max_tokens;
  if (!max || max <= 0) return 0;
  return Math.min(Math.round((used / max) * 100), 100);
});

const budgetColorClass = computed(() => {
  if (!tokenBudget.value) return "bg-blue-500";
  if (tokenBudget.value.coverage === "unavailable") return "bg-amber-500";
  const used = tokenBudget.value.known_used_tokens ?? 0;
  const max = tokenBudget.value.max_tokens;
  if (used >= max) return "bg-red-500";
  if (used >= (tokenBudget.value.warn_at_tokens || max * 0.8)) {
    return "bg-amber-500";
  }
  return "bg-blue-500";
});

const stopCodeBadge = computed(() => {
  const code = tokenBudget.value?.stop_code;
  if (!code) return null;
  if (code === "token_budget_exhausted") {
    return { label: "额度耗尽强停", variant: "error" };
  }
  if (code === "token_budget_unverifiable") {
    return { label: "用量待对账停机", variant: "warning" };
  }
  return null;
});

function handleRunChange(e: Event) {
  const target = e.target as HTMLSelectElement;
  if (target?.value) {
    emit("select-run", target.value);
  }
}
</script>

<template>
  <aside
    class="flex h-full flex-col border-l border-gray-200 bg-white font-sans select-text dark:border-dark-800 dark:bg-dark-900"
    data-testid="run-usage-panel"
  >
    <!-- 头部工具栏 -->
    <header
      class="flex h-11 items-center justify-between border-b border-gray-200 px-3.5 dark:border-dark-800"
    >
      <div class="flex items-center gap-2 min-w-0">
        <span
          class="inline-block rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider border leading-none font-mono"
          :class="{
            'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border-emerald-200 dark:border-emerald-900':
              availBadge.variant === 'success',
            'bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border-amber-200 dark:border-amber-900':
              availBadge.variant === 'warning',
            'bg-gray-100 text-gray-700 dark:bg-dark-800 dark:text-gray-300 border-gray-200 dark:border-dark-700':
              availBadge.variant === 'muted',
          }"
        >
          {{ availBadge.label }}
        </span>
        <h3
          class="text-xs font-semibold text-gray-900 dark:text-gray-100 truncate"
        >
          用量与成本分析
        </h3>
      </div>

      <div class="flex items-center gap-1.5">
        <button
          type="button"
          data-testid="refresh-usage-btn"
          class="inline-flex h-6 w-6 items-center justify-center rounded text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-dark-400 dark:hover:bg-dark-800 dark:hover:text-gray-200 transition-colors"
          :disabled="runLoading || isRunRefreshing"
          title="刷新用量"
          @click="refresh"
        >
          <BaseIcon
            name="refresh"
            size="xs"
            :class="{ 'animate-spin': isRunRefreshing }"
          />
        </button>

        <button
          type="button"
          data-testid="close-usage-btn"
          class="inline-flex h-6 w-6 items-center justify-center rounded text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-dark-400 dark:hover:bg-dark-800 dark:hover:text-gray-200 transition-colors"
          title="关闭面板"
          @click="emit('close')"
        >
          <BaseIcon name="x" size="xs" />
        </button>
      </div>
    </header>

    <!-- 主体可滚动区 -->
    <div class="flex-1 overflow-y-auto p-4 space-y-4">
      <!-- 1. Run 切换选择器 -->
      <div v-if="runs && runs.length > 1" class="flex items-center gap-2">
        <label
          class="text-[11px] font-medium text-gray-500 dark:text-dark-400 shrink-0"
        >
          目标 Run:
        </label>
        <select
          :value="runId"
          class="h-7 w-full rounded border border-gray-200 bg-gray-50 px-2 text-xs text-gray-800 dark:border-dark-700 dark:bg-dark-950 dark:text-gray-200"
          @change="handleRunChange"
        >
          <option v-for="r in runs" :key="r.run_id" :value="r.run_id">
            {{ r.run_id.slice(0, 8) }} ({{ r.status }})
          </option>
        </select>
      </div>

      <!-- 2. 加载骨架屏 -->
      <div v-if="runLoading && !runData" class="space-y-3 animate-pulse">
        <div class="h-20 bg-gray-100 dark:bg-dark-800 rounded-lg" />
        <div class="h-32 bg-gray-100 dark:bg-dark-800 rounded-lg" />
        <div class="h-24 bg-gray-100 dark:bg-dark-800 rounded-lg" />
      </div>

      <!-- 3. 错误态展示 -->
      <div
        v-else-if="runError && !runData"
        class="rounded-lg border border-red-200 bg-red-50/50 p-4 text-xs text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300"
      >
        <div class="font-semibold mb-1">加载用量失败</div>
        <div class="text-[11px] opacity-90 mb-3">{{ runError.message }}</div>
        <button
          type="button"
          class="rounded bg-red-600 px-2.5 py-1 text-[11px] text-white hover:bg-red-700 transition-colors"
          @click="refresh"
        >
          重试
        </button>
      </div>

      <!-- 4. 正常数据区 -->
      <template v-else-if="runData">
        <!-- 截断警告卡片 (若存在服务端维度截断) -->
        <div
          v-if="runData.truncated || threadData?.truncated"
          data-testid="usage-truncated-alert"
          class="rounded-lg border border-amber-200 bg-amber-50/70 p-3 text-xs text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-300 flex items-start gap-2"
        >
          <BaseIcon
            name="shield"
            size="xs"
            class="shrink-0 mt-0.5 text-amber-600"
          />
          <div>
            <div class="font-semibold">用量数据已受限截断</div>
            <div class="text-[11px] opacity-90 mt-0.5">
              历史价格版本较多或受限维度已被服务端截断，当前仅展示保留部分。
            </div>
          </div>
        </div>

        <!-- 借鉴 open-swe Context Usage Meter 紧凑水位仪表（结合 Token Budget 额度保护） -->
        <div
          class="rounded-lg border border-gray-200 bg-gray-50/70 p-3 dark:border-dark-800 dark:bg-dark-900/60 space-y-2.5"
          data-testid="context-meter-card"
        >
          <!-- 1. Token 额度水位条（仅在 token_budget 存在时展示） -->
          <div
            v-if="tokenBudget"
            class="space-y-1.5"
            data-testid="token-budget-section"
          >
            <div class="flex items-center justify-between text-xs">
              <div
                class="flex items-center gap-1.5 font-medium text-gray-700 dark:text-gray-300"
              >
                <BaseIcon name="shield" size="xs" class="text-indigo-500" />
                <span>Token 额度保护 (Run Cap)</span>
                <span
                  v-if="stopCodeBadge"
                  class="rounded px-1.5 py-0.2 text-[10px] font-mono leading-tight border"
                  :class="{
                    'bg-red-50 text-red-700 border-red-200 dark:bg-red-950/60 dark:text-red-300 dark:border-red-900':
                      stopCodeBadge.variant === 'error',
                    'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/60 dark:text-amber-300 dark:border-amber-900':
                      stopCodeBadge.variant === 'warning',
                  }"
                >
                  {{ stopCodeBadge.label }}
                </span>
              </div>
              <div
                class="font-mono text-[11px] text-gray-600 dark:text-dark-300"
              >
                <template v-if="tokenBudget.coverage === 'unavailable'">
                  <span class="text-amber-600 dark:text-amber-400">
                    用量待对账
                  </span>
                  · 上限 {{ tokenBudget.max_tokens.toLocaleString() }}
                </template>
                <template v-else>
                  {{ (tokenBudget.known_used_tokens ?? 0).toLocaleString() }} /
                  {{ tokenBudget.max_tokens.toLocaleString() }}
                  <span
                    v-if="
                      (tokenBudget.known_used_tokens ?? 0) >=
                      tokenBudget.max_tokens
                    "
                    class="text-red-500 font-semibold ml-0.5"
                    >({{
                      Math.round(
                        ((tokenBudget.known_used_tokens ?? 0) /
                          tokenBudget.max_tokens) *
                          100,
                      )
                    }}%)</span
                  >
                </template>
              </div>
            </div>
            <!-- 额度进度条 -->
            <div
              class="h-1.5 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-dark-700"
            >
              <div
                class="h-full rounded-full transition-all duration-500"
                :class="budgetColorClass"
                :style="{ width: budgetUsagePercentage + '%' }"
                :title="`额度使用率: ${tokenBudget.coverage === 'unavailable' ? '未知' : budgetUsagePercentage + '%'}`"
              />
            </div>
          </div>

          <!-- 2. 缓存命中水位条 -->
          <div class="space-y-1.5 pt-0.5">
            <div class="flex items-center justify-between text-xs">
              <div
                class="flex items-center gap-1.5 font-medium text-gray-700 dark:text-gray-300"
              >
                <BaseIcon name="activity" size="xs" class="text-blue-500" />
                <span>运行水位 (Usage Meter)</span>
              </div>
              <div
                class="font-mono text-[11px] text-gray-500 dark:text-dark-400"
              >
                {{ formatTokenCompact(displayTokens.tokens?.total_tokens) }}
                tokens
                <template v-if="cacheHitRate !== '未采集'">
                  · 缓存命中 {{ cacheHitRate }}
                </template>
              </div>
            </div>
            <!-- 缓存读取在输入中的占比进度条 -->
            <div
              class="h-1.5 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-dark-700"
            >
              <div
                class="h-full rounded-full bg-emerald-500 transition-all duration-500"
                :style="{ width: cacheHitPercentage + '%' }"
                :title="`缓存命中率: ${cacheHitRate}`"
              />
            </div>
          </div>
        </div>

        <!-- 成本与覆盖率卡片 -->
        <div
          class="rounded-lg border border-gray-200 bg-gray-50/70 p-3.5 dark:border-dark-800 dark:bg-dark-900/60"
        >
          <div class="flex items-center justify-between mb-2">
            <span
              class="text-[11px] font-medium text-gray-500 dark:text-dark-400"
            >
              Run 估算成本 (USD)
              <span
                v-if="currentRun"
                class="ml-1 text-[10px] text-gray-400 font-mono"
              >
                ({{ currentRun.run_id.slice(0, 8) }})
              </span>
            </span>
            <span
              v-if="runCost.isPartial"
              class="text-[10px] bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 px-1.5 py-0.5 rounded font-mono"
            >
              已知小计
            </span>
          </div>

          <div class="flex items-baseline gap-2">
            <span
              class="text-2xl font-bold font-mono text-gray-900 dark:text-white"
              :title="runCost.fullUsd"
            >
              {{ runCost.display }}
            </span>
            <span
              v-if="runCost.fullUsd && runCost.display !== runCost.fullUsd"
              class="text-[10px] font-mono text-gray-400 dark:text-dark-500"
            >
              ({{ runCost.fullUsd }})
            </span>
          </div>

          <div
            v-if="runData.cost.unpriced_call_count > 0"
            class="mt-2 text-[11px] text-amber-600 dark:text-amber-400"
          >
            存在 {{ runData.cost.unpriced_call_count }} 次未配置价格的模型调用
          </div>

          <div
            v-if="runData.coverage.collection_degraded"
            class="mt-1 text-[11px] text-red-600 dark:text-red-400"
          >
            ⚠️ 本次 Run 采集曾发生局部降级，数据可能不完整
          </div>
        </div>

        <!-- Token 层级分解卡片 -->
        <div
          class="rounded-lg border border-gray-200 bg-white p-3.5 dark:border-dark-800 dark:bg-dark-900"
        >
          <div
            class="flex items-center justify-between mb-3 border-b pb-2 border-gray-100 dark:border-dark-800"
          >
            <span
              class="text-xs font-semibold text-gray-900 dark:text-gray-100"
            >
              Token 消耗明细
            </span>
            <span
              v-if="displayTokens.isPartial"
              class="text-[10px] text-amber-600 dark:text-amber-400"
            >
              (展示已采集小计)
            </span>
          </div>

          <div class="space-y-2 text-xs font-mono">
            <!-- 总计 -->
            <div
              class="flex items-center justify-between font-semibold text-gray-900 dark:text-white"
            >
              <span>总 Tokens:</span>
              <span>{{
                formatTokenCount(displayTokens.tokens?.total_tokens)
              }}</span>
            </div>

            <!-- 输入与缓存读取 -->
            <div
              class="flex items-center justify-between text-gray-700 dark:text-gray-300 pt-1"
            >
              <span>输入 (Input):</span>
              <span>{{
                formatTokenCount(displayTokens.tokens?.input_tokens)
              }}</span>
            </div>
            <div
              class="flex items-center justify-between text-[11px] text-gray-500 pl-3"
            >
              <span>└ 缓存读取 (Read):</span>
              <span
                >{{
                  formatTokenCount(displayTokens.tokens?.cache_read_tokens)
                }}
                (命中 {{ cacheHitRate }})</span
              >
            </div>

            <!-- 缓存创建总量及 TTL -->
            <div
              class="flex items-center justify-between text-gray-700 dark:text-gray-300 pt-1"
            >
              <span>缓存写入 (Creation):</span>
              <span>{{
                formatTokenCount(displayTokens.tokens?.cache_creation_tokens)
              }}</span>
            </div>
            <div
              class="flex items-center justify-between text-[11px] text-gray-500 pl-3"
            >
              <span>├ 5分钟 TTL:</span>
              <span>{{
                formatTokenCount(displayTokens.tokens?.cache_creation_5m_tokens)
              }}</span>
            </div>
            <div
              class="flex items-center justify-between text-[11px] text-gray-500 pl-3"
            >
              <span>└ 1小时 TTL:</span>
              <span>{{
                formatTokenCount(displayTokens.tokens?.cache_creation_1h_tokens)
              }}</span>
            </div>

            <!-- 输出与深度思考 -->
            <div
              class="flex items-center justify-between text-gray-700 dark:text-gray-300 pt-1"
            >
              <span>输出 (Output):</span>
              <span>{{
                formatTokenCount(displayTokens.tokens?.output_tokens)
              }}</span>
            </div>
            <div
              class="flex items-center justify-between text-[11px] text-gray-500 pl-3"
            >
              <span>└ 思考推理 (Reasoning):</span>
              <span>{{
                formatTokenCount(displayTokens.tokens?.reasoning_tokens)
              }}</span>
            </div>
          </div>
        </div>

        <!-- Thread 会话累计卡片 -->
        <div
          v-if="threadData"
          class="rounded-lg border border-blue-100 bg-blue-50/40 p-3.5 dark:border-blue-900/40 dark:bg-blue-950/20"
        >
          <div class="flex items-center justify-between mb-2">
            <span
              class="text-xs font-semibold text-blue-900 dark:text-blue-300"
            >
              会话累计已采集汇总
            </span>
            <span
              class="text-[10px] font-mono text-blue-700 dark:text-blue-400"
            >
              覆盖 {{ threadData.recorded_run_count }} 个 Run
            </span>
          </div>

          <div
            class="flex items-center justify-between text-xs font-mono text-gray-700 dark:text-gray-300"
          >
            <div class="flex items-center gap-1.5">
              <span>会话累计成本:</span>
              <span
                v-if="threadCost.isPartial"
                class="text-[10px] bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 px-1 py-0.2 rounded font-mono"
              >
                已知小计
              </span>
            </div>
            <span
              class="font-bold text-gray-900 dark:text-white"
              :title="threadCost.fullUsd"
            >
              {{ threadCost.display }}
            </span>
          </div>
          <div
            class="flex items-center justify-between text-xs font-mono text-gray-700 dark:text-gray-300 mt-1"
          >
            <div class="flex items-center gap-1.5">
              <span>会话累计 Tokens:</span>
              <span
                v-if="
                  threadData.tokens.total_tokens === null &&
                  threadData.known_tokens.total_tokens !== null
                "
                class="text-[10px] text-amber-600 dark:text-amber-400"
              >
                (已采集小计)
              </span>
            </div>
            <span>{{
              formatTokenCount(
                threadData.tokens.total_tokens ??
                  threadData.known_tokens.total_tokens,
              )
            }}</span>
          </div>

          <div
            v-if="threadData.coverage.excluded_operations.length > 0"
            class="mt-2 text-[10px] text-blue-600/80 dark:text-blue-400/80"
          >
            * 排除项:
            {{ threadData.coverage.excluded_operations.join(", ") }}
            不计入原生汇总
          </div>
        </div>

        <!-- 模型调用明细流水 -->
        <div class="space-y-2">
          <div
            class="flex items-center justify-between text-xs font-semibold text-gray-900 dark:text-gray-100"
          >
            <span>模型调用明细 ({{ calls.length }})</span>
            <span
              v-if="calls.length > 0"
              class="text-[10px] text-gray-400 font-normal"
            >
              按时间升序
            </span>
          </div>

          <div
            v-if="calls.length === 0"
            class="py-4 text-center text-xs text-gray-400"
          >
            无模型调用记录
          </div>

          <div
            v-for="call in calls"
            :key="call.model_call_id"
            class="rounded border border-gray-100 bg-gray-50/50 p-2.5 text-xs dark:border-dark-800 dark:bg-dark-900/40 space-y-1.5"
            data-testid="usage-call-item"
          >
            <div class="flex items-center justify-between">
              <span
                class="font-semibold text-gray-800 dark:text-gray-200 truncate"
              >
                {{ call.model_name || call.model_id || "未知模型" }}
              </span>
              <div class="flex items-center gap-1.5">
                <!-- Outcome 胶囊 -->
                <span
                  class="rounded px-1.5 py-0.2 text-[10px] font-mono"
                  :class="{
                    'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300':
                      call.outcome === 'completed',
                    'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300':
                      call.outcome === 'failed',
                    'bg-gray-100 text-gray-700 dark:bg-dark-800 dark:text-gray-300':
                      call.outcome === 'cancelled',
                    'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300':
                      call.outcome === 'started',
                  }"
                >
                  {{ getCallOutcomeBadge(call.outcome).label }}
                </span>

                <!-- Scope 胶囊 -->
                <span
                  class="rounded px-1.5 py-0.2 text-[10px] font-mono"
                  :class="{
                    'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300':
                      call.scope === 'primary',
                    'bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300':
                      call.scope === 'subagent',
                    'bg-gray-100 text-gray-700 dark:bg-dark-800 dark:text-gray-300':
                      call.scope === 'auxiliary',
                  }"
                >
                  {{ getCallScopeBadge(call.scope).label }}
                </span>
              </div>
            </div>

            <div
              class="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-gray-500 font-mono"
            >
              <span>用途: {{ getCallPurposeLabel(call.purpose) }}</span>
              <span>·</span>
              <span
                >耗时:
                {{ formatCallDuration(call.started_at, call.ended_at) }}</span
              >
              <span>·</span>
              <span
                >Tokens: {{ formatTokenCount(call.tokens.total_tokens) }}</span
              >
              <span>·</span>
              <span>{{
                formatCostUsd(call.cost.estimated_cost_usd, call.cost.status)
                  .display
              }}</span>
              <template v-if="getCallQualityBadge(call.quality).isDegraded">
                <span>·</span>
                <span class="text-amber-600 dark:text-amber-400">
                  ({{ getCallQualityBadge(call.quality).label }})
                </span>
              </template>
            </div>

            <!-- 子项明细: 缓存读取与推理 -->
            <div
              v-if="
                (call.tokens.cache_read_tokens &&
                  call.tokens.cache_read_tokens > 0) ||
                (call.tokens.reasoning_tokens &&
                  call.tokens.reasoning_tokens > 0)
              "
              class="flex items-center gap-3 text-[10px] font-mono text-gray-400 pl-1"
            >
              <span v-if="call.tokens.cache_read_tokens">
                缓存读取: {{ formatTokenCount(call.tokens.cache_read_tokens) }}
              </span>
              <span v-if="call.tokens.reasoning_tokens">
                思考输出: {{ formatTokenCount(call.tokens.reasoning_tokens) }}
              </span>
            </div>
          </div>

          <!-- 加载更多与重试 -->
          <div v-if="nextCursor" class="pt-2 space-y-1.5">
            <button
              type="button"
              data-testid="load-more-calls-btn"
              class="w-full rounded border border-gray-200 py-1.5 text-xs text-gray-600 hover:bg-gray-50 dark:border-dark-700 dark:text-dark-300 dark:hover:bg-dark-800 transition-colors"
              :disabled="loadingMore"
              @click="loadMoreCalls"
            >
              {{ loadingMore ? "加载中..." : "加载更多调用..." }}
            </button>
            <div
              v-if="loadMoreError"
              class="text-center text-[11px] text-red-600 dark:text-red-400"
            >
              加载下一页明细失败:
              {{ loadMoreError.message }}，请点击上方按钮重试
            </div>
          </div>
          <div
            v-else-if="calls.length > 0"
            class="pt-1 text-center text-[10px] text-gray-400 dark:text-dark-500"
          >
            已展示全部调用
          </div>
        </div>
      </template>

      <!-- 5. 暂无 Run 选中 -->
      <div v-else class="py-8 text-center text-xs text-gray-400">
        请选择一个 Run 查看用量
      </div>
    </div>
  </aside>
</template>

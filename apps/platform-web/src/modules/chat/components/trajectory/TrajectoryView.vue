<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { BaseMessage } from "@langchain/core/messages";
import type { AssembledToolCall } from "@langchain/vue";
import {
  buildTrajectoryRecords,
  groupTrajectoryByTurn,
} from "../../trajectory/trajectory-adapter";
import type { TrajectoryRecord } from "../../trajectory/types";
import TrajectoryLedger from "./TrajectoryLedger.vue";
import TrajectoryInspector from "./TrajectoryInspector.vue";
import TrajectoryTimeline from "./TrajectoryTimeline.vue";
import RunDiagnostics from "./RunDiagnostics.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";

const props = withDefaults(
  defineProps<{
    messages: readonly BaseMessage[];
    calls: readonly AssembledToolCall[];
    isRunning: boolean;
    projectId?: string;
    threadId?: string;
    runId?: string | null;
    runs?: Array<{ run_id: string; status: string; created_at?: string }>;
    runsLoading?: boolean;
    canRead?: boolean;
  }>(),
  {
    projectId: undefined,
    threadId: undefined,
    runId: null,
    runs: () => [],
    runsLoading: false,
    canRead: true,
  },
);

const emit = defineEmits<{
  "select-run": [runId: string];
}>();

const records = computed(() =>
  buildTrajectoryRecords(props.messages, props.calls, props.isRunning),
);

const groups = computed(() => groupTrajectoryByTurn(records.value));

type InspectorMode = "record" | "diagnostics";
const inspectorMode = ref<InspectorMode>("record");

const selectedRecordId = ref<string | null>(null);
const isInspectorOpen = ref(true);
const filter = ref<"all" | "tools" | "errors">("all");
const searchQuery = ref("");
const actualDuration = ref(true);
const allTurnsCollapsed = ref(false);
const allCallsCollapsed = ref(false);

const selectedRunId = ref<string | null>(props.runId ?? null);
watch(
  () => props.runId,
  (val) => {
    selectedRunId.value = val ?? null;
  },
);

// 统计信息
const stats = computed(() => {
  let toolsCount = 0;
  let errorsCount = 0;
  let totalInputTokens = 0;
  let totalOutputTokens = 0;

  for (const r of records.value) {
    if (r.kind === "tool" || r.kind === "subagent") toolsCount++;
    if (r.status === "error") errorsCount++;
    if (r.tokens?.input) totalInputTokens += r.tokens.input;
    if (r.tokens?.output) totalOutputTokens += r.tokens.output;
  }
  return {
    turns: groups.value.length,
    steps: records.value.length,
    tools: toolsCount,
    errors: errorsCount,
    inputTokens: totalInputTokens,
    outputTokens: totalOutputTokens,
  };
});

// 监听并在没有选中项或选中失效时，自动选中最新一条
watch(
  () => records.value.length,
  (newLen) => {
    if (
      newLen > 0 &&
      !records.value.some((r) => r.id === selectedRecordId.value)
    ) {
      selectedRecordId.value = records.value[newLen - 1]?.id ?? null;
    }
  },
  { immediate: true },
);

const selectedRecord = computed<TrajectoryRecord | null>(() => {
  if (!selectedRecordId.value) return null;
  return records.value.find((r) => r.id === selectedRecordId.value) ?? null;
});

function handleSelect(record: TrajectoryRecord) {
  selectedRecordId.value = record.id;
  inspectorMode.value = "record";
  isInspectorOpen.value = true;
}

function handleToggleDiagnostics() {
  if (inspectorMode.value === "diagnostics") {
    inspectorMode.value = "record";
  } else {
    inspectorMode.value = "diagnostics";
    isInspectorOpen.value = true;
  }
}

function handleSelectRun(runId: string) {
  selectedRunId.value = runId;
  emit("select-run", runId);
}

function handleCloseInspector() {
  isInspectorOpen.value = false;
  if (inspectorMode.value === "diagnostics") {
    inspectorMode.value = "record";
  }
}
</script>

<template>
  <div
    class="flex h-full w-full flex-col overflow-hidden bg-white dark:bg-dark-950 font-sans"
    data-testid="trajectory-view"
  >
    <!-- 1. Top Toolbar: Indicators + Controls + Diagnostics Toggle + Search + Filter -->
    <div
      class="flex flex-wrap items-center justify-between gap-3 border-b border-gray-200/90 bg-white px-3.5 py-2 select-none dark:border-dark-800 dark:bg-dark-900"
    >
      <!-- Left: Duration / Turns / Calls Controls + Diagnostics Entry + Stats -->
      <div class="flex items-center gap-2 text-xs">
        <div class="flex items-center gap-1.5">
          <button
            type="button"
            class="inline-flex h-6.5 items-center gap-1 rounded border px-2 text-[11px] font-mono transition-colors"
            :class="
              actualDuration
                ? 'border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-900/60 dark:bg-blue-950/40 dark:text-blue-300 font-semibold'
                : 'border-gray-200 bg-white text-gray-500 hover:bg-gray-50 dark:border-dark-700 dark:bg-dark-900 dark:text-dark-400'
            "
            :title="
              actualDuration
                ? '切换为等宽模式 (Use Equal Width)'
                : '切换为真实耗时模式 (Use Actual Duration)'
            "
            @click="actualDuration = !actualDuration"
          >
            <svg
              class="h-3 w-3 fill-none stroke-current stroke-[2]"
              viewBox="0 0 24 24"
            >
              <circle cx="12" cy="12" r="9" />
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M12 7v5l3 2"
              />
            </svg>
            <span>Duration</span>
          </button>

          <button
            type="button"
            class="inline-flex h-6.5 items-center gap-1 rounded border border-gray-200 bg-white px-2 text-[11px] font-mono text-gray-600 shadow-2xs hover:bg-gray-50 dark:border-dark-700 dark:bg-dark-900 dark:text-dark-300 dark:hover:bg-dark-800 transition-colors"
            :class="{
              'border-blue-300 bg-blue-50/60 text-blue-700 font-semibold dark:border-blue-800/60 dark:bg-blue-950/40 dark:text-blue-300':
                allTurnsCollapsed,
            }"
            :title="
              allTurnsCollapsed
                ? '展开所有轮次 (Expand Turns)'
                : '折叠所有轮次 (Collapse Turns)'
            "
            @click="allTurnsCollapsed = !allTurnsCollapsed"
          >
            <span class="font-mono text-xs">{{
              allTurnsCollapsed ? "⊞" : "⊟"
            }}</span>
            <span>Turns</span>
          </button>

          <button
            type="button"
            class="inline-flex h-6.5 items-center gap-1 rounded border border-gray-200 bg-white px-2 text-[11px] font-mono text-gray-600 shadow-2xs hover:bg-gray-50 dark:border-dark-700 dark:bg-dark-900 dark:text-dark-300 dark:hover:bg-dark-800 transition-colors"
            :class="{
              'border-amber-300 bg-amber-50/60 text-amber-800 font-semibold dark:border-amber-800/60 dark:bg-amber-950/40 dark:text-amber-300':
                allCallsCollapsed,
            }"
            :title="
              allCallsCollapsed
                ? '展开所有工具调用 (Expand Calls)'
                : '折叠所有工具调用 (Collapse Calls)'
            "
            @click="allCallsCollapsed = !allCallsCollapsed"
          >
            <span class="font-mono text-xs">{{
              allCallsCollapsed ? "⊞" : "⊟"
            }}</span>
            <span>Calls</span>
          </button>

          <!-- 运行诊断常驻入口 (构图失败无消息时仍可直接点击打开) -->
          <button
            type="button"
            data-testid="toggle-diagnostics-btn"
            class="inline-flex h-6.5 items-center gap-1 rounded border px-2 text-[11px] font-mono transition-colors"
            :class="
              inspectorMode === 'diagnostics' && isInspectorOpen
                ? 'border-indigo-300 bg-indigo-50 text-indigo-700 dark:border-indigo-800/60 dark:bg-indigo-950/40 dark:text-indigo-300 font-semibold shadow-2xs'
                : 'border-gray-200 bg-white text-gray-600 shadow-2xs hover:bg-gray-50 dark:border-dark-700 dark:bg-dark-900 dark:text-dark-300 dark:hover:bg-dark-800'
            "
            title="查看当前运行诊断与健康报告"
            @click="handleToggleDiagnostics"
          >
            <BaseIcon name="shield" size="xs" />
            <span>运行诊断</span>
          </button>
        </div>

        <div
          class="h-3.5 w-px bg-gray-200 dark:bg-dark-700 mx-1 hidden sm:block"
        />

        <!-- Stats Overview Banner -->
        <div
          class="flex items-center gap-1.5 font-mono text-xs text-gray-900 dark:text-white font-semibold"
        >
          <span>{{ stats.turns }} 轮</span>
          <span>·</span>
          <span>{{ stats.steps }} 步</span>
          <span>·</span>
          <span
            :class="
              stats.tools > 0
                ? 'text-amber-600 dark:text-amber-400'
                : 'text-gray-400 dark:text-dark-500'
            "
            >{{ stats.tools }} 工具</span
          >
          <template v-if="stats.errors > 0">
            <span>·</span>
            <span class="text-red-600 dark:text-red-400"
              >{{ stats.errors }} 异常</span
            >
          </template>
        </div>
      </div>

      <!-- Right: Search + Filter -->
      <div class="flex items-center gap-2.5">
        <!-- Search Input -->
        <div class="relative flex items-center">
          <BaseIcon
            name="search"
            size="xs"
            class="absolute left-2.5 text-gray-400 pointer-events-none"
          />
          <input
            v-model="searchQuery"
            type="search"
            placeholder="搜索轨迹..."
            class="h-7 w-36 sm:w-48 rounded-md border border-gray-200 bg-gray-50/70 pl-7 pr-2.5 text-xs text-gray-800 placeholder-gray-400 outline-none transition-all focus:border-blue-500 focus:bg-white focus:ring-1 focus:ring-blue-500 dark:border-dark-700 dark:bg-dark-950 dark:text-gray-100 dark:focus:bg-dark-900"
          />
        </div>

        <!-- Filter Segment -->
        <div
          class="flex items-center rounded-md bg-gray-100 p-0.5 text-[11px] font-medium dark:bg-dark-800"
        >
          <button
            type="button"
            class="rounded px-2 py-0.5 transition-colors"
            :class="
              filter === 'all'
                ? 'bg-white text-gray-900 shadow-xs dark:bg-dark-900 dark:text-white'
                : 'text-gray-600 hover:text-gray-900 dark:text-dark-400 dark:hover:text-gray-200'
            "
            @click="filter = 'all'"
          >
            全部 ({{ stats.steps }})
          </button>
          <button
            type="button"
            class="rounded px-2 py-0.5 transition-colors"
            :class="
              filter === 'tools'
                ? 'bg-white text-gray-900 shadow-xs dark:bg-dark-900 dark:text-white'
                : 'text-gray-600 hover:text-gray-900 dark:text-dark-400 dark:hover:text-gray-200'
            "
            @click="filter = 'tools'"
          >
            仅工具 ({{ stats.tools }})
          </button>
          <button
            v-if="stats.errors > 0"
            type="button"
            class="rounded px-2 py-0.5 transition-colors"
            :class="
              filter === 'errors'
                ? 'bg-red-50 text-red-700 shadow-xs dark:bg-red-950/60 dark:text-red-300'
                : 'text-red-600 hover:text-red-700 dark:text-red-400'
            "
            @click="filter = 'errors'"
          >
            仅错误 ({{ stats.errors }})
          </button>
        </div>
      </div>
    </div>

    <!-- 2. Multi-lane Gantt Timeline Strip -->
    <TrajectoryTimeline
      :records="records"
      :selected-record-id="selectedRecordId"
      :actual-duration="actualDuration"
      @select="handleSelect"
    />

    <!-- 3. Main Master-Detail Body -->
    <div class="flex flex-1 min-h-0 overflow-hidden">
      <!-- Left: Ledger Table -->
      <div
        class="flex-1 min-w-0 flex flex-col h-full"
        :class="{
          'max-w-[48%] border-r border-gray-200 dark:border-dark-800':
            isInspectorOpen &&
            (inspectorMode === 'diagnostics' || selectedRecord),
        }"
      >
        <TrajectoryLedger
          :groups="groups"
          :selected-record-id="
            inspectorMode === 'record' ? selectedRecordId : null
          "
          :filter="filter"
          :search-query="searchQuery"
          :all-turns-collapsed="allTurnsCollapsed"
          :all-calls-collapsed="allCallsCollapsed"
          @select="handleSelect"
        />
      </div>

      <!-- Right: Inspector Panel (Record or Diagnostics) -->
      <div
        v-if="
          isInspectorOpen && (inspectorMode === 'diagnostics' || selectedRecord)
        "
        class="flex-1 min-w-0 h-full overflow-hidden"
      >
        <!-- 运行诊断独立面板 -->
        <RunDiagnostics
          v-if="inspectorMode === 'diagnostics'"
          :project-id="projectId"
          :thread-id="threadId || ''"
          :run-id="selectedRunId"
          :runs="runs"
          :runs-loading="runsLoading"
          :can-read="canRead"
          @select-run="handleSelectRun"
          @close="handleCloseInspector"
        />

        <!-- 单条记录详情面板 (保持原有职责不变) -->
        <TrajectoryInspector
          v-else-if="selectedRecord"
          :record="selectedRecord"
          @close="handleCloseInspector"
        />
      </div>
    </div>

    <!-- 4. Footer Metrics Strip -->
    <footer
      class="flex items-center justify-between border-t border-gray-200/80 bg-gray-50/50 px-3.5 py-1 text-[11px] font-mono text-gray-500 select-none dark:border-dark-800 dark:bg-dark-900/40 dark:text-dark-400"
    >
      <div class="flex items-center gap-2">
        <span>{{ stats.turns }} 轮 · {{ stats.steps }} 步</span>
        <span>|</span>
        <span>工具 {{ stats.tools }} 次</span>
        <template v-if="stats.inputTokens > 0 || stats.outputTokens > 0">
          <span>|</span>
          <span
            >Tokens: In {{ stats.inputTokens.toLocaleString() }} · Out
            {{ stats.outputTokens.toLocaleString() }}</span
          >
        </template>
      </div>
      <div class="text-[10px] text-gray-400 dark:text-dark-500">
        Trajectory Engine
      </div>
    </footer>
  </div>
</template>

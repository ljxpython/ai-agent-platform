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
import BaseIcon from "@/components/base/BaseIcon.vue";

const props = defineProps<{
  messages: readonly BaseMessage[];
  calls: readonly AssembledToolCall[];
  isRunning: boolean;
}>();

const records = computed(() =>
  buildTrajectoryRecords(props.messages, props.calls, props.isRunning),
);

const groups = computed(() => groupTrajectoryByTurn(records.value));

const selectedRecordId = ref<string | null>(null);
const isInspectorOpen = ref(true);
const filter = ref<"all" | "tools" | "errors">("all");
const searchQuery = ref("");

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
    if (newLen > 0 && !records.value.some((r) => r.id === selectedRecordId.value)) {
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
  isInspectorOpen.value = true;
}

function handleCloseInspector() {
  isInspectorOpen.value = false;
}
</script>

<template>
  <div
    class="flex h-full w-full flex-col overflow-hidden bg-white dark:bg-dark-950 font-sans"
    data-testid="trajectory-view"
  >
    <!-- 1. Top Toolbar: Indicators + Search + Filter -->
    <div class="flex flex-wrap items-center justify-between gap-3 border-b border-gray-200/90 bg-white px-3.5 py-2 select-none dark:border-dark-800 dark:bg-dark-900">
      <!-- Left: Indicators -->
      <div class="flex items-center gap-3 text-xs">
        <div class="flex items-center gap-1.5 font-mono text-[11px] text-gray-500 dark:text-dark-400">
          <span class="font-semibold text-gray-900 dark:text-white">
            {{ stats.turns }} 轮 · {{ stats.steps }} 步
          </span>
          <span>·</span>
          <span>{{ stats.tools }} 工具</span>
          <span
            v-if="stats.errors > 0"
            class="text-red-600 dark:text-red-400 font-semibold"
          >
            · {{ stats.errors }} 异常
          </span>
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
          >
        </div>

        <!-- Filter Segment -->
        <div class="flex items-center rounded-md bg-gray-100 p-0.5 text-[11px] font-medium dark:bg-dark-800">
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
      @select="handleSelect"
    />

    <!-- 3. Main Master-Detail Body -->
    <div class="flex flex-1 min-h-0 overflow-hidden">
      <!-- Left: Ledger Table -->
      <div
        class="flex-1 min-w-0 flex flex-col h-full"
        :class="{
          'max-w-[48%] border-r border-gray-200 dark:border-dark-800': isInspectorOpen && selectedRecord,
        }"
      >
        <TrajectoryLedger
          :groups="groups"
          :selected-record-id="selectedRecordId"
          :filter="filter"
          :search-query="searchQuery"
          @select="handleSelect"
        />
      </div>

      <!-- Right: Inspector Panel -->
      <div
        v-if="isInspectorOpen && selectedRecord"
        class="flex-1 min-w-0 h-full overflow-hidden"
      >
        <TrajectoryInspector
          :record="selectedRecord"
          @close="handleCloseInspector"
        />
      </div>
    </div>

    <!-- 4. Footer Metrics Strip -->
    <footer class="flex items-center justify-between border-t border-gray-200/80 bg-gray-50/50 px-3.5 py-1 text-[11px] font-mono text-gray-500 select-none dark:border-dark-800 dark:bg-dark-900/40 dark:text-dark-400">
      <div class="flex items-center gap-2">
        <span>{{ stats.turns }} 轮 · {{ stats.steps }} 步</span>
        <span>|</span>
        <span>工具 {{ stats.tools }} 次</span>
        <template v-if="stats.inputTokens > 0 || stats.outputTokens > 0">
          <span>|</span>
          <span>Tokens: In {{ stats.inputTokens.toLocaleString() }} · Out {{ stats.outputTokens.toLocaleString() }}</span>
        </template>
      </div>
      <div class="text-[10px] text-gray-400 dark:text-dark-500">
        Trajectory Engine
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import type { UsageRun } from "../types";
import { formatCompactTokens } from "../view-model";

interface Props {
  runs: UsageRun[];
  loading?: boolean;
  loadingMore?: boolean;
  hasMore?: boolean;
  activeFilterRange?: { from: string; to: string } | null;
  projectId?: string;
}

withDefaults(defineProps<Props>(), {
  runs: () => [],
  loading: false,
  loadingMore: false,
  hasMore: false,
  activeFilterRange: null,
  projectId: undefined,
});

const emit = defineEmits<{
  (e: "select-run", run: UsageRun): void;
  (e: "clear-range"): void;
  (e: "load-more"): void;
}>();

function formatTime(iso: string) {
  if (!iso) return "--";
  const d = new Date(iso);
  return d.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function calculateDurationMs(startIso: string, endIso: string): number {
  const s = new Date(startIso).getTime();
  const e = new Date(endIso).getTime();
  return Math.max(0, e - s);
}
</script>

<template>
  <div
    class="space-y-4 rounded-2xl border border-gray-100 bg-white p-5 shadow-sm dark:border-dark-800 dark:bg-dark-900/90"
  >
    <!-- 顶栏状态与范围高亮条 -->
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div class="flex items-center gap-2">
        <h3 class="text-sm font-semibold text-gray-900 dark:text-white">
          网关调用日志 (Invocation Logs)
        </h3>
        <span
          class="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600 dark:bg-dark-800 dark:text-gray-300"
        >
          共 {{ runs.length }} 条记录
        </span>
      </div>

      <!-- 下钻过滤区间 Pill -->
      <div
        v-if="activeFilterRange"
        class="flex items-center gap-2 rounded-xl bg-primary-50 px-3 py-1 text-xs text-primary-700 dark:bg-primary-950/40 dark:text-primary-300"
      >
        <span>当前下钻锁定区间:</span>
        <span class="font-mono font-medium"
          >{{ activeFilterRange.from.slice(11, 19) }} ~
          {{ activeFilterRange.to.slice(11, 19) }}</span
        >
        <button
          type="button"
          class="ml-1 rounded p-0.5 hover:bg-primary-100 dark:hover:bg-primary-900"
          title="清除下钻区间限制"
          @click="emit('clear-range')"
        >
          <svg
            class="h-3.5 w-3.5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
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
    </div>

    <!-- 无项目提示（平台模式未指定单一项目时） -->
    <div
      v-if="!projectId"
      class="flex flex-col items-center justify-center py-12 text-center"
    >
      <div
        class="flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-50 text-amber-500 dark:bg-amber-950/30 dark:text-amber-400"
      >
        <svg
          class="h-6 w-6"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="1.5"
            d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
      </div>
      <p class="mt-3 text-sm font-medium text-gray-800 dark:text-dark-200">
        请选择具体项目以查看调用明细
      </p>
      <p class="mt-1 text-xs text-gray-400 dark:text-dark-500">
        平台级概览保护隐私，仅支持在指定项目内查阅真实调用日志与 Trace 链路
      </p>
    </div>

    <!-- 加载中骨架 -->
    <div
      v-else-if="loading && runs.length === 0"
      class="flex flex-col items-center justify-center py-16"
    >
      <div
        class="h-6 w-6 animate-spin rounded-full border-2 border-primary-500 border-t-transparent"
      />
      <span class="mt-3 text-xs text-gray-500 dark:text-dark-400"
        >检索日志明细中...</span
      >
    </div>

    <!-- 空数据 -->
    <div
      v-else-if="runs.length === 0"
      class="flex flex-col items-center justify-center py-16 text-center"
    >
      <div
        class="flex h-12 w-12 items-center justify-center rounded-2xl bg-gray-100 text-gray-400 dark:bg-dark-800 dark:text-dark-400"
      >
        <svg
          class="h-6 w-6"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="1.5"
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
          />
        </svg>
      </div>
      <p class="mt-3 text-sm font-medium text-gray-700 dark:text-dark-300">
        此时间段暂无调用记录
      </p>
      <p class="mt-1 text-xs text-gray-400 dark:text-dark-500">
        可调整时间范围或点击上方清除下钻限制
      </p>
    </div>

    <!-- 列表表格 -->
    <div v-else class="overflow-x-auto">
      <table class="w-full text-left text-xs">
        <thead
          class="border-b border-gray-100 text-gray-400 dark:border-dark-800 dark:text-dark-500"
        >
          <tr>
            <th class="py-3 px-3 font-medium">调用时刻</th>
            <th class="py-3 px-3 font-medium">Agent / Graph</th>
            <th class="py-3 px-3 font-medium">耗时</th>
            <th class="py-3 px-3 font-medium">输入 Token</th>
            <th class="py-3 px-3 font-medium">输出 Token</th>
            <th class="py-3 px-3 font-medium">缓存命中 (Tokens)</th>
            <th class="py-3 px-3 font-medium">预估费用</th>
            <th class="py-3 px-3 text-right font-medium">操作</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-50 dark:divide-dark-800/60">
          <tr
            v-for="run in runs"
            :key="run.run_id"
            class="group transition hover:bg-gray-50/80 dark:hover:bg-dark-800/40"
          >
            <td class="py-3 px-3 text-gray-600 dark:text-dark-300 font-mono">
              {{ formatTime(run.first_matching_call_at) }}
            </td>
            <td class="py-3 px-3 font-medium text-gray-900 dark:text-white">
              <div
                class="truncate max-w-[160px]"
                :title="run.agent_name || run.graph_id"
              >
                {{ run.agent_name || run.graph_id }}
              </div>
              <div
                class="text-[10px] text-gray-400 dark:text-dark-500 font-mono truncate max-w-[160px]"
              >
                {{ run.run_id }}
              </div>
            </td>
            <td class="py-3 px-3 text-gray-600 dark:text-dark-300 font-mono">
              {{
                calculateDurationMs(
                  run.first_matching_call_at,
                  run.last_matching_call_at,
                )
              }}
              ms
            </td>
            <td class="py-3 px-3 text-gray-700 dark:text-dark-200">
              {{ formatCompactTokens(run.tokens.input_tokens) }}
            </td>
            <td class="py-3 px-3 text-gray-700 dark:text-dark-200">
              {{ formatCompactTokens(run.tokens.output_tokens) }}
            </td>
            <td class="py-3 px-3">
              <span
                v-if="
                  run.tokens.cache_read_tokens &&
                  run.tokens.cache_read_tokens > 0
                "
                class="inline-flex items-center gap-1 rounded bg-emerald-50 px-1.5 py-0.5 text-[11px] font-medium text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300"
              >
                {{ formatCompactTokens(run.tokens.cache_read_tokens) }}
              </span>
              <span v-else class="text-gray-400 dark:text-dark-500">0</span>
            </td>
            <td
              class="py-3 px-3 font-mono font-medium text-emerald-600 dark:text-emerald-400"
            >
              ${{
                parseFloat(
                  run.cost.known_cost_usd || run.cost.estimated_cost_usd || "0",
                ).toFixed(5)
              }}
            </td>
            <td class="py-3 px-3 text-right">
              <button
                type="button"
                class="rounded-lg px-2.5 py-1 text-xs font-medium text-primary-600 hover:bg-primary-50 dark:text-primary-400 dark:hover:bg-primary-950/40 transition"
                @click="emit('select-run', run)"
              >
                查看 Trace
              </button>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- 加载更多 -->
      <div v-if="hasMore" class="mt-4 flex justify-center">
        <button
          type="button"
          class="rounded-xl border border-gray-200 bg-white px-4 py-2 text-xs font-medium text-gray-700 shadow-sm transition hover:bg-gray-50 dark:border-dark-700 dark:bg-dark-800 dark:text-gray-200 dark:hover:bg-dark-700 disabled:opacity-50"
          :disabled="loadingMore"
          @click="emit('load-more')"
        >
          {{ loadingMore ? "加载中..." : "加载更多日志" }}
        </button>
      </div>
    </div>
  </div>
</template>

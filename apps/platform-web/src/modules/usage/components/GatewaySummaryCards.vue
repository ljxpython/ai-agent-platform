<script setup lang="ts">
import { computed } from "vue";
import type { GatewaySummary } from "../types";

interface Props {
  summary?: GatewaySummary | null;
  loading?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  summary: null,
  loading: false,
});

const errorRatePercent = computed(() => {
  if (!props.summary) return "0.00";
  return (props.summary.error_rate * 100).toFixed(2);
});

const isErrorRateWarning = computed(() => {
  if (!props.summary) return false;
  return props.summary.error_rate > 0.01; // 错误率高于 1% 预警
});

const cacheHitRatioPercent = computed(() => {
  if (!props.summary || props.summary.cache_hit_ratio == null) return null;
  return (props.summary.cache_hit_ratio * 100).toFixed(1);
});

const formattedTotalTokens = computed(() => {
  if (!props.summary) return "0";
  const t = props.summary.total_tokens;
  if (t >= 1000000000) return (t / 1000000000).toFixed(2) + " B";
  if (t >= 1000000) return (t / 1000000).toFixed(2) + " M";
  if (t >= 1000) return (t / 1000).toFixed(1) + " k";
  return t.toLocaleString();
});

const formattedCost = computed(() => {
  if (!props.summary) return "$0.0000";
  return `$${parseFloat(props.summary.total_cost_usd || "0").toFixed(4)}`;
});
</script>

<template>
  <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
    <!-- 卡片 1：总请求数 & 错误率 -->
    <div
      class="relative overflow-hidden rounded-2xl border border-gray-100 bg-white p-5 shadow-sm transition hover:shadow-md dark:border-dark-800 dark:bg-dark-900/90"
    >
      <div class="flex items-center justify-between">
        <span
          class="text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-dark-400"
        >
          总请求数 (Total Requests)
        </span>
        <div
          class="flex h-8 w-8 items-center justify-center rounded-xl bg-sky-50 text-sky-600 dark:bg-sky-950/40 dark:text-sky-400"
        >
          <svg
            class="h-4 w-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M13 10V3L4 14h7v7l9-11h-7z"
            />
          </svg>
        </div>
      </div>

      <div class="mt-3 flex items-baseline gap-2">
        <span
          v-if="loading"
          class="h-8 w-24 animate-pulse rounded bg-gray-200 dark:bg-dark-700"
        />
        <span
          v-else
          class="text-2xl font-bold tracking-tight text-gray-900 dark:text-white"
        >
          {{ (summary?.total_requests ?? 0).toLocaleString() }}
        </span>
        <span class="text-xs text-gray-400 dark:text-dark-500">次</span>
      </div>

      <div class="mt-2 flex items-center gap-2 text-xs">
        <span
          class="inline-flex items-center rounded-md px-1.5 py-0.5 text-[11px] font-medium"
          :class="
            isErrorRateWarning
              ? 'bg-rose-50 text-rose-700 dark:bg-rose-950/50 dark:text-rose-300'
              : 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300'
          "
        >
          异常率 {{ errorRatePercent }}%
        </span>
        <span class="text-gray-400 dark:text-dark-500">
          ({{ (summary?.total_errors ?? 0).toLocaleString() }} 失败)
        </span>
      </div>
    </div>

    <!-- 卡片 2：P90 延迟分位数 -->
    <div
      class="relative overflow-hidden rounded-2xl border border-gray-100 bg-white p-5 shadow-sm transition hover:shadow-md dark:border-dark-800 dark:bg-dark-900/90"
    >
      <div class="flex items-center justify-between">
        <span
          class="text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-dark-400"
        >
          P90 响应耗时 (P90 Latency)
        </span>
        <div
          class="flex h-8 w-8 items-center justify-center rounded-xl bg-amber-50 text-amber-600 dark:bg-amber-950/40 dark:text-amber-400"
        >
          <svg
            class="h-4 w-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        </div>
      </div>

      <div class="mt-3 flex items-baseline gap-2">
        <span
          v-if="loading"
          class="h-8 w-24 animate-pulse rounded bg-gray-200 dark:bg-dark-700"
        />
        <span
          v-else
          class="text-2xl font-bold tracking-tight text-gray-900 dark:text-white"
        >
          {{
            summary?.p90_latency_ms != null
              ? summary.p90_latency_ms.toFixed(0)
              : "--"
          }}
        </span>
        <span class="text-xs text-gray-400 dark:text-dark-500">ms</span>
      </div>

      <div
        class="mt-2 flex items-center gap-2 text-xs text-gray-500 dark:text-dark-400"
      >
        <span>均值 / 次:</span>
        <span class="font-medium text-gray-700 dark:text-dark-200">
          {{
            summary?.avg_tokens_per_request != null
              ? summary.avg_tokens_per_request.toFixed(0) + " T/Req"
              : "--"
          }}
        </span>
      </div>
    </div>

    <!-- 卡片 3：Token 吞吐与缓存命中率 -->
    <div
      class="relative overflow-hidden rounded-2xl border border-gray-100 bg-white p-5 shadow-sm transition hover:shadow-md dark:border-dark-800 dark:bg-dark-900/90"
    >
      <div class="flex items-center justify-between">
        <span
          class="text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-dark-400"
        >
          Token 吞吐与缓存利用
        </span>
        <div
          class="flex h-8 w-8 items-center justify-center rounded-xl bg-violet-50 text-violet-600 dark:bg-violet-950/40 dark:text-violet-400"
        >
          <svg
            class="h-4 w-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
            />
          </svg>
        </div>
      </div>

      <div class="mt-3 flex items-baseline gap-2">
        <span
          v-if="loading"
          class="h-8 w-24 animate-pulse rounded bg-gray-200 dark:bg-dark-700"
        />
        <span
          v-else
          class="text-2xl font-bold tracking-tight text-gray-900 dark:text-white"
        >
          {{ formattedTotalTokens }}
        </span>
        <span class="text-xs text-gray-400 dark:text-dark-500">Tokens</span>
      </div>

      <div class="mt-2 flex items-center gap-2 text-xs">
        <span
          v-if="cacheHitRatioPercent"
          class="inline-flex items-center rounded-md bg-emerald-50 px-1.5 py-0.5 text-[11px] font-medium text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300"
        >
          Prompt Caching 命中: {{ cacheHitRatioPercent }}%
        </span>
        <span v-else class="text-gray-400 dark:text-dark-500">
          缓存读取:
          {{ (summary?.total_cache_read_tokens ?? 0).toLocaleString() }}
        </span>
      </div>
    </div>

    <!-- 卡片 4：网关总成本 -->
    <div
      class="relative overflow-hidden rounded-2xl border border-gray-100 bg-white p-5 shadow-sm transition hover:shadow-md dark:border-dark-800 dark:bg-dark-900/90"
    >
      <div class="flex items-center justify-between">
        <span
          class="text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-dark-400"
        >
          预估总成本 (Estimated Cost)
        </span>
        <div
          class="flex h-8 w-8 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-400"
        >
          <svg
            class="h-4 w-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        </div>
      </div>

      <div class="mt-3 flex items-baseline gap-2">
        <span
          v-if="loading"
          class="h-8 w-24 animate-pulse rounded bg-gray-200 dark:bg-dark-700"
        />
        <span
          v-else
          class="text-2xl font-bold tracking-tight text-emerald-600 dark:text-emerald-400"
        >
          {{ formattedCost }}
        </span>
        <span class="text-xs text-gray-400 dark:text-dark-500">USD</span>
      </div>

      <div class="mt-2 text-xs text-gray-500 dark:text-dark-400">
        输入 / 输出细分核算
      </div>
    </div>
  </div>
</template>

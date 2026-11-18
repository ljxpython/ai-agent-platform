<script setup lang="ts">
import { ref, computed } from "vue";
import { useGatewaySeries } from "../composables/useGatewaySeries";
import type { GatewaySeriesQueryParams, GatewayMetricPoint } from "../types";
import GatewayFilterToolbar, {
  type TimeRangePreset,
} from "./GatewayFilterToolbar.vue";
import GatewaySummaryCards from "./GatewaySummaryCards.vue";
import GatewayRequestsChart from "./charts/GatewayRequestsChart.vue";
import GatewayLatencyChart from "./charts/GatewayLatencyChart.vue";
import GatewayTokenUsageChart from "./charts/GatewayTokenUsageChart.vue";
import GatewayTokenStatsChart from "./charts/GatewayTokenStatsChart.vue";
import GatewayCostChart from "./charts/GatewayCostChart.vue";

interface Props {
  scope: {
    kind: "platform" | "project";
    projectId?: string;
  };
}

const props = defineProps<Props>();

const emit = defineEmits<{
  (
    e: "drilldown-to-logs",
    payload: { from: string; to: string; point: GatewayMetricPoint },
  ): void;
}>();

// 状态管理
const preset = ref<TimeRangePreset>("24h");
const bucketSeconds = ref<number>(300);
const statusFilter = ref<"all" | "ok" | "error">("all");
const refreshInterval = ref<number>(0);

// 根据 preset 计算 from 与 to（UTC ISO 格式）
function calculateTimeWindow(p: TimeRangePreset): { from: string; to: string } {
  const now = new Date();
  const end = now.toISOString();
  let startMs = now.getTime();

  switch (p) {
    case "1h":
      startMs -= 60 * 60 * 1000;
      break;
    case "6h":
      startMs -= 6 * 60 * 60 * 1000;
      break;
    case "24h":
      startMs -= 24 * 60 * 60 * 1000;
      break;
    case "7d":
      startMs -= 7 * 24 * 60 * 60 * 1000;
      break;
    case "30d":
      startMs -= 30 * 24 * 60 * 60 * 1000;
      break;
  }
  const from = new Date(startMs).toISOString();
  return { from, to: end };
}

const filters = computed<GatewaySeriesQueryParams>(() => {
  const { from, to } = calculateTimeWindow(preset.value);
  return {
    from,
    to,
    timezone: "Asia/Shanghai",
    bucket_seconds: bucketSeconds.value || 300,
    status: statusFilter.value,
  };
});

const { data, loading, isRefreshing, error, refresh } = useGatewaySeries({
  scope: computed(() => props.scope),
  filters,
  refreshIntervalMs: refreshInterval,
});

// 处理下钻到明细日志
function handleDrilldown(point: GatewayMetricPoint) {
  // 根据点的时间戳与当前 bucket 计算起止毫秒时间范围
  const bSec = bucketSeconds.value || 300;
  const startMs = point.timestamp_ms;
  const endMs = point.timestamp_ms + bSec * 1000;
  emit("drilldown-to-logs", {
    from: new Date(startMs).toISOString(),
    to: new Date(endMs).toISOString(),
    point,
  });
}
</script>

<template>
  <div class="space-y-6">
    <!-- 顶栏过滤控制栏 -->
    <GatewayFilterToolbar
      v-model:preset="preset"
      v-model:bucket-seconds="bucketSeconds"
      v-model:status="statusFilter"
      v-model:refresh-interval="refreshInterval"
      :loading="loading || isRefreshing"
      @refresh="refresh"
    />

    <!-- 错误横幅提示 -->
    <div
      v-if="error"
      class="flex items-center justify-between rounded-2xl border border-rose-200 bg-rose-50/70 p-4 text-xs text-rose-800 dark:border-rose-900/60 dark:bg-rose-950/20 dark:text-rose-300"
    >
      <div class="flex items-center gap-2">
        <svg
          class="h-4 w-4 shrink-0 text-rose-500"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
        <span>数据拉取失败：{{ error.message }}</span>
      </div>
      <button
        type="button"
        class="font-medium underline hover:text-rose-900 dark:hover:text-rose-100"
        @click="refresh"
      >
        重试
      </button>
    </div>

    <!-- 4 联指标摘要卡 -->
    <GatewaySummaryCards :summary="data?.summary" :loading="loading && !data" />

    <!-- 全宽图表 1：请求吞吐趋势 -->
    <GatewayRequestsChart
      :points="data?.series || []"
      :loading="loading && !data"
      @drilldown="handleDrilldown"
    />

    <!-- 三列并排：延迟分位数、Token 吞吐与单请求均值 -->
    <div class="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
      <!-- 图表 2：延迟分位数与异常 -->
      <GatewayLatencyChart
        :points="data?.series || []"
        :loading="loading && !data"
        @drilldown="handleDrilldown"
      />

      <!-- 图表 3：Token 吞吐与缓存 -->
      <GatewayTokenUsageChart
        :points="data?.series || []"
        :loading="loading && !data"
        @drilldown="handleDrilldown"
      />

      <!-- 图表 4：Tokens per Request 均值 -->
      <GatewayTokenStatsChart
        :points="data?.series || []"
        :loading="loading && !data"
        @drilldown="handleDrilldown"
      />
    </div>

    <!-- 全宽复合图表 5：成本走势与模型用量分布 (2:1 黄金比例) -->
    <GatewayCostChart
      :points="data?.series || []"
      :breakdown="data?.breakdown || []"
      :loading="loading && !data"
      @drilldown="handleDrilldown"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type {
  GatewayMetricPoint,
  GatewayModelBreakdownItem,
} from "../../types";
import BaseGatewayChart from "./BaseGatewayChart.vue";
import * as echarts from "echarts/core";

interface Props {
  points: GatewayMetricPoint[];
  breakdown?: GatewayModelBreakdownItem[];
  loading?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  points: () => [],
  breakdown: () => [],
  loading: false,
});

const emit = defineEmits<{
  (e: "drilldown", point: GatewayMetricPoint): void;
}>();

const isEmpty = computed(() => !props.loading && props.points.length === 0);

const chartOptions = computed<echarts.EChartsCoreOption>(() => {
  const labels = props.points.map((p) => p.time_label);
  const costValues = props.points.map((p) => parseFloat(p.cost_usd || "0"));

  return {
    tooltip: {
      trigger: "axis",
      formatter: (params: any) => {
        if (!Array.isArray(params) || params.length === 0) return "";
        const dataIndex = params[0].dataIndex;
        const point = props.points[dataIndex];
        if (!point) return "";

        return `
          <div class="space-y-1.5 font-sans">
            <div class="text-[11px] font-semibold text-gray-500 dark:text-dark-400">${point.time_label}</div>
            <div class="flex items-center justify-between gap-4 text-xs">
              <span class="flex items-center gap-1.5 text-gray-700 dark:text-dark-200">
                <span class="inline-block h-2 w-2 rounded-full bg-emerald-500"></span>
                估算成本:
              </span>
              <span class="font-semibold text-emerald-600 dark:text-emerald-400">
                $${parseFloat(point.cost_usd || "0").toFixed(6)}
              </span>
            </div>
            <div class="flex items-center justify-between gap-4 text-[11px] text-gray-500 dark:text-dark-400">
              <span>当期请求数:</span>
              <span>${point.requests.toLocaleString()}</span>
            </div>
            <div class="border-t border-gray-100 pt-1.5 text-[10px] text-primary-500 dark:border-dark-700">
              👉 点击图表穿透至此区间 Logs
            </div>
          </div>
        `;
      },
    },
    grid: {
      top: 24,
      right: 16,
      bottom: 20,
      left: 48,
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: labels,
      boundaryGap: false,
      axisLine: { lineStyle: { color: "#cbd5e1" } },
      axisLabel: { color: "#64748b", fontSize: 11, hideOverlap: true },
    },
    yAxis: {
      type: "value",
      name: "成本 (USD)",
      nameTextStyle: { color: "#64748b", fontSize: 11, padding: [0, 0, 0, 16] },
      splitLine: { lineStyle: { color: "#f1f5f9", type: "dashed" } },
      axisLabel: {
        color: "#64748b",
        fontSize: 11,
        formatter: (val: number) => `$${val.toFixed(4)}`,
      },
    },
    series: [
      {
        name: "Cost USD",
        type: "line",
        smooth: true,
        showSymbol: false,
        data: costValues,
        itemStyle: { color: "#059669" },
        lineStyle: { width: 2.2, color: "#059669" },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "rgba(5, 150, 105, 0.28)" },
            { offset: 1, color: "rgba(5, 150, 105, 0.02)" },
          ]),
        },
      },
    ],
  };
});

function handleDrilldown(index: number) {
  const target = props.points[index];
  if (target) {
    emit("drilldown", target);
  }
}
</script>

<template>
  <div class="grid grid-cols-1 gap-5 lg:grid-cols-3">
    <!-- 成本走势图 -->
    <div class="lg:col-span-2">
      <BaseGatewayChart
        title="网关预估成本走势 (Gateway Estimated Cost)"
        subtitle="监控模型调用消费与费用时序积累"
        :options="chartOptions"
        :loading="loading"
        :empty="isEmpty"
        height="260px"
        @drilldown="handleDrilldown"
      />
    </div>

    <!-- 模型消耗排行 Breakdown -->
    <div
      class="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm dark:border-dark-800 dark:bg-dark-900/90"
    >
      <div class="mb-3 flex items-center justify-between">
        <h4 class="text-sm font-semibold text-gray-900 dark:text-white">
          模型用量分布 (Breakdown)
        </h4>
        <span class="text-xs text-gray-400 dark:text-dark-500">TOP 10</span>
      </div>

      <div v-if="loading" class="flex h-[200px] items-center justify-center">
        <div
          class="h-5 w-5 animate-spin rounded-full border-2 border-primary-500 border-t-transparent"
        />
      </div>

      <div
        v-else-if="!breakdown || breakdown.length === 0"
        class="flex h-[200px] flex-col items-center justify-center text-center"
      >
        <span class="text-xs text-gray-400 dark:text-dark-500"
          >暂无模型调用分布</span
        >
      </div>

      <div v-else class="max-h-[220px] space-y-3 overflow-y-auto pr-1">
        <div
          v-for="item in breakdown"
          :key="item.key"
          class="flex items-center justify-between rounded-xl border border-gray-50 bg-gray-50/50 p-2.5 transition hover:border-gray-200 dark:border-dark-800 dark:bg-dark-800/40"
        >
          <div class="min-w-0 flex-1 pr-3">
            <div
              class="truncate text-xs font-semibold text-gray-900 dark:text-gray-100"
              :title="item.key"
            >
              {{ item.key }}
            </div>
            <div
              class="mt-0.5 flex items-center gap-2 text-[11px] text-gray-500 dark:text-dark-400"
            >
              <span>{{ item.requests.toLocaleString() }} 次请求</span>
              <span>·</span>
              <span>{{ item.total_tokens.toLocaleString() }} Tokens</span>
            </div>
          </div>
          <div class="text-right">
            <span
              class="font-mono text-xs font-semibold text-emerald-600 dark:text-emerald-400"
            >
              ${{ parseFloat(item.cost_usd || "0").toFixed(4) }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

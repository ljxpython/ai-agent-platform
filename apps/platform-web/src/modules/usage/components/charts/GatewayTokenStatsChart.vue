<script setup lang="ts">
import { computed } from "vue";
import type { GatewayMetricPoint } from "../../types";
import BaseGatewayChart from "./BaseGatewayChart.vue";
import * as echarts from "echarts/core";

interface Props {
  points: GatewayMetricPoint[];
  loading?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  points: () => [],
  loading: false,
});

const emit = defineEmits<{
  (e: "drilldown", point: GatewayMetricPoint): void;
}>();

const isEmpty = computed(() => !props.loading && props.points.length === 0);

const chartOptions = computed<echarts.EChartsCoreOption>(() => {
  const labels = props.points.map((p) => p.time_label);
  const stats = props.points.map((p) => p.tokens_per_request ?? null);

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
                <span class="inline-block h-2 w-2 rounded-full bg-indigo-500"></span>
                单请求均值 (Tokens/Req):
              </span>
              <span class="font-semibold text-gray-900 dark:text-white">
                ${point.tokens_per_request != null ? point.tokens_per_request.toFixed(1) : "--"}
              </span>
            </div>
            <div class="flex items-center justify-between gap-4 text-[11px] text-gray-500 dark:text-dark-400">
              <span>当期总 Tokens:</span>
              <span>${point.total_tokens.toLocaleString()}</span>
            </div>
            <div class="flex items-center justify-between gap-4 text-[11px] text-gray-500 dark:text-dark-400">
              <span>当期总请求数:</span>
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
      name: "Tokens/Req",
      nameTextStyle: { color: "#64748b", fontSize: 11, padding: [0, 0, 0, 16] },
      splitLine: { lineStyle: { color: "#f1f5f9", type: "dashed" } },
      axisLabel: { color: "#64748b", fontSize: 11 },
    },
    series: [
      {
        name: "Tokens per Request",
        type: "line",
        smooth: true,
        showSymbol: false,
        data: stats,
        itemStyle: { color: "#6366f1" },
        lineStyle: { width: 2, color: "#6366f1" },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "rgba(99, 102, 241, 0.25)" },
            { offset: 1, color: "rgba(99, 102, 241, 0.02)" },
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
  <BaseGatewayChart
    title="单请求 Token 均值 (Tokens per Request)"
    subtitle="监控每笔请求平均承载上下文及输出长度"
    :options="chartOptions"
    :loading="loading"
    :empty="isEmpty"
    height="260px"
    @drilldown="handleDrilldown"
  />
</template>

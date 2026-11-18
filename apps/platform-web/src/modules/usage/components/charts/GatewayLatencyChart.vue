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
  const p50 = props.points.map((p) => p.latency_p50_ms ?? null);
  const p90 = props.points.map((p) => p.latency_p90_ms ?? null);
  const p99 = props.points.map((p) => p.latency_p99_ms ?? null);
  const errors = props.points.map((p) => p.errors);

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
                P50 延迟:
              </span>
              <span class="font-semibold text-gray-900 dark:text-white">${point.latency_p50_ms != null ? point.latency_p50_ms.toFixed(1) + " ms" : "--"}</span>
            </div>
            <div class="flex items-center justify-between gap-4 text-xs">
              <span class="flex items-center gap-1.5 text-gray-700 dark:text-dark-200">
                <span class="inline-block h-2 w-2 rounded-full bg-amber-500"></span>
                P90 延迟:
              </span>
              <span class="font-semibold text-gray-900 dark:text-white">${point.latency_p90_ms != null ? point.latency_p90_ms.toFixed(1) + " ms" : "--"}</span>
            </div>
            <div class="flex items-center justify-between gap-4 text-xs">
              <span class="flex items-center gap-1.5 text-gray-700 dark:text-dark-200">
                <span class="inline-block h-2 w-2 rounded-full bg-rose-500"></span>
                P99 延迟:
              </span>
              <span class="font-semibold text-gray-900 dark:text-white">${point.latency_p99_ms != null ? point.latency_p99_ms.toFixed(1) + " ms" : "--"}</span>
            </div>
            <div class="flex items-center justify-between gap-4 text-xs">
              <span class="flex items-center gap-1.5 text-gray-700 dark:text-dark-200">
                <span class="inline-block h-2 w-2 rounded-full bg-rose-400"></span>
                错误数:
              </span>
              <span class="${point.errors > 0 ? "text-rose-500 font-semibold" : "text-gray-900 dark:text-white"}">${point.errors} 次</span>
            </div>
            <div class="border-t border-gray-100 pt-1.5 text-[10px] text-primary-500 dark:border-dark-700">
              👉 点击图表穿透至此区间 Logs
            </div>
          </div>
        `;
      },
    },
    legend: {
      top: 0,
      right: 0,
      textStyle: { fontSize: 11, color: "#64748b" },
      data: ["P50 延迟", "P90 延迟", "P99 延迟", "异常数"],
    },
    grid: {
      top: 36,
      right: 48,
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
    yAxis: [
      {
        type: "value",
        name: "延迟 (ms)",
        nameTextStyle: { color: "#64748b", fontSize: 11 },
        splitLine: { lineStyle: { color: "#f1f5f9", type: "dashed" } },
        axisLabel: { color: "#64748b", fontSize: 11 },
      },
      {
        type: "value",
        name: "异常数",
        nameTextStyle: { color: "#64748b", fontSize: 11 },
        minInterval: 1,
        splitLine: { show: false },
        axisLabel: { color: "#64748b", fontSize: 11 },
      },
    ],
    series: [
      {
        name: "P50 延迟",
        type: "line",
        smooth: true,
        showSymbol: false,
        data: p50,
        itemStyle: { color: "#10b981" },
        lineStyle: { width: 2, color: "#10b981" },
      },
      {
        name: "P90 延迟",
        type: "line",
        smooth: true,
        showSymbol: false,
        data: p90,
        itemStyle: { color: "#f59e0b" },
        lineStyle: { width: 2, color: "#f59e0b" },
      },
      {
        name: "P99 延迟",
        type: "line",
        smooth: true,
        showSymbol: false,
        data: p99,
        itemStyle: { color: "#f43f5e" },
        lineStyle: { width: 1.5, type: "dashed", color: "#f43f5e" },
      },
      {
        name: "异常数",
        type: "bar",
        yAxisIndex: 1,
        barMaxWidth: 16,
        data: errors,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "rgba(244, 63, 94, 0.7)" },
            { offset: 1, color: "rgba(244, 63, 94, 0.15)" },
          ]),
          borderRadius: [4, 4, 0, 0],
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
    title="网关响应延迟与异常 (Latency & Errors)"
    subtitle="监控 P50/P90/P99 耗时分位数与异常错误分布"
    :options="chartOptions"
    :loading="loading"
    :empty="isEmpty"
    height="260px"
    @drilldown="handleDrilldown"
  />
</template>

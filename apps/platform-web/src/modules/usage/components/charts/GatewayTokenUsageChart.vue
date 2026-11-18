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
  const input = props.points.map((p) => p.input_tokens);
  const output = props.points.map((p) => p.output_tokens);
  const cacheRead = props.points.map((p) => p.cache_read_tokens);
  const cacheCreation = props.points.map((p) => p.cache_creation_tokens);

  return {
    tooltip: {
      trigger: "axis",
      formatter: (params: any) => {
        if (!Array.isArray(params) || params.length === 0) return "";
        const dataIndex = params[0].dataIndex;
        const point = props.points[dataIndex];
        if (!point) return "";

        const hitRatio =
          point.input_tokens > 0
            ? ((point.cache_read_tokens / point.input_tokens) * 100).toFixed(1)
            : "0.0";

        return `
          <div class="space-y-1.5 font-sans min-w-[200px]">
            <div class="flex items-center justify-between text-[11px] font-semibold text-gray-500 dark:text-dark-400">
              <span>${point.time_label}</span>
              <span class="text-emerald-500 font-medium">缓存命中: ${hitRatio}%</span>
            </div>
            <div class="flex items-center justify-between gap-4 text-xs">
              <span class="flex items-center gap-1.5 text-gray-700 dark:text-dark-200">
                <span class="inline-block h-2 w-2 rounded-full bg-violet-500"></span>
                输入 Tokens:
              </span>
              <span class="font-semibold text-gray-900 dark:text-white">${point.input_tokens.toLocaleString()}</span>
            </div>
            <div class="flex items-center justify-between gap-4 text-xs">
              <span class="flex items-center gap-1.5 text-gray-700 dark:text-dark-200">
                <span class="inline-block h-2 w-2 rounded-full bg-sky-500"></span>
                输出 Tokens:
              </span>
              <span class="font-semibold text-gray-900 dark:text-white">${point.output_tokens.toLocaleString()}</span>
            </div>
            <div class="flex items-center justify-between gap-4 text-xs">
              <span class="flex items-center gap-1.5 text-gray-700 dark:text-dark-200">
                <span class="inline-block h-2 w-2 rounded-full bg-emerald-500"></span>
                缓存读取 (命中):
              </span>
              <span class="font-semibold text-emerald-600 dark:text-emerald-400">${point.cache_read_tokens.toLocaleString()}</span>
            </div>
            <div class="flex items-center justify-between gap-4 text-xs">
              <span class="flex items-center gap-1.5 text-gray-700 dark:text-dark-200">
                <span class="inline-block h-2 w-2 rounded-full bg-amber-500"></span>
                缓存写入:
              </span>
              <span class="font-semibold text-amber-600 dark:text-amber-400">${point.cache_creation_tokens.toLocaleString()}</span>
            </div>
            <div class="border-t border-gray-100 pt-1.5 flex items-center justify-between text-xs font-semibold text-gray-900 dark:border-dark-700 dark:text-white">
              <span>总 Token:</span>
              <span>${point.total_tokens.toLocaleString()}</span>
            </div>
            <div class="text-[10px] text-primary-500">
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
      data: ["输入 Tokens", "输出 Tokens", "缓存读取 (命中)", "缓存写入"],
    },
    grid: {
      top: 36,
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
      name: "Tokens",
      nameTextStyle: { color: "#64748b", fontSize: 11 },
      splitLine: { lineStyle: { color: "#f1f5f9", type: "dashed" } },
      axisLabel: {
        color: "#64748b",
        fontSize: 11,
        formatter: (val: number) => {
          if (val >= 1000000) return `${(val / 1000000).toFixed(1)}M`;
          if (val >= 1000) return `${(val / 1000).toFixed(0)}k`;
          return `${val}`;
        },
      },
    },
    series: [
      {
        name: "输入 Tokens",
        type: "line",
        stack: "Total",
        smooth: true,
        showSymbol: false,
        areaStyle: { opacity: 0.6 },
        itemStyle: { color: "#8b5cf6" },
        lineStyle: { width: 1.5, color: "#8b5cf6" },
        data: input,
      },
      {
        name: "输出 Tokens",
        type: "line",
        stack: "Total",
        smooth: true,
        showSymbol: false,
        areaStyle: { opacity: 0.6 },
        itemStyle: { color: "#0ea5e9" },
        lineStyle: { width: 1.5, color: "#0ea5e9" },
        data: output,
      },
      {
        name: "缓存读取 (命中)",
        type: "line",
        stack: "Total",
        smooth: true,
        showSymbol: false,
        areaStyle: { opacity: 0.7 },
        itemStyle: { color: "#10b981" },
        lineStyle: { width: 1.5, color: "#10b981" },
        data: cacheRead,
      },
      {
        name: "缓存写入",
        type: "line",
        stack: "Total",
        smooth: true,
        showSymbol: false,
        areaStyle: { opacity: 0.5 },
        itemStyle: { color: "#f59e0b" },
        lineStyle: { width: 1.5, color: "#f59e0b" },
        data: cacheCreation,
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
    title="Token 吞吐与缓存分布 (Token Usage & Prompt Caching)"
    subtitle="监控输入、输出及 Prompt Caching 命中节省情况"
    :options="chartOptions"
    :loading="loading"
    :empty="isEmpty"
    height="260px"
    @drilldown="handleDrilldown"
  />
</template>

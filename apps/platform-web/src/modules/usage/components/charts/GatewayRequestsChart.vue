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
  const requestValues = props.points.map((p) => p.requests);

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
                <span class="inline-block h-2 w-2 rounded-full bg-sky-500"></span>
                总请求数:
              </span>
              <span class="font-semibold text-gray-900 dark:text-white">${point.requests.toLocaleString()} 次</span>
            </div>
            <div class="flex items-center justify-between gap-4 text-[11px] text-gray-500 dark:text-dark-400">
              <span>异常请求:</span>
              <span class="${point.errors > 0 ? "text-rose-500 font-semibold" : ""}">${point.errors} 次</span>
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
      name: "请求数",
      nameTextStyle: { color: "#64748b", fontSize: 11, padding: [0, 0, 0, 16] },
      splitLine: { lineStyle: { color: "#f1f5f9", type: "dashed" } },
      axisLabel: { color: "#64748b", fontSize: 11 },
    },
    series: [
      {
        name: "Requests",
        type: "line",
        smooth: true,
        showSymbol: false,
        data: requestValues,
        itemStyle: { color: "#0284c7" },
        lineStyle: { width: 2.5, color: "#0284c7" },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "rgba(2, 132, 199, 0.28)" },
            { offset: 1, color: "rgba(2, 132, 199, 0.02)" },
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
    title="网关请求吞吐趋势 (Requests Throughput)"
    subtitle="监控网关总调用流量与请求高峰波动"
    :options="chartOptions"
    :loading="loading"
    :empty="isEmpty"
    height="260px"
    @drilldown="handleDrilldown"
  >
    <template #extra>
      <span class="text-xs font-medium text-gray-500 dark:text-dark-400">
        点数: {{ points.length }}
      </span>
    </template>
  </BaseGatewayChart>
</template>

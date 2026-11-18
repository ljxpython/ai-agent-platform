<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from "vue";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { LineChart, BarChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  DataZoomComponent,
} from "echarts/components";
import { useThemeStore } from "@/stores/theme";
import { useResizeObserver } from "@vueuse/core";

echarts.use([
  CanvasRenderer,
  LineChart,
  BarChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  DataZoomComponent,
]);

interface Props {
  title?: string;
  subtitle?: string;
  options: echarts.EChartsCoreOption;
  loading?: boolean;
  empty?: boolean;
  height?: string;
  showDrilldownHint?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  title: "",
  subtitle: "",
  loading: false,
  empty: false,
  height: "280px",
  showDrilldownHint: true,
});

const emit = defineEmits<{
  (e: "point-click", params: any): void;
  (e: "drilldown", pointIndex: number): void;
}>();

const chartRef = ref<HTMLDivElement | null>(null);
let chartInstance: echarts.ECharts | null = null;
const themeStore = useThemeStore();

const isDark = computed(() => themeStore.mode === "dark");

function initChart() {
  if (!chartRef.value) return;
  if (chartInstance) {
    chartInstance.dispose();
    chartInstance = null;
  }

  chartInstance = echarts.init(
    chartRef.value,
    isDark.value ? "dark" : undefined,
    {
      renderer: "canvas",
    },
  );

  chartInstance.on("click", (params) => {
    emit("point-click", params);
    if (typeof params.dataIndex === "number") {
      emit("drilldown", params.dataIndex);
    }
  });

  updateChart();
}

function updateChart() {
  if (!chartInstance) return;
  if (props.loading || props.empty) {
    chartInstance.clear();
    return;
  }

  // 深浅主题通用基础融合
  const themeMergeOption: echarts.EChartsCoreOption = {
    backgroundColor: "transparent",
    textStyle: {
      fontFamily:
        'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      color: isDark.value ? "#94a3b8" : "#64748b",
    },
    grid: {
      top: 36,
      right: 16,
      bottom: 24,
      left: 48,
      containLabel: true,
      borderColor: isDark.value ? "#1e293b" : "#e2e8f0",
    },
    tooltip: {
      backgroundColor: isDark.value
        ? "rgba(15, 23, 42, 0.92)"
        : "rgba(255, 255, 255, 0.95)",
      borderColor: isDark.value ? "#334155" : "#e2e8f0",
      borderWidth: 1,
      padding: [10, 14],
      textStyle: {
        color: isDark.value ? "#f1f5f9" : "#0f172a",
        fontSize: 12,
      },
      extraCssText:
        "border-radius: 12px; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1); backdrop-filter: blur(8px);",
    },
  };

  chartInstance.setOption(
    {
      ...themeMergeOption,
      ...props.options,
    },
    { notMerge: true },
  );
}

watch(
  () => props.options,
  () => {
    nextTick(() => {
      updateChart();
    });
  },
  { deep: true },
);

watch(
  () => isDark.value,
  () => {
    nextTick(() => {
      initChart();
    });
  },
);

watch(
  () => [props.loading, props.empty],
  () => {
    nextTick(() => {
      updateChart();
    });
  },
);

useResizeObserver(chartRef, () => {
  chartInstance?.resize();
});

onMounted(() => {
  nextTick(() => {
    initChart();
  });
});

onUnmounted(() => {
  if (chartInstance) {
    chartInstance.dispose();
    chartInstance = null;
  }
});
</script>

<template>
  <div
    class="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm transition-all duration-200 dark:border-dark-800 dark:bg-dark-900/90"
  >
    <div
      v-if="title || $slots.header || $slots.extra"
      class="mb-4 flex items-center justify-between"
    >
      <div>
        <div class="flex items-center gap-2">
          <h3 class="text-sm font-semibold text-gray-900 dark:text-white">
            <slot name="title">{{ title }}</slot>
          </h3>
          <span
            v-if="showDrilldownHint && !empty && !loading"
            class="hidden rounded bg-primary-50 px-1.5 py-0.5 text-[10px] font-medium text-primary-600 dark:bg-primary-950/40 dark:text-primary-400 sm:inline-block"
          >
            点击图表下钻 Logs
          </span>
        </div>
        <p
          v-if="subtitle"
          class="mt-0.5 text-xs text-gray-500 dark:text-dark-400"
        >
          {{ subtitle }}
        </p>
      </div>
      <div v-if="$slots.extra" class="flex items-center gap-2">
        <slot name="extra" />
      </div>
    </div>

    <div class="relative w-full" :style="{ minHeight: height }">
      <!-- 加载遮罩 -->
      <div
        v-if="loading"
        class="absolute inset-0 z-10 flex flex-col items-center justify-center bg-white/60 backdrop-blur-[2px] dark:bg-dark-900/60"
      >
        <div
          class="h-6 w-6 animate-spin rounded-full border-2 border-primary-500 border-t-transparent"
        />
        <span class="mt-2 text-xs text-gray-500 dark:text-dark-400"
          >加载时序数据中...</span
        >
      </div>

      <!-- 空状态 -->
      <div
        v-else-if="empty"
        class="absolute inset-0 flex flex-col items-center justify-center py-12 text-center"
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
              d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
            />
          </svg>
        </div>
        <p class="mt-3 text-xs font-medium text-gray-700 dark:text-dark-300">
          当前时间范围暂无网关指标
        </p>
        <p class="mt-1 text-[11px] text-gray-400 dark:text-dark-500">
          可尝试调整时间窗口或检查是否有客户端产生调用
        </p>
      </div>

      <!-- ECharts 挂载节点 -->
      <div ref="chartRef" class="w-full" :style="{ height }" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import * as echarts from "echarts";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseDialog from "@/components/base/BaseDialog.vue";
import BaseSelect from "@/components/base/BaseSelect.vue";
import StatusPill from "@/components/platform/StatusPill.vue";
import type { EvalRunItem } from "@/services/evaluation/studio";

const props = defineProps<{
  show: boolean;
  suiteName: string;
  runs: EvalRunItem[];
}>();

const emit = defineEmits<{
  close: [];
  compareTwo: [baselineId: string, candidateId: string];
}>();

type MetricGroup = "quality" | "latency" | "cost";

const metricGroup = ref<MetricGroup>("quality");
const graphFilter = ref("ALL");
const terminalOnly = ref(true);
const selectedSubMetrics = ref<string[]>([]);
const selectedPkIds = ref<string[]>([]);
const chartEl = ref<HTMLElement | null>(null);
let chart: echarts.ECharts | null = null;
let resizeObserver: ResizeObserver | null = null;

function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

const graphOptions = computed(() => {
  const unique = Array.from(
    new Set(props.runs.map((r) => r.target_graph_id).filter(Boolean)),
  );
  return [
    { label: "全部 Graph", value: "ALL" },
    ...unique.map((g) => ({ label: g, value: g })),
  ];
});

// 时间正序排列用于趋势演进分析
const filteredRuns = computed(() => {
  return [...props.runs]
    .filter((r) => {
      if (
        graphFilter.value !== "ALL" &&
        r.target_graph_id !== graphFilter.value
      ) {
        return false;
      }
      if (terminalOnly.value && !["completed", "failed"].includes(r.status)) {
        return false;
      }
      return true;
    })
    .sort((a, b) => (a.created_at ?? "").localeCompare(b.created_at ?? ""));
});

// 从历次运行的 summary_metrics.metrics_breakdown 提取出现过的所有 L1/L2 子指标名
const availableSubMetrics = computed(() => {
  const names = new Set<string>();
  for (const r of filteredRuns.value) {
    const bd = (r.summary_metrics as Record<string, any>)?.metrics_breakdown;
    if (bd && typeof bd === "object") {
      for (const k of Object.keys(bd)) {
        names.add(k);
      }
    }
  }
  return Array.from(names).sort();
});

watch(
  availableSubMetrics,
  (list) => {
    if (!selectedSubMetrics.value.length && list.length > 0) {
      selectedSubMetrics.value = list.slice(0, 3);
    } else {
      selectedSubMetrics.value = selectedSubMetrics.value.filter((k) =>
        list.includes(k),
      );
    }
  },
  { immediate: true },
);

watch(
  () => props.show,
  (open) => {
    if (open) {
      selectedPkIds.value = [];
    }
  },
);

function toggleSubMetric(name: string) {
  if (selectedSubMetrics.value.includes(name)) {
    selectedSubMetrics.value = selectedSubMetrics.value.filter(
      (m) => m !== name,
    );
  } else if (selectedSubMetrics.value.length < 6) {
    selectedSubMetrics.value = [...selectedSubMetrics.value, name];
  }
}

function togglePkRun(runId: string) {
  if (selectedPkIds.value.includes(runId)) {
    selectedPkIds.value = selectedPkIds.value.filter((id) => id !== runId);
  } else if (selectedPkIds.value.length < 2) {
    selectedPkIds.value = [...selectedPkIds.value, runId];
  } else {
    selectedPkIds.value = [selectedPkIds.value[1], runId];
  }
}

function triggerPk() {
  if (selectedPkIds.value.length === 2) {
    emit("compareTwo", selectedPkIds.value[0], selectedPkIds.value[1]);
    return;
  }
  if (filteredRuns.value.length >= 2) {
    const n = filteredRuns.value.length;
    emit(
      "compareTwo",
      filteredRuns.value[n - 2].id,
      filteredRuns.value[n - 1].id,
    );
  }
}

function runLabel(r: EvalRunItem) {
  const ver = r.version_num ? `v${r.version_num}` : "";
  const model = r.target_model_name
    ? r.target_model_name.slice(0, 14)
    : r.target_graph_id;
  return `#${r.id.slice(0, 6)} ${ver ? `${ver} ` : ""}(${model})`;
}

function pct(v: unknown): number | null {
  const n = num(v);
  return n !== null ? Math.round(n * 1000) / 10 : null;
}

function subMetricScorePct(r: EvalRunItem, name: string): number | null {
  const bd = (r.summary_metrics as Record<string, any>)?.metrics_breakdown;
  const entry = bd?.[name];
  if (!entry || typeof entry !== "object") return null;
  const val = num(entry.avg_score ?? entry.pass_rate);
  return val !== null ? Math.round(val * 1000) / 10 : null;
}

function renderChart() {
  if (!chartEl.value || !props.show || filteredRuns.value.length === 0) return;
  const w = chartEl.value.clientWidth;
  const h = chartEl.value.clientHeight;
  if (w === 0 || h === 0) return;
  if (chart && (chart.isDisposed() || chart.getWidth() === 0)) {
    chart.dispose();
    chart = null;
  }
  if (!chart) {
    chart = echarts.init(chartEl.value);
  }

  const xLabels = filteredRuns.value.map(runLabel);
  const series: echarts.SeriesOption[] = [];
  let yAxis: echarts.YAXisComponentOption | echarts.YAXisComponentOption[] = {
    type: "value",
    name: "%",
    min: 0,
    max: 100,
  };

  if (metricGroup.value === "quality") {
    series.push(
      {
        name: "综合分 (%)",
        type: "line",
        smooth: true,
        data: filteredRuns.value.map((r) =>
          pct(
            (r.summary_metrics as any)?.overall_score ??
              (r.summary_metrics as any)?.tsr_pass_at_1,
          ),
        ),
        itemStyle: { color: "#4f46e5" },
      },
      {
        name: "TSR / Pass@1 (%)",
        type: "line",
        smooth: true,
        data: filteredRuns.value.map((r) =>
          pct((r.summary_metrics as any)?.tsr_pass_at_1),
        ),
        itemStyle: { color: "#10b981" },
      },
      {
        name: "L1 规则通过率 (%)",
        type: "line",
        smooth: true,
        data: filteredRuns.value.map((r) =>
          pct((r.summary_metrics as any)?.l1_pass_rate),
        ),
        itemStyle: { color: "#f59e0b" },
      },
    );
    const palette = [
      "#06b6d4",
      "#ec4899",
      "#8b5cf6",
      "#14b8a6",
      "#f97316",
      "#64748b",
    ];
    selectedSubMetrics.value.forEach((mName, idx) => {
      series.push({
        name: `${mName} (%)`,
        type: "line",
        smooth: true,
        lineStyle: { type: "dashed" },
        data: filteredRuns.value.map((r) => subMetricScorePct(r, mName)),
        itemStyle: { color: palette[idx % palette.length] },
      });
    });
  } else if (metricGroup.value === "latency") {
    yAxis = { type: "value", name: "ms", min: 0 };
    series.push(
      {
        name: "TTFT P50 (ms)",
        type: "line",
        smooth: true,
        data: filteredRuns.value.map((r) =>
          num((r.summary_metrics as any)?.ttft_ms?.p50),
        ),
        itemStyle: { color: "#0ea5e9" },
      },
      {
        name: "TTFT P95 (ms)",
        type: "line",
        smooth: true,
        data: filteredRuns.value.map((r) =>
          num((r.summary_metrics as any)?.ttft_ms?.p95),
        ),
        itemStyle: { color: "#6366f1" },
      },
      {
        name: "Agent 单题均耗 (ms)",
        type: "line",
        smooth: true,
        data: filteredRuns.value.map(
          (r) =>
            num(
              (r.summary_metrics as any)?.timing_breakdown?.agent_duration_ms
                ?.avg,
            ) ?? num((r.summary_metrics as any)?.duration_ms?.avg),
        ),
        itemStyle: { color: "#f59e0b" },
      },
      {
        name: "L2 裁判均耗 (ms)",
        type: "line",
        smooth: true,
        data: filteredRuns.value.map((r) =>
          num((r.summary_metrics as any)?.timing_breakdown?.judge_ms?.avg),
        ),
        itemStyle: { color: "#ec4899" },
      },
    );
  } else {
    yAxis = [
      { type: "value", name: "Tokens / 题数", min: 0 },
      { type: "value", name: "死循环率 %", min: 0, max: 100 },
    ];
    series.push(
      {
        name: "总 Token",
        type: "bar",
        yAxisIndex: 0,
        data: filteredRuns.value.map((r) =>
          num((r.summary_metrics as any)?.token_usage?.total_tokens),
        ),
        itemStyle: { color: "#6366f1" },
      },
      {
        name: "失败/异常题数",
        type: "bar",
        yAxisIndex: 0,
        data: filteredRuns.value.map((r) => {
          const bd = (r.summary_metrics as any)?.error_breakdown;
          if (!bd) return null;
          return (
            (bd.fail ?? 0) + (bd.runtime_error ?? 0) + (bd.eval_error ?? 0)
          );
        }),
        itemStyle: { color: "#f43f5e" },
      },
      {
        name: "死循环率 (%)",
        type: "line",
        yAxisIndex: 1,
        smooth: true,
        data: filteredRuns.value.map((r) =>
          pct((r.summary_metrics as any)?.loop_rate ?? 0),
        ),
        itemStyle: { color: "#f59e0b" },
      },
    );
  }

  chart.setOption(
    {
      tooltip: { trigger: "axis" },
      legend: { bottom: 0, type: "scroll" },
      grid: { left: 48, right: 48, top: 24, bottom: 48 },
      xAxis: { type: "category", data: xLabels, axisLabel: { fontSize: 10 } },
      yAxis,
      series,
    },
    true,
  );
  chart.resize();
}

function scheduleChartRender() {
  void nextTick().then(() => {
    requestAnimationFrame(() => {
      renderChart();
      setTimeout(renderChart, 200);
    });
  });
}

watch(
  () => [
    props.show,
    filteredRuns.value,
    metricGroup.value,
    selectedSubMetrics.value,
  ],
  ([open]) => {
    if (open) {
      scheduleChartRender();
    }
  },
  { deep: true, immediate: true },
);

watch(
  chartEl,
  (el) => {
    resizeObserver?.disconnect();
    resizeObserver = null;
    if (!el || typeof ResizeObserver === "undefined") return;
    resizeObserver = new ResizeObserver(() => {
      if (props.show) renderChart();
    });
    resizeObserver.observe(el);
  },
  { flush: "post" },
);

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  resizeObserver = null;
  chart?.dispose();
  chart = null;
});

interface MatrixMetricRow {
  key: string;
  label: string;
  higherBetter: boolean;
  format: "pct" | "ms" | "int" | "usd";
  values: Array<number | null>;
  bestValue: number | null;
}

const matrixRows = computed<MatrixMetricRow[]>(() => {
  const runsList = filteredRuns.value;
  if (!runsList.length) return [];

  const defs: Array<{
    key: string;
    label: string;
    higherBetter: boolean;
    format: MatrixMetricRow["format"];
    extract: (r: EvalRunItem) => number | null;
  }> = [
    {
      key: "overall_score",
      label: "综合质量分",
      higherBetter: true,
      format: "pct",
      extract: (r) =>
        num(
          (r.summary_metrics as any)?.overall_score ??
            (r.summary_metrics as any)?.tsr_pass_at_1,
        ),
    },
    {
      key: "tsr_pass_at_1",
      label: "任务达成率 TSR / Pass@1",
      higherBetter: true,
      format: "pct",
      extract: (r) => num((r.summary_metrics as any)?.tsr_pass_at_1),
    },
    {
      key: "l1_pass_rate",
      label: "L1 硬规则通过率",
      higherBetter: true,
      format: "pct",
      extract: (r) => num((r.summary_metrics as any)?.l1_pass_rate),
    },
    {
      key: "loop_rate",
      label: "死循环率",
      higherBetter: false,
      format: "pct",
      extract: (r) => num((r.summary_metrics as any)?.loop_rate),
    },
    ...availableSubMetrics.value.map((mName) => ({
      key: `sub:${mName}`,
      label: `子指标 · ${mName}`,
      higherBetter: true,
      format: "pct" as const,
      extract: (r: EvalRunItem) => {
        const entry = (r.summary_metrics as any)?.metrics_breakdown?.[mName];
        if (!entry || typeof entry !== "object") return null;
        return num(entry.avg_score ?? entry.pass_rate);
      },
    })),
    {
      key: "ttft_p50",
      label: "TTFT P50 首字延迟",
      higherBetter: false,
      format: "ms",
      extract: (r) => num((r.summary_metrics as any)?.ttft_ms?.p50),
    },
    {
      key: "ttft_p95",
      label: "TTFT P95 首字延迟",
      higherBetter: false,
      format: "ms",
      extract: (r) => num((r.summary_metrics as any)?.ttft_ms?.p95),
    },
    {
      key: "agent_avg_ms",
      label: "Agent 单题均耗",
      higherBetter: false,
      format: "ms",
      extract: (r) =>
        num(
          (r.summary_metrics as any)?.timing_breakdown?.agent_duration_ms?.avg,
        ) ?? num((r.summary_metrics as any)?.duration_ms?.avg),
    },
    {
      key: "total_tokens",
      label: "全量 Token",
      higherBetter: false,
      format: "int",
      extract: (r) =>
        num((r.summary_metrics as any)?.token_usage?.total_tokens),
    },
    {
      key: "total_cost_usd",
      label: "预估总费用",
      higherBetter: false,
      format: "usd",
      extract: (r) => num((r.summary_metrics as any)?.total_cost_usd),
    },
  ];

  return defs.map((def) => {
    const vals = runsList.map(def.extract);
    const valid = vals.filter((v): v is number => v !== null);
    const bestValue = valid.length
      ? def.higherBetter
        ? Math.max(...valid)
        : Math.min(...valid)
      : null;
    return {
      key: def.key,
      label: def.label,
      higherBetter: def.higherBetter,
      format: def.format,
      values: vals,
      bestValue,
    };
  });
});

function formatCell(
  val: number | null,
  fmt: MatrixMetricRow["format"],
): string {
  if (val === null) return "-";
  if (fmt === "pct") return `${Math.round(val * 1000) / 10}%`;
  if (fmt === "ms") return `${Math.round(val)} ms`;
  if (fmt === "usd") return `$${val.toFixed(5)}`;
  return `${Math.round(val)}`;
}

function deltaInfo(
  row: MatrixMetricRow,
  idx: number,
): { text: string; cls: string } | null {
  if (idx === 0) return null;
  const cur = row.values[idx];
  const prev = row.values[idx - 1];
  if (cur === null || prev === null) return null;
  const diff = cur - prev;
  if (Math.abs(diff) < 1e-6) return null;
  const good = row.higherBetter ? diff > 0 : diff < 0;
  let text = "";
  if (row.format === "pct") {
    const pts = Math.round(diff * 1000) / 10;
    text = `${pts > 0 ? "+" : ""}${pts}%`;
  } else if (row.format === "ms") {
    const ms = Math.round(diff);
    text = `${ms > 0 ? "+" : ""}${ms}ms`;
  } else if (row.format === "usd") {
    text = `${diff > 0 ? "+" : ""}$${diff.toFixed(4)}`;
  } else {
    const n = Math.round(diff);
    text = `${n > 0 ? "+" : ""}${n}`;
  }
  return {
    text,
    cls: good
      ? "text-emerald-600 dark:text-emerald-400"
      : "text-rose-600 dark:text-rose-400",
  };
}
</script>

<template>
  <BaseDialog
    :show="show"
    width="full"
    :title="`同评测集历史各指标对比与趋势 · ${suiteName}`"
    @close="emit('close')"
  >
    <div class="space-y-4 text-xs">
      <!-- 顶部筛选与维度控制 -->
      <div
        class="p-3 rounded-xl border border-gray-200 dark:border-dark-700 bg-gray-50/80 dark:bg-dark-800/60 flex flex-wrap items-center justify-between gap-3"
      >
        <div class="flex flex-wrap items-center gap-2">
          <div class="w-40">
            <BaseSelect
              v-model="graphFilter"
              :options="graphOptions"
              placeholder="Graph 筛选"
            />
          </div>
          <label
            class="inline-flex items-center gap-1.5 text-gray-600 dark:text-dark-300 cursor-pointer"
          >
            <input v-model="terminalOnly" type="checkbox" />
            <span>仅看终态场次 (completed/failed)</span>
          </label>
          <span class="text-gray-500 font-mono">
            共 {{ filteredRuns.length }} 场参与对比
          </span>
        </div>

        <div class="flex flex-wrap items-center gap-2">
          <div
            class="inline-flex rounded-lg border border-gray-200 dark:border-dark-700 bg-white dark:bg-dark-900 p-0.5"
          >
            <button
              type="button"
              class="px-2.5 py-1 rounded-md font-medium transition-colors"
              :class="
                metricGroup === 'quality'
                  ? 'bg-primary-600 text-white'
                  : 'text-gray-600 dark:text-dark-300 hover:bg-gray-100 dark:hover:bg-dark-800'
              "
              @click="metricGroup = 'quality'"
            >
              质量与子指标
            </button>
            <button
              type="button"
              class="px-2.5 py-1 rounded-md font-medium transition-colors"
              :class="
                metricGroup === 'latency'
                  ? 'bg-primary-600 text-white'
                  : 'text-gray-600 dark:text-dark-300 hover:bg-gray-100 dark:hover:bg-dark-800'
              "
              @click="metricGroup = 'latency'"
            >
              时延与吞吐
            </button>
            <button
              type="button"
              class="px-2.5 py-1 rounded-md font-medium transition-colors"
              :class="
                metricGroup === 'cost'
                  ? 'bg-primary-600 text-white'
                  : 'text-gray-600 dark:text-dark-300 hover:bg-gray-100 dark:hover:bg-dark-800'
              "
              @click="metricGroup = 'cost'"
            >
              成本与稳定性
            </button>
          </div>

          <BaseButton
            size="sm"
            variant="primary"
            :disabled="selectedPkIds.length !== 2 && filteredRuns.length < 2"
            @click="triggerPk"
          >
            {{
              selectedPkIds.length === 2
                ? "逐题对撞所选 2 场 PK →"
                : "对比最近两场逐题 PK →"
            }}
          </BaseButton>
        </div>
      </div>

      <div
        v-if="!filteredRuns.length"
        class="p-10 text-center text-gray-500 rounded-xl border border-dashed border-gray-200 dark:border-dark-700"
      >
        当前筛选条件下暂无历史打擂记录。
      </div>

      <template v-else>
        <!-- 子指标叠加芯片（质量组） -->
        <div
          v-if="metricGroup === 'quality' && availableSubMetrics.length"
          class="flex flex-wrap items-center gap-1.5"
        >
          <span class="text-gray-500 font-medium"
            >叠加具体指标趋势 (最多 6 项):</span
          >
          <button
            v-for="mName in availableSubMetrics"
            :key="mName"
            type="button"
            class="px-2 py-0.5 rounded-full border font-mono text-[11px] transition-colors"
            :class="
              selectedSubMetrics.includes(mName)
                ? 'bg-primary-50 border-primary-400 text-primary-700 dark:bg-primary-950/40 dark:border-primary-700 dark:text-primary-300 font-semibold'
                : 'border-gray-200 dark:border-dark-700 text-gray-500 hover:text-gray-800'
            "
            @click="toggleSubMetric(mName)"
          >
            {{ selectedSubMetrics.includes(mName) ? "✓ " : "+ " }}{{ mName }}
          </button>
        </div>

        <!-- ECharts 趋势折线图 -->
        <div
          class="rounded-xl border border-gray-200 dark:border-dark-700 bg-white dark:bg-dark-900 p-3"
        >
          <div ref="chartEl" class="w-full h-72" />
        </div>

        <!-- 全指标横向对照矩阵表 -->
        <div
          class="rounded-xl border border-gray-200 dark:border-dark-700 overflow-x-auto bg-white dark:bg-dark-900"
        >
          <table class="w-full text-left border-collapse text-xs">
            <thead>
              <tr
                class="bg-gray-50 dark:bg-dark-800/80 border-b border-gray-200 dark:border-dark-700"
              >
                <th
                  class="p-3 font-semibold min-w-48 sticky left-0 bg-gray-50 dark:bg-dark-800 z-10"
                >
                  指标维度 (较前一场涨跌)
                </th>
                <th
                  v-for="r in filteredRuns"
                  :key="r.id"
                  class="p-3 min-w-36 align-top border-l border-gray-100 dark:border-dark-800"
                >
                  <label class="flex items-start gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      :checked="selectedPkIds.includes(r.id)"
                      @change="togglePkRun(r.id)"
                    />
                    <div class="space-y-1">
                      <div
                        class="font-mono font-semibold text-gray-900 dark:text-dark-100"
                      >
                        #{{ r.id.slice(0, 8) }}
                      </div>
                      <div class="flex flex-wrap items-center gap-1">
                        <StatusPill
                          :tone="
                            r.status === 'completed' ? 'success' : 'danger'
                          "
                        >
                          {{ r.status }}
                        </StatusPill>
                        <span
                          v-if="r.version_num"
                          class="px-1.5 py-0.2 rounded bg-gray-100 dark:bg-dark-700 font-mono text-[10px]"
                        >
                          v{{ r.version_num }}
                        </span>
                      </div>
                      <div class="text-[11px] font-normal text-gray-500">
                        {{ r.target_graph_id }}
                        <span v-if="r.target_model_name">
                          · {{ r.target_model_name }}
                        </span>
                      </div>
                      <div
                        v-if="r.created_at"
                        class="text-[10px] font-normal text-gray-400"
                      >
                        {{ new Date(r.created_at).toLocaleString() }}
                      </div>
                    </div>
                  </label>
                </th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100 dark:divide-dark-800">
              <tr
                v-for="row in matrixRows"
                :key="row.key"
                class="hover:bg-gray-50/70 dark:hover:bg-dark-800/40"
              >
                <td
                  class="p-2.5 font-medium text-gray-700 dark:text-dark-200 sticky left-0 bg-white dark:bg-dark-900 z-10"
                >
                  {{ row.label }}
                </td>
                <td
                  v-for="(val, idx) in row.values"
                  :key="`${row.key}-${filteredRuns[idx].id}`"
                  class="p-2.5 font-mono border-l border-gray-100 dark:border-dark-800"
                >
                  <div class="flex items-center gap-1.5">
                    <span
                      :class="
                        val !== null &&
                        row.bestValue !== null &&
                        val === row.bestValue
                          ? 'font-bold text-amber-600 dark:text-amber-400'
                          : ''
                      "
                    >
                      {{ formatCell(val, row.format) }}
                    </span>
                    <span
                      v-if="
                        val !== null &&
                        row.bestValue !== null &&
                        val === row.bestValue
                      "
                      title="同评测集历史最佳"
                    >
                      🏆
                    </span>
                    <span
                      v-if="deltaInfo(row, idx)"
                      class="text-[10px]"
                      :class="deltaInfo(row, idx)!.cls"
                    >
                      {{ deltaInfo(row, idx)!.text }}
                    </span>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>

      <div class="flex justify-end pt-1">
        <BaseButton variant="secondary" @click="emit('close')">
          关闭对比工坊
        </BaseButton>
      </div>
    </div>
  </BaseDialog>
</template>

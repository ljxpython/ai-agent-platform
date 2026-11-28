<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import * as echarts from "echarts";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseDialog from "@/components/base/BaseDialog.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import BaseInput from "@/components/base/BaseInput.vue";
import BaseSelect from "@/components/base/BaseSelect.vue";
import StatusPill from "@/components/platform/StatusPill.vue";
import { buildMlflowTraceUrl } from "@/services/observability/langfuse-url";
import type {
  CompareRunsResult,
  CompareSidePayload,
  EvalRunItem,
} from "@/services/evaluation/studio";

const props = defineProps<{
  show: boolean;
  comparison: CompareRunsResult | null;
  runs?: EvalRunItem[];
}>();

const emit = defineEmits<{
  close: [];
  switchCompare: [baselineId: string, candidateId: string];
}>();

const activeTab = ref<"macro" | "cases" | "perf">("macro");
const caseFilter = ref<"all" | "regressed" | "improved" | "unchanged">("all");
const searchText = ref("");
const chartEl = ref<HTMLElement | null>(null);
let chart: echarts.ECharts | null = null;
let resizeObserver: ResizeObserver | null = null;

const runSelectOptions = computed(() =>
  (props.runs ?? []).map((r) => ({
    label: `#${r.id.slice(0, 8)} · ${r.suite_name || r.suite_id.slice(0, 6)} (${r.target_graph_id} · ${r.status})`,
    value: r.id,
  })),
);

const isSameRunComparison = computed(
  () =>
    Boolean(props.comparison) &&
    props.comparison!.baseline.id === props.comparison!.candidate.id,
);

const allDiffCases = computed(() => {
  if (!props.comparison) return [];
  const rows = [
    ...props.comparison.regressed.map((item) => ({
      ...item,
      diffType: "regressed" as const,
    })),
    ...props.comparison.improved.map((item) => ({
      ...item,
      diffType: "improved" as const,
    })),
    ...props.comparison.unchanged.map((item) => ({
      ...item,
      diffType: "unchanged" as const,
    })),
  ];
  const byTab =
    caseFilter.value === "all"
      ? rows
      : rows.filter((r) => r.diffType === caseFilter.value);
  const kw = searchText.value.trim().toLowerCase();
  if (!kw) return byTab;
  return byTab.filter(
    (r) =>
      r.case_key.toLowerCase().includes(kw) ||
      (r.question ?? "").toLowerCase().includes(kw),
  );
});

const baseSummary = computed(
  () =>
    (props.comparison?.baseline.summary_metrics ?? {}) as Record<string, any>,
);
const candSummary = computed(
  () =>
    (props.comparison?.candidate.summary_metrics ?? {}) as Record<string, any>,
);

function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function pctLabel(v: unknown): string {
  const n = num(v);
  return n !== null ? `${Math.round(n * 1000) / 10}%` : "-";
}

function msLabel(v: unknown): string {
  const n = num(v);
  return n !== null ? `${Math.round(n)} ms` : "-- (未记录)";
}

function fmtUsd(v: unknown): string {
  const n = num(v);
  if (n === null || n === 0) return "$0.0000";
  return `$${n.toFixed(6)}`;
}

const engineeringAdvice = computed(() => {
  if (!props.comparison) return null;
  if (isSameRunComparison.value) {
    return {
      tone: "warning" as const,
      text: "当前左右选择了同一场打擂记录，请在右侧下拉框切换另一场历史批次或新版本以查看真实差异对比。",
    };
  }
  const bScore = num(
    baseSummary.value.overall_score ?? baseSummary.value.tsr_pass_at_1,
  );
  const cScore = num(
    candSummary.value.overall_score ?? candSummary.value.tsr_pass_at_1,
  );
  const regCount = props.comparison.counts.regressed;
  const impCount = props.comparison.counts.improved;
  const parts: string[] = [];
  if (bScore !== null && cScore !== null) {
    const diffPts = Math.round((cScore - bScore) * 1000) / 10;
    if (diffPts > 0) parts.push(`【质量提升】对比组综合分领先 +${diffPts} 分`);
    else if (diffPts < 0)
      parts.push(`【质量明显退化】对比组综合分落后 ${diffPts} 分`);
    else parts.push("【综合分持平】两组整体得分接近");
  }
  const bP95 = num(baseSummary.value.ttft_ms?.p95);
  const cP95 = num(candSummary.value.ttft_ms?.p95);
  if (bP95 !== null && cP95 !== null) {
    const dMs = Math.round(cP95 - bP95);
    parts.push(
      dMs <= 0
        ? `首字延迟 TTFT P95 优化 ${Math.abs(dMs)} ms`
        : `首字延迟 TTFT P95 变慢 +${dMs} ms`,
    );
  }
  if (regCount > 0) {
    parts.push(
      `⚠️ 警告：检测到 ${regCount} 道题目出现退化，请切到「用例胜负榜」逐题排查原因！`,
    );
  } else if (impCount > 0) {
    parts.push(`共有 ${impCount} 道题目实现优化突破，0 道退化。`);
  }
  return {
    tone: regCount > 0 ? ("warning" as const) : ("success" as const),
    text:
      parts.join("；") || "已完成两场评测全量对比，可切换页签查看详细差异。",
  };
});

const macroRows = computed(() => {
  const b = baseSummary.value;
  const c = candSummary.value;
  const pctDelta = (bv: unknown, cv: unknown, higherBetter = true) => {
    const bn = num(bv);
    const cn = num(cv);
    if (bn === null || cn === null) return { text: "-", cls: "text-gray-400" };
    const d = Math.round((cn - bn) * 1000) / 10;
    if (d === 0) return { text: "0%", cls: "text-gray-500" };
    const good = higherBetter ? d > 0 : d < 0;
    return {
      text: `${d > 0 ? "+" : ""}${d}%`,
      cls: good
        ? "text-emerald-600 font-semibold"
        : "text-rose-600 font-semibold",
    };
  };
  const msDelta = (bv: unknown, cv: unknown) => {
    const bn = num(bv);
    const cn = num(cv);
    if (bn === null || cn === null) return { text: "-", cls: "text-gray-400" };
    const d = Math.round(cn - bn);
    if (d === 0) return { text: "0 ms", cls: "text-gray-500" };
    return {
      text: `${d > 0 ? "+" : ""}${d} ms`,
      cls:
        d < 0
          ? "text-emerald-600 font-semibold"
          : "text-rose-600 font-semibold",
    };
  };
  return [
    {
      label: "综合质量评分",
      base: pctLabel(b.overall_score ?? b.tsr_pass_at_1),
      cand: pctLabel(c.overall_score ?? c.tsr_pass_at_1),
      delta: pctDelta(
        b.overall_score ?? b.tsr_pass_at_1,
        c.overall_score ?? c.tsr_pass_at_1,
        true,
      ),
    },
    {
      label: "任务达成率 TSR / Pass@1",
      base: pctLabel(b.tsr_pass_at_1),
      cand: pctLabel(c.tsr_pass_at_1),
      delta: pctDelta(b.tsr_pass_at_1, c.tsr_pass_at_1, true),
    },
    {
      label: "L1 硬规则通过率",
      base: pctLabel(b.l1_pass_rate),
      cand: pctLabel(c.l1_pass_rate),
      delta: pctDelta(b.l1_pass_rate, c.l1_pass_rate, true),
    },
    {
      label: "工具死循环率",
      base: pctLabel(b.loop_rate ?? 0),
      cand: pctLabel(c.loop_rate ?? 0),
      delta: pctDelta(b.loop_rate ?? 0, c.loop_rate ?? 0, false),
    },
    {
      label: "TTFT 首字延迟 P50 / P95",
      base: `${b.ttft_ms?.p50 ?? "-"} / ${b.ttft_ms?.p95 ?? "-"} ms`,
      cand: `${c.ttft_ms?.p50 ?? "-"} / ${c.ttft_ms?.p95 ?? "-"} ms`,
      delta: msDelta(b.ttft_ms?.p95, c.ttft_ms?.p95),
    },
    {
      label: "Agent 单题端到端均耗",
      base: msLabel(b.duration_ms?.avg ?? b.duration_ms?.p50),
      cand: msLabel(c.duration_ms?.avg ?? c.duration_ms?.p50),
      delta: msDelta(
        b.duration_ms?.avg ?? b.duration_ms?.p50,
        c.duration_ms?.avg ?? c.duration_ms?.p50,
      ),
    },
    {
      label: "全量 Token / 预估费用",
      base: `${b.token_usage?.total_tokens ?? "--"} tok · ${fmtUsd(b.total_cost_usd)}`,
      cand: `${c.token_usage?.total_tokens ?? "--"} tok · ${fmtUsd(c.total_cost_usd)}`,
      delta: { text: "-", cls: "text-gray-400" },
    },
  ];
});

function sidePerfStats(sideRun: EvalRunItem, summary: Record<string, any>) {
  const tb = (summary.timing_breakdown ?? {}) as Record<string, any>;
  const avgMs =
    num(tb.agent_duration_ms?.avg) ??
    num(summary.duration_ms?.avg) ??
    num(summary.duration_ms?.p50);
  const p50Gen = num(tb.generation_ms?.p50);
  const avgGen = num(tb.generation_ms?.avg);
  const avgJudge = num(tb.judge_ms?.avg);
  const tok = (summary.token_usage ?? {}) as Record<string, unknown>;
  const bd = (summary.error_breakdown ?? {}) as Record<string, number>;
  return {
    graphId: sideRun.target_graph_id,
    avgMs,
    ttftP50: num(summary.ttft_ms?.p50),
    ttftP95: num(summary.ttft_ms?.p95),
    ttftP99: num(summary.ttft_ms?.p99),
    genAvg: avgGen ?? p50Gen,
    judgeAvg: avgJudge,
    totalDurationMs:
      avgMs !== null && num(summary.total_cases) !== null
        ? Math.round(avgMs * Number(summary.total_cases))
        : null,
    agentTokens: num(tok.agent_tokens),
    judgeTokens: num(tok.judge_tokens),
    totalTokens: num(tok.total_tokens),
    totalCost: num(summary.total_cost_usd),
    loopRate: num(summary.loop_rate),
    errorsTotal:
      (bd.fail ?? 0) + (bd.runtime_error ?? 0) + (bd.eval_error ?? 0),
    breakdown: bd,
  };
}

const basePerf = computed(() =>
  props.comparison
    ? sidePerfStats(props.comparison.baseline, baseSummary.value)
    : null,
);
const candPerf = computed(() =>
  props.comparison
    ? sidePerfStats(props.comparison.candidate, candSummary.value)
    : null,
);

function renderRadar() {
  if (!chartEl.value || !props.comparison || activeTab.value !== "macro")
    return;
  const width = chartEl.value.clientWidth;
  const height = chartEl.value.clientHeight;
  if (width === 0 || height === 0) return;
  if (chart && (chart.isDisposed() || chart.getWidth() === 0)) {
    chart.dispose();
    chart = null;
  }
  if (!chart) {
    chart = echarts.init(chartEl.value);
  }
  const b = baseSummary.value;
  const c = candSummary.value;
  const toPct = (v: unknown) =>
    typeof v === "number" ? Math.round(v * 100) : 0;
  const ttftScore = (p95: unknown) =>
    typeof p95 === "number"
      ? Math.max(10, 100 - Math.min(90, Math.round(p95 / 350)))
      : 75;

  chart.setOption(
    {
      tooltip: { trigger: "item" },
      legend: { bottom: 0, data: ["基线版本", "候选版本"] },
      radar: {
        radius: "65%",
        center: ["50%", "45%"],
        indicator: [
          { name: "任务达成 TSR", max: 100 },
          { name: "L1 规则通过", max: 100 },
          { name: "无死循环率", max: 100 },
          { name: "TTFT 响应", max: 100 },
          { name: "综合评分", max: 100 },
        ],
      },
      series: [
        {
          type: "radar",
          data: [
            {
              name: "基线版本",
              itemStyle: { color: "#4f46e5" },
              areaStyle: { color: "rgba(79, 70, 229, 0.14)" },
              value: [
                toPct(b.tsr_pass_at_1),
                toPct(b.l1_pass_rate),
                Math.max(0, 100 - toPct(b.loop_rate)),
                ttftScore(b.ttft_ms?.p95),
                toPct(b.overall_score ?? b.tsr_pass_at_1),
              ],
            },
            {
              name: "候选版本",
              itemStyle: { color: "#10b981" },
              areaStyle: { color: "rgba(16, 185, 129, 0.18)" },
              value: [
                toPct(c.tsr_pass_at_1),
                toPct(c.l1_pass_rate),
                Math.max(0, 100 - toPct(c.loop_rate)),
                ttftScore(c.ttft_ms?.p95),
                toPct(c.overall_score ?? c.tsr_pass_at_1),
              ],
            },
          ],
        },
      ],
    },
    true,
  );
  chart.resize();
}

function scheduleRadarRender() {
  void nextTick().then(() => {
    requestAnimationFrame(() => {
      renderRadar();
      setTimeout(renderRadar, 220);
    });
  });
}

watch(
  () => [props.show, props.comparison, activeTab.value],
  ([open, , tab]) => {
    if (open && tab === "macro") {
      scheduleRadarRender();
    }
  },
  { immediate: true },
);

watch(
  chartEl,
  (el) => {
    resizeObserver?.disconnect();
    resizeObserver = null;
    if (!el || typeof ResizeObserver === "undefined") return;
    resizeObserver = new ResizeObserver(() => {
      if (props.show && activeTab.value === "macro") {
        renderRadar();
      }
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

function swapBaselineAndCandidate() {
  if (!props.comparison) return;
  emit(
    "switchCompare",
    props.comparison.candidate.id,
    props.comparison.baseline.id,
  );
}

function onSelectBaseline(id: string) {
  if (!props.comparison || !id) return;
  emit("switchCompare", id, props.comparison.candidate.id);
}

function onSelectCandidate(id: string) {
  if (!props.comparison || !id) return;
  emit("switchCompare", props.comparison.baseline.id, id);
}

function openSideTrace(
  side: CompareSidePayload | null | undefined,
  projectId: string,
) {
  if (!side?.thread_id && !side?.trace_ids?.length) return;
  const url = buildMlflowTraceUrl(side.trace_ids?.[0] || "", {
    threadId: side.thread_id || undefined,
    projectId,
    view: side.trace_ids?.[0] ? "trace" : "sessions",
  });
  if (url) window.open(url, "_blank", "noopener");
}

function maxBarWidth(val: number | null, other: number | null): string {
  if (val === null) return "0%";
  const top = Math.max(val, other ?? 0, 1);
  return `${Math.max(8, Math.round((val / top) * 100))}%`;
}
</script>

<template>
  <BaseDialog
    :show="show"
    title="评测多维横向对撞与回溯工坊 (Head-to-Head PK)"
    width="full"
    @close="emit('close')"
  >
    <div v-if="comparison" class="space-y-4">
      <div
        class="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-gray-100 dark:border-dark-800"
      >
        <div class="flex flex-wrap items-center gap-2 text-xs text-gray-500">
          <StatusPill :tone="comparison.compatible ? 'success' : 'warning'">
            {{
              comparison.compatible ? "同冻结版本可比" : "跨版本注意口径差异"
            }}
          </StatusPill>
          <span
            >基线 #{{ comparison.baseline.id.slice(0, 8) }} ({{
              comparison.baseline.target_graph_id
            }})</span
          >
          <span>VS</span>
          <span
            >对比 #{{ comparison.candidate.id.slice(0, 8) }} ({{
              comparison.candidate.target_graph_id
            }})</span
          >
          <span class="text-rose-600 font-semibold"
            >退化: {{ comparison.counts.regressed }}</span
          >
          <span class="text-emerald-600 font-semibold"
            >提升: {{ comparison.counts.improved }}</span
          >
          <span>持平: {{ comparison.counts.unchanged }}</span>
        </div>
        <BaseButton
          size="sm"
          variant="secondary"
          @click="swapBaselineAndCandidate"
        >
          <BaseIcon name="refresh" size="xs" />
          <span class="ml-1">对调基准</span>
        </BaseButton>
      </div>

      <div
        v-if="engineeringAdvice"
        class="rounded-xl px-4 py-2.5 text-xs flex items-start gap-2 border"
        :class="
          engineeringAdvice.tone === 'warning'
            ? 'bg-amber-50/80 dark:bg-amber-950/30 border-amber-200 dark:border-amber-800 text-amber-900 dark:text-amber-200'
            : 'bg-emerald-50/80 dark:bg-emerald-950/30 border-emerald-200 dark:border-emerald-800 text-emerald-900 dark:text-emerald-200'
        "
      >
        <span class="font-semibold shrink-0">工程诊断建议：</span>
        <span>{{ engineeringAdvice.text }}</span>
      </div>

      <div class="flex flex-wrap items-center justify-between gap-3">
        <div
          class="inline-flex rounded-lg border border-gray-200 dark:border-dark-700 p-0.5 text-xs bg-gray-50 dark:bg-dark-800"
        >
          <button
            type="button"
            class="px-3 py-1.5 rounded-md font-medium transition"
            :class="
              activeTab === 'macro'
                ? 'bg-primary-600 text-white shadow-sm'
                : 'text-gray-600 dark:text-dark-300'
            "
            @click="activeTab = 'macro'"
          >
            宏观概览对决
          </button>
          <button
            type="button"
            class="px-3 py-1.5 rounded-md font-medium transition"
            :class="
              activeTab === 'cases'
                ? 'bg-primary-600 text-white shadow-sm'
                : 'text-gray-600 dark:text-dark-300'
            "
            @click="activeTab = 'cases'"
          >
            用例胜负榜 (Side-by-Side Diff ·
            {{
              comparison.counts.regressed +
              comparison.counts.improved +
              comparison.counts.unchanged
            }})
          </button>
          <button
            type="button"
            class="px-3 py-1.5 rounded-md font-medium transition"
            :class="
              activeTab === 'perf'
                ? 'bg-primary-600 text-white shadow-sm'
                : 'text-gray-600 dark:text-dark-300'
            "
            @click="activeTab = 'perf'"
          >
            性能与时延剖析
          </button>
        </div>

        <div
          v-if="runSelectOptions.length"
          class="flex flex-wrap items-center gap-2 text-xs"
        >
          <span class="text-gray-500">基准:</span>
          <div class="w-56">
            <BaseSelect
              :model-value="comparison.baseline.id"
              :options="runSelectOptions"
              @update:model-value="onSelectBaseline"
            />
          </div>
          <span class="font-semibold text-gray-400">VS</span>
          <span class="text-gray-500">对比:</span>
          <div class="w-56">
            <BaseSelect
              :model-value="comparison.candidate.id"
              :options="runSelectOptions"
              @update:model-value="onSelectCandidate"
            />
          </div>
        </div>
      </div>

      <!-- Tab 1: Macro Radar & 7D KPI Comparison -->
      <div
        v-if="activeTab === 'macro'"
        class="grid gap-4 lg:grid-cols-12 items-start"
      >
        <div
          class="lg:col-span-6 rounded-xl border border-gray-200 dark:border-dark-700 p-4 bg-white dark:bg-dark-900"
        >
          <div
            class="text-xs font-semibold text-gray-700 dark:text-dark-200 mb-2"
          >
            5 维能力对撞雷达图
          </div>
          <div ref="chartEl" class="w-full h-72 min-h-[288px]" />
        </div>

        <div
          class="lg:col-span-6 rounded-xl border border-gray-200 dark:border-dark-700 overflow-hidden bg-white dark:bg-dark-900"
        >
          <div
            class="px-4 py-2.5 bg-gray-50 dark:bg-dark-800 border-b border-gray-100 dark:border-dark-700 text-xs font-semibold"
          >
            7 维核心指标并排对比表
          </div>
          <table class="w-full text-xs">
            <thead
              class="bg-gray-50/60 dark:bg-dark-800/40 text-gray-500 border-b border-gray-100 dark:border-dark-700"
            >
              <tr>
                <th class="px-3 py-2 text-left font-medium">维度指标</th>
                <th class="px-3 py-2 text-right font-medium text-indigo-600">
                  基线 #{{ comparison.baseline.id.slice(0, 6) }}
                </th>
                <th class="px-3 py-2 text-right font-medium text-emerald-600">
                  对比 #{{ comparison.candidate.id.slice(0, 6) }}
                </th>
                <th class="px-3 py-2 text-right font-medium">涨跌 Delta</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100 dark:divide-dark-800">
              <tr v-for="row in macroRows" :key="row.label">
                <td
                  class="px-3 py-2.5 text-gray-700 dark:text-dark-200 font-medium"
                >
                  {{ row.label }}
                </td>
                <td class="px-3 py-2.5 text-right font-mono">{{ row.base }}</td>
                <td class="px-3 py-2.5 text-right font-mono">{{ row.cand }}</td>
                <td
                  class="px-3 py-2.5 text-right font-mono"
                  :class="row.delta.cls"
                >
                  {{ row.delta.text }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Tab 2: Side-by-Side Diff -->
      <div v-else-if="activeTab === 'cases'" class="space-y-3 text-xs">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div class="flex flex-wrap items-center gap-2">
            <BaseButton
              size="sm"
              :variant="caseFilter === 'all' ? 'primary' : 'secondary'"
              @click="caseFilter = 'all'"
            >
              全部 ({{
                comparison.counts.regressed +
                comparison.counts.improved +
                comparison.counts.unchanged
              }})
            </BaseButton>
            <BaseButton
              size="sm"
              :variant="caseFilter === 'regressed' ? 'danger' : 'secondary'"
              @click="caseFilter = 'regressed'"
            >
              仅看退化 ({{ comparison.counts.regressed }})
            </BaseButton>
            <BaseButton
              size="sm"
              :variant="caseFilter === 'improved' ? 'primary' : 'secondary'"
              @click="caseFilter = 'improved'"
            >
              仅看提升 ({{ comparison.counts.improved }})
            </BaseButton>
            <BaseButton
              size="sm"
              :variant="caseFilter === 'unchanged' ? 'primary' : 'secondary'"
              @click="caseFilter = 'unchanged'"
            >
              持平 ({{ comparison.counts.unchanged }})
            </BaseButton>
          </div>
          <div class="w-64">
            <BaseInput
              v-model="searchText"
              placeholder="搜索 case_key 或题目关键词..."
            />
          </div>
        </div>

        <div class="max-h-[460px] overflow-y-auto space-y-3 pr-1">
          <div
            v-for="item in allDiffCases"
            :key="`${item.case_key}-${item.attempt_idx}`"
            class="rounded-xl border border-gray-200 dark:border-dark-700 overflow-hidden bg-white dark:bg-dark-900"
          >
            <div
              class="px-4 py-2.5 bg-gray-50/90 dark:bg-dark-800/70 border-b border-gray-100 dark:border-dark-700 flex flex-wrap items-center justify-between gap-2"
            >
              <div class="flex flex-wrap items-center gap-2">
                <StatusPill
                  :tone="
                    item.diffType === 'regressed'
                      ? 'danger'
                      : item.diffType === 'improved'
                        ? 'success'
                        : 'neutral'
                  "
                >
                  {{
                    item.diffType === "regressed"
                      ? "严重退化"
                      : item.diffType === "improved"
                        ? "优化提升"
                        : "持平"
                  }}
                </StatusPill>
                <span class="font-mono font-semibold"
                  >{{ item.case_key }} #{{ item.attempt_idx }}</span
                >
                <span
                  class="text-gray-700 dark:text-dark-200 font-medium line-clamp-1 max-w-xl"
                >
                  {{ item.question || "（暂无题目原文）" }}
                </span>
              </div>
              <div
                class="flex flex-wrap items-center gap-3 font-mono text-[11px]"
              >
                <span>
                  得分 {{ pctLabel(item.baseline_score) }} →
                  {{ pctLabel(item.candidate_score) }}
                </span>
                <span class="text-gray-500">
                  TTFT {{ item.baseline_ttft_ms ?? "-" }}ms →
                  {{ item.candidate_ttft_ms ?? "-" }}ms
                </span>
              </div>
            </div>

            <div class="p-3.5 grid gap-3 md:grid-cols-2">
              <!-- Baseline Side -->
              <div
                class="rounded-lg border border-indigo-200/80 dark:border-indigo-900/60 bg-indigo-50/20 dark:bg-indigo-950/10 p-3 space-y-2"
              >
                <div class="flex items-center justify-between gap-2">
                  <span
                    class="font-semibold text-indigo-700 dark:text-indigo-300"
                  >
                    基线回复 (#{{ comparison.baseline.id.slice(0, 6) }})
                  </span>
                  <div class="flex items-center gap-1.5">
                    <StatusPill
                      :tone="
                        item.baseline_status === 'completed'
                          ? 'success'
                          : 'danger'
                      "
                    >
                      {{ item.baseline_status || "缺失" }}
                    </StatusPill>
                    <BaseButton
                      v-if="
                        item.baseline?.thread_id ||
                        item.baseline?.trace_ids?.length
                      "
                      size="sm"
                      variant="secondary"
                      @click="
                        openSideTrace(
                          item.baseline,
                          comparison.baseline.target_project_id,
                        )
                      "
                    >
                      Trace ↗
                    </BaseButton>
                  </div>
                </div>
                <div
                  class="p-2.5 rounded bg-white dark:bg-dark-900 border border-gray-200/80 dark:border-dark-700 whitespace-pre-wrap max-h-36 overflow-y-auto text-[11px]"
                >
                  {{ item.baseline?.final_answer || "（无输出正文）" }}
                </div>
                <div
                  v-if="item.baseline?.metrics?.length"
                  class="flex flex-wrap gap-1.5"
                >
                  <span
                    v-for="m in item.baseline.metrics"
                    :key="`b-${String(m.name)}`"
                    class="px-2 py-0.5 rounded border text-[11px]"
                    :class="
                      m.passed
                        ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
                        : 'bg-rose-50 border-rose-200 text-rose-700'
                    "
                    :title="String(m.reason || '')"
                  >
                    [{{ m.layer }}] {{ m.name }}: {{ m.score ?? "-" }}
                  </span>
                </div>
              </div>

              <!-- Candidate Side -->
              <div
                class="rounded-lg border border-emerald-200/80 dark:border-emerald-900/60 bg-emerald-50/20 dark:bg-emerald-950/10 p-3 space-y-2"
              >
                <div class="flex items-center justify-between gap-2">
                  <span
                    class="font-semibold text-emerald-700 dark:text-emerald-300"
                  >
                    对比回复 (#{{ comparison.candidate.id.slice(0, 6) }})
                  </span>
                  <div class="flex items-center gap-1.5">
                    <StatusPill
                      :tone="
                        item.candidate_status === 'completed'
                          ? 'success'
                          : 'danger'
                      "
                    >
                      {{ item.candidate_status || "缺失" }}
                    </StatusPill>
                    <BaseButton
                      v-if="
                        item.candidate?.thread_id ||
                        item.candidate?.trace_ids?.length
                      "
                      size="sm"
                      variant="secondary"
                      @click="
                        openSideTrace(
                          item.candidate,
                          comparison.candidate.target_project_id,
                        )
                      "
                    >
                      Trace ↗
                    </BaseButton>
                  </div>
                </div>
                <div
                  class="p-2.5 rounded bg-white dark:bg-dark-900 border border-gray-200/80 dark:border-dark-700 whitespace-pre-wrap max-h-36 overflow-y-auto text-[11px]"
                >
                  {{ item.candidate?.final_answer || "（无输出正文）" }}
                </div>
                <div
                  v-if="item.candidate?.metrics?.length"
                  class="flex flex-wrap gap-1.5"
                >
                  <span
                    v-for="m in item.candidate.metrics"
                    :key="`c-${String(m.name)}`"
                    class="px-2 py-0.5 rounded border text-[11px]"
                    :class="
                      m.passed
                        ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
                        : 'bg-rose-50 border-rose-200 text-rose-700'
                    "
                    :title="String(m.reason || '')"
                  >
                    [{{ m.layer }}] {{ m.name }}: {{ m.score ?? "-" }}
                  </span>
                </div>
              </div>
            </div>

            <div
              v-if="item.expected_answer"
              class="px-4 py-2 bg-gray-50/60 dark:bg-dark-800/40 border-t border-gray-100 dark:border-dark-800 text-[11px] text-gray-600 dark:text-dark-300"
            >
              <span class="font-semibold">参考黄金答案：</span
              >{{ item.expected_answer }}
            </div>
          </div>
        </div>
      </div>

      <!-- Tab 3: Performance & Latency/Cost Breakdown (LightRAG Parity) -->
      <div v-else-if="basePerf && candPerf" class="space-y-4 text-xs">
        <div class="grid gap-4 md:grid-cols-2">
          <div
            class="rounded-xl border border-indigo-200 dark:border-indigo-900/70 bg-indigo-50/20 dark:bg-indigo-950/10 p-4 space-y-2.5"
          >
            <div class="flex items-center justify-between">
              <span class="font-semibold text-indigo-700 dark:text-indigo-300">
                基线 #{{ comparison.baseline.id.slice(0, 8) }} ({{
                  basePerf.graphId
                }}) 耗时与成本拓扑
              </span>
              <span class="font-mono font-semibold text-indigo-600">
                单题均耗: {{ msLabel(basePerf.avgMs) }}
              </span>
            </div>
            <div class="space-y-1.5 font-mono text-[11px]">
              <div class="flex justify-between">
                <span class="text-gray-600"
                  >TTFT 首字响应延迟 (P50 / P95):</span
                >
                <span
                  >{{ basePerf.ttftP50 ?? "--" }} /
                  {{ basePerf.ttftP95 ?? "--" }} ms</span
                >
              </div>
              <div class="flex justify-between">
                <span class="text-gray-600">首字后生成与工具耗时 (均值):</span>
                <span>{{ msLabel(basePerf.genAvg) }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-600">DeepEval L2 裁判思考均耗:</span>
                <span>{{ msLabel(basePerf.judgeAvg) }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-600">整场累计推理总耗时:</span>
                <span>{{ msLabel(basePerf.totalDurationMs) }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-600"
                  >全量 Token (Agent / 裁判 / 总计):</span
                >
                <span
                  >{{ basePerf.agentTokens ?? "--" }} /
                  {{ basePerf.judgeTokens ?? "--" }} /
                  {{ basePerf.totalTokens ?? "--" }}</span
                >
              </div>
              <div class="flex justify-between">
                <span class="text-gray-600">网关与裁判累计预估费用:</span>
                <span class="font-semibold">{{
                  fmtUsd(basePerf.totalCost)
                }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-600">死循环信号 / 异常病例数:</span>
                <span
                  >{{ pctLabel(basePerf.loopRate ?? 0) }} ·
                  {{ basePerf.errorsTotal }} 异常</span
                >
              </div>
            </div>
          </div>

          <div
            class="rounded-xl border border-emerald-200 dark:border-emerald-900/70 bg-emerald-50/20 dark:bg-emerald-950/10 p-4 space-y-2.5"
          >
            <div class="flex items-center justify-between">
              <span
                class="font-semibold text-emerald-700 dark:text-emerald-300"
              >
                对比 #{{ comparison.candidate.id.slice(0, 8) }} ({{
                  candPerf.graphId
                }}) 耗时与成本拓扑
              </span>
              <span class="font-mono font-semibold text-emerald-600">
                单题均耗: {{ msLabel(candPerf.avgMs) }}
              </span>
            </div>
            <div class="space-y-1.5 font-mono text-[11px]">
              <div class="flex justify-between">
                <span class="text-gray-600"
                  >TTFT 首字响应延迟 (P50 / P95):</span
                >
                <span
                  >{{ candPerf.ttftP50 ?? "--" }} /
                  {{ candPerf.ttftP95 ?? "--" }} ms</span
                >
              </div>
              <div class="flex justify-between">
                <span class="text-gray-600">首字后生成与工具耗时 (均值):</span>
                <span>{{ msLabel(candPerf.genAvg) }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-600">DeepEval L2 裁判思考均耗:</span>
                <span>{{ msLabel(candPerf.judgeAvg) }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-600">整场累计推理总耗时:</span>
                <span>{{ msLabel(candPerf.totalDurationMs) }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-600"
                  >全量 Token (Agent / 裁判 / 总计):</span
                >
                <span
                  >{{ candPerf.agentTokens ?? "--" }} /
                  {{ candPerf.judgeTokens ?? "--" }} /
                  {{ candPerf.totalTokens ?? "--" }}</span
                >
              </div>
              <div class="flex justify-between">
                <span class="text-gray-600">网关与裁判累计预估费用:</span>
                <span class="font-semibold">{{
                  fmtUsd(candPerf.totalCost)
                }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-600">死循环信号 / 异常病例数:</span>
                <span
                  >{{ pctLabel(candPerf.loopRate ?? 0) }} ·
                  {{ candPerf.errorsTotal }} 异常</span
                >
              </div>
            </div>
          </div>
        </div>

        <!-- Visual Latency Bars -->
        <div
          class="rounded-xl border border-gray-200 dark:border-dark-700 p-4 space-y-3 bg-white dark:bg-dark-900"
        >
          <div class="font-semibold text-gray-700 dark:text-dark-200">
            耗时对比直观进度条
          </div>
          <div class="space-y-2">
            <div>
              <div class="flex justify-between text-[11px] mb-1">
                <span>TTFT P95 首字响应</span>
                <span class="font-mono"
                  >基线 {{ basePerf.ttftP95 ?? "--" }}ms vs 对比
                  {{ candPerf.ttftP95 ?? "--" }}ms</span
                >
              </div>
              <div class="space-y-1">
                <div
                  class="h-2 rounded bg-indigo-500/80"
                  :style="{
                    width: maxBarWidth(basePerf.ttftP95, candPerf.ttftP95),
                  }"
                />
                <div
                  class="h-2 rounded bg-emerald-500/80"
                  :style="{
                    width: maxBarWidth(candPerf.ttftP95, basePerf.ttftP95),
                  }"
                />
              </div>
            </div>
            <div>
              <div class="flex justify-between text-[11px] mb-1">
                <span>Agent 单题端到端均耗</span>
                <span class="font-mono"
                  >基线 {{ basePerf.avgMs ?? "--" }}ms vs 对比
                  {{ candPerf.avgMs ?? "--" }}ms</span
                >
              </div>
              <div class="space-y-1">
                <div
                  class="h-2 rounded bg-indigo-500/80"
                  :style="{
                    width: maxBarWidth(basePerf.avgMs, candPerf.avgMs),
                  }"
                />
                <div
                  class="h-2 rounded bg-emerald-500/80"
                  :style="{
                    width: maxBarWidth(candPerf.avgMs, basePerf.avgMs),
                  }"
                />
              </div>
            </div>
          </div>
        </div>

        <div
          class="rounded-xl border border-gray-200 dark:border-dark-700 bg-gray-50/80 dark:bg-dark-800/50 p-3.5 text-[11px] text-gray-600 dark:text-dark-300 space-y-1"
        >
          <div class="font-semibold">耗时分段与数据真实度口径说明</div>
          <p>
            1) TTFT 首字延迟与端到端总耗时均由 <code>eval-runner</code> 通过流式
            SSE 真实到达时刻计算； 2) 若某场历史打擂早于本版本
            Token/分段计时上线或未配置模型单价，对应 Token、生成阶段或 L2
            裁判耗时将按事实显示为
            <code>-- (未记录)</code
            >；新发起的评测会自动穿透采集平台网关用量与单价计费。
          </p>
        </div>
      </div>

      <div
        class="flex justify-end pt-2 border-t border-gray-100 dark:border-dark-800"
      >
        <BaseButton variant="secondary" @click="emit('close')"
          >关闭工作台</BaseButton
        >
      </div>
    </div>
  </BaseDialog>
</template>

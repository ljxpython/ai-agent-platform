<script setup lang="ts">
import { computed, ref, watch } from "vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseInput from "@/components/base/BaseInput.vue";
import SurfaceCard from "@/components/base/SurfaceCard.vue";
import EmptyState from "@/components/platform/EmptyState.vue";
import MetricCard from "@/components/platform/MetricCard.vue";
import StatusPill from "@/components/platform/StatusPill.vue";
import { buildMlflowTraceUrl } from "@/services/observability/langfuse-url";
import type {
  EvalRunCaseItem,
  EvalRunItem,
  EvalSuiteItem,
} from "@/services/evaluation/studio";

const props = defineProps<{
  runs: EvalRunItem[];
  suites: EvalSuiteItem[];
  activeRun: EvalRunItem | null;
  runCases: EvalRunCaseItem[];
}>();

const emit = defineEmits<{
  selectRun: [runId: string];
  control: [
    runId: string,
    action: "pause" | "resume" | "retry_failed" | "rescore" | "cancel",
  ];
  compare: [baselineId: string, candidateId: string];
  review: [runCaseId: string, verdict: "pass" | "fail", reason: string];
  openDiagnosis: [runId: string];
  rerunSuite: [suiteId: string];
  toggleSandbox: [];
}>();

const selectedCompareIds = ref<string[]>([]);
const expandedSuites = ref<Record<string, boolean>>({});
const expandedCaseId = ref<string | null>(null);
const reviewNotes = ref<Record<string, string>>({});
const expandedRunId = ref<string | null>(props.activeRun?.id ?? null);

watch(
  () => props.activeRun?.id,
  (newId) => {
    if (newId) {
      expandedRunId.value = newId;
    }
  },
  { immediate: true },
);

function isRunExpanded(runId: string): boolean {
  return expandedRunId.value === runId && props.activeRun?.id === runId;
}

function toggleRunEvidence(runId: string) {
  if (expandedRunId.value === runId) {
    expandedRunId.value = null;
  } else {
    expandedRunId.value = runId;
    emit("selectRun", runId);
  }
}

watch(
  () => props.runCases,
  (cases) => {
    if (cases && cases.length === 1) {
      expandedCaseId.value = cases[0].id;
    }
  },
  { immediate: true },
);

function runScore(r: EvalRunItem): number | null {
  const m = r.summary_metrics as Record<string, unknown> | undefined;
  const val = m?.overall_score ?? m?.tsr_pass_at_1;
  return typeof val === "number" ? val : null;
}

const runningCount = computed(
  () =>
    props.runs.filter((r) => r.status === "running" || r.status === "queued")
      .length,
);

const averageScore = computed(() => {
  const vals = props.runs.map(runScore).filter((v): v is number => v !== null);
  if (!vals.length) return "-";
  return `${Math.round((vals.reduce((a, b) => a + b, 0) / vals.length) * 100)}%`;
});

const bestPassRate = computed(() => {
  const vals = props.runs
    .map((r) => (r.summary_metrics as Record<string, unknown>)?.tsr_pass_at_1)
    .filter((v): v is number => typeof v === "number");
  if (!vals.length) return "0%";
  return `${Math.round(Math.max(...vals) * 100)}%`;
});

const groupedRuns = computed(() => {
  const suiteNameById = new Map(props.suites.map((s) => [s.id, s.name]));
  const map = new Map<string, EvalRunItem[]>();
  for (const run of props.runs) {
    const arr = map.get(run.suite_id) ?? [];
    arr.push(run);
    map.set(run.suite_id, arr);
  }
  return [...map.entries()].map(([suiteId, items]) => {
    const sorted = [...items].sort((a, b) =>
      (b.created_at ?? "").localeCompare(a.created_at ?? ""),
    );
    const scores = sorted.map(runScore).filter((v): v is number => v !== null);
    const best = scores.length ? Math.max(...scores) : null;
    const latest = scores[0] ?? null;
    const prev = scores[1] ?? null;
    const delta = latest !== null && prev !== null ? latest - prev : null;
    return {
      suiteId,
      suiteName:
        sorted[0]?.suite_name ||
        suiteNameById.get(suiteId) ||
        `题库 ${suiteId.slice(0, 8)}`,
      targetProjectName:
        sorted[0]?.target_project_name ||
        sorted[0]?.target_project_id.slice(0, 8),
      items: sorted,
      bestScore: best,
      latestScore: latest,
      delta,
    };
  });
});

const summary = computed(
  () => (props.activeRun?.summary_metrics ?? {}) as Record<string, any>,
);

function toggleCompare(runId: string) {
  if (selectedCompareIds.value.includes(runId)) {
    selectedCompareIds.value = selectedCompareIds.value.filter(
      (id) => id !== runId,
    );
  } else if (selectedCompareIds.value.length < 2) {
    selectedCompareIds.value = [...selectedCompareIds.value, runId];
  } else {
    selectedCompareIds.value = [selectedCompareIds.value[1], runId];
  }
}

function triggerCompare() {
  if (selectedCompareIds.value.length === 2) {
    emit("compare", selectedCompareIds.value[0], selectedCompareIds.value[1]);
    return;
  }
  if (props.runs.length >= 2) {
    const sorted = [...props.runs].sort((a, b) =>
      (b.created_at ?? "").localeCompare(a.created_at ?? ""),
    );
    emit("compare", sorted[1].id, sorted[0].id);
  }
}

function quickCompareRun(run: EvalRunItem, groupItems: EvalRunItem[]) {
  const peer =
    groupItems.find((item) => item.id !== run.id) ??
    props.runs.find((item) => item.id !== run.id);
  if (peer) {
    emit("compare", peer.id, run.id);
  } else {
    emit("compare", run.id, run.id);
  }
}

function statusTone(status: string) {
  if (status === "completed" || status === "success") return "success";
  if (status === "failed" || status === "error") return "danger";
  if (status === "running" || status === "queued") return "info";
  return "warning";
}

function openMlflowTrace(rc: EvalRunCaseItem, projectId: string) {
  const url = buildMlflowTraceUrl(rc.trace_ids?.[0] || "", {
    threadId: rc.thread_id || undefined,
    projectId,
    view: rc.trace_ids?.[0] ? "trace" : "sessions",
  });
  if (url) window.open(url, "_blank", "noopener");
}

function caseMetrics(rc: EvalRunCaseItem) {
  const res = rc.results as Record<string, unknown> | undefined;
  return Array.isArray(res?.metrics)
    ? (res.metrics as Array<Record<string, unknown>>)
    : [];
}

function caseTranscript(rc: EvalRunCaseItem) {
  const res = rc.results as Record<string, unknown> | undefined;
  return Array.isArray(res?.transcript)
    ? (res.transcript as Array<Record<string, unknown>>)
    : [];
}
</script>

<template>
  <div class="space-y-4">
    <section class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <MetricCard
        label="总打擂场次"
        :value="runs.length"
        hint="已归档+进行中"
        icon="activity"
        tone="primary"
      />
      <MetricCard
        label="正在并发打擂"
        :value="runningCount"
        hint="支持暂停与断点续跑"
        icon="refresh"
        tone="info"
      />
      <MetricCard
        label="历史平均综合分"
        :value="averageScore"
        hint="全题库加权均分"
        icon="overview"
        tone="success"
      />
      <MetricCard
        label="最高全项通过率"
        :value="bestPassRate"
        hint="TSR / Pass@1"
        icon="shield"
        tone="warning"
      />
    </section>

    <SurfaceCard class="p-4 space-y-3">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 class="text-sm font-semibold">
            历史打擂成果归档 ({{ groupedRuns.length }} 个评测集)
          </h3>
          <p class="text-xs text-gray-500">
            按评测集聚合历史最高分、趋势涨跌与逐题取证（支持勾选两场或一键点「+
            对比」直接横向 PK）
          </p>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <BaseButton
            size="sm"
            variant="secondary"
            @click="emit('toggleSandbox')"
          >
            设为专用测试靶场
          </BaseButton>
          <BaseButton
            size="sm"
            variant="primary"
            :disabled="selectedCompareIds.length !== 2 && runs.length < 2"
            @click="triggerCompare"
          >
            {{
              selectedCompareIds.length === 2
                ? "横向对撞已选 2 场 PK"
                : runs.length >= 2
                  ? "对比最近两场 PK"
                  : `横向跨场次对撞 PK (${selectedCompareIds.length}/2)`
            }}
          </BaseButton>
        </div>
      </div>

      <EmptyState
        v-if="!groupedRuns.length"
        title="尚无评测运行记录"
        description="请从“题库资产全景”或“考题表格汇总”点击“发起评测打擂”启动首轮并发评测。"
      />

      <div v-else class="space-y-3">
        <div
          v-for="group in groupedRuns"
          :key="group.suiteId"
          class="rounded-xl border border-gray-200 dark:border-dark-700 overflow-hidden"
        >
          <div
            class="p-3.5 bg-gray-50/80 dark:bg-dark-800/60 flex flex-wrap items-center justify-between gap-3"
          >
            <div class="flex flex-wrap items-center gap-2.5 text-xs">
              <strong class="text-sm text-gray-900 dark:text-dark-100">{{
                group.suiteName
              }}</strong>
              <StatusPill tone="neutral"
                >共 {{ group.items.length }} 场打擂</StatusPill
              >
              <span class="text-gray-500"
                >靶场: {{ group.targetProjectName }}</span
              >
            </div>

            <div class="flex flex-wrap items-center gap-3 text-xs">
              <span
                v-if="group.bestScore !== null"
                class="px-2 py-1 rounded bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 font-semibold"
              >
                历史最佳 {{ Math.round(group.bestScore * 100) }}%
              </span>
              <span v-if="group.latestScore !== null" class="font-semibold">
                最新 {{ Math.round(group.latestScore * 100) }}%
                <span
                  v-if="group.delta !== null"
                  :class="
                    group.delta >= 0 ? 'text-emerald-600' : 'text-rose-600'
                  "
                >
                  ({{ group.delta >= 0 ? "+" : ""
                  }}{{ Math.round(group.delta * 1000) / 10 }}%)
                </span>
              </span>
              <button
                type="button"
                class="text-primary-600 hover:underline font-medium"
                @click="
                  expandedSuites[group.suiteId] = !(
                    expandedSuites[group.suiteId] ?? true
                  )
                "
              >
                {{
                  (expandedSuites[group.suiteId] ?? true)
                    ? "收起时序 ▲"
                    : "展开时序 ▼"
                }}
              </button>
            </div>
          </div>

          <div
            v-if="expandedSuites[group.suiteId] ?? true"
            class="divide-y divide-gray-100 dark:divide-dark-800"
          >
            <template v-for="run in group.items" :key="run.id">
              <div
                class="p-3 flex flex-wrap items-center justify-between gap-3 text-xs hover:bg-gray-50/60 dark:hover:bg-dark-800/30"
                :class="
                  isRunExpanded(run.id)
                    ? 'bg-primary-50/40 dark:bg-primary-950/20'
                    : ''
                "
              >
                <div class="flex items-center gap-3">
                  <input
                    type="checkbox"
                    :checked="selectedCompareIds.includes(run.id)"
                    @change="toggleCompare(run.id)"
                  />
                  <div class="space-y-0.5">
                    <div class="flex items-center gap-2">
                      <span class="font-mono font-semibold"
                        >打擂 #{{ run.id.slice(0, 8) }}</span
                      >
                      <span
                        v-if="isRunExpanded(run.id)"
                        class="px-1.5 py-0.5 rounded text-[10px] font-medium bg-primary-100 text-primary-700 dark:bg-primary-900/50 dark:text-primary-300"
                      >
                        已展开取证
                      </span>
                      <StatusPill :tone="statusTone(run.status)">{{
                        run.status
                      }}</StatusPill>
                      <StatusPill tone="neutral">{{
                        run.target_graph_id
                      }}</StatusPill>
                      <span
                        >并发 {{ run.concurrency }} · k={{ run.repeat_k }}</span
                      >
                    </div>
                    <div class="text-[11px] text-gray-500">
                      靶场
                      {{
                        run.target_project_name ||
                        run.target_project_id.slice(0, 8)
                      }}
                      <span v-if="run.created_at"
                        >· {{ new Date(run.created_at).toLocaleString() }}</span
                      >
                    </div>
                  </div>
                </div>

                <div class="flex flex-wrap items-center gap-3">
                  <div class="text-right font-mono">
                    <div class="font-semibold">
                      综合
                      {{
                        runScore(run) !== null
                          ? `${Math.round(runScore(run)! * 100)}%`
                          : "-"
                      }}
                    </div>
                    <div class="text-[11px] text-gray-500">
                      TTFT P95:
                      {{ (run.summary_metrics as any)?.ttft_ms?.p95 ?? "-" }} ms
                      <span
                        v-if="
                          (run.summary_metrics as any)?.token_usage
                            ?.total_tokens
                        "
                      >
                        ·
                        {{
                          (run.summary_metrics as any).token_usage.total_tokens
                        }}
                        tok
                      </span>
                    </div>
                  </div>
                  <BaseButton
                    size="sm"
                    variant="secondary"
                    @click="emit('rerunSuite', run.suite_id)"
                  >
                    重跑
                  </BaseButton>
                  <BaseButton
                    size="sm"
                    variant="secondary"
                    :disabled="runs.length < 2"
                    @click="quickCompareRun(run, group.items)"
                  >
                    + 对比
                  </BaseButton>
                  <BaseButton
                    size="sm"
                    :variant="isRunExpanded(run.id) ? 'primary' : 'secondary'"
                    @click="toggleRunEvidence(run.id)"
                  >
                    <span class="inline-flex items-center gap-1">
                      {{ isRunExpanded(run.id) ? "收起取证 ▲" : "查看取证 ▼" }}
                    </span>
                  </BaseButton>
                </div>
              </div>

              <!-- 就地内联展开的白盒取证详情面板 -->
              <div
                v-if="isRunExpanded(run.id) && activeRun"
                class="p-4 bg-gray-50/80 dark:bg-dark-900/80 border-t border-b border-primary-200/50 dark:border-primary-900/40 space-y-4"
              >
                <div class="flex flex-wrap items-center justify-between gap-2">
                  <div class="flex items-center gap-2">
                    <h3 class="text-sm font-semibold">
                      批次白盒取证 · #{{ activeRun.id.slice(0, 8) }}
                    </h3>
                    <StatusPill :tone="statusTone(activeRun.status)">{{
                      activeRun.status
                    }}</StatusPill>
                  </div>
                  <div class="flex flex-wrap items-center gap-2">
                    <BaseButton
                      size="sm"
                      variant="ghost"
                      class="text-gray-500 hover:text-gray-700 dark:hover:text-dark-200"
                      @click="toggleRunEvidence(run.id)"
                    >
                      收起取证 ▲
                    </BaseButton>
                    <BaseButton
                      size="sm"
                      variant="secondary"
                      :disabled="
                        activeRun.status !== 'running' &&
                        activeRun.status !== 'queued'
                      "
                      @click="emit('control', activeRun.id, 'pause')"
                    >
                      暂停
                    </BaseButton>
                    <BaseButton
                      size="sm"
                      variant="secondary"
                      :disabled="
                        activeRun.status === 'running' ||
                        activeRun.status === 'queued' ||
                        activeRun.status === 'completed'
                      "
                      @click="emit('control', activeRun.id, 'resume')"
                    >
                      继续未完成
                    </BaseButton>
                    <BaseButton
                      size="sm"
                      variant="secondary"
                      :disabled="
                        activeRun.status === 'running' ||
                        activeRun.status === 'queued'
                      "
                      @click="emit('control', activeRun.id, 'retry_failed')"
                    >
                      仅重跑失败题
                    </BaseButton>
                    <BaseButton
                      size="sm"
                      variant="secondary"
                      :disabled="
                        activeRun.status === 'running' ||
                        activeRun.status === 'queued'
                      "
                      @click="emit('control', activeRun.id, 'rescore')"
                    >
                      同证据重评
                    </BaseButton>
                    <BaseButton
                      size="sm"
                      variant="primary"
                      @click="emit('openDiagnosis', activeRun.id)"
                    >
                      呼出 AI 诊断专家
                    </BaseButton>
                  </div>
                </div>

                <section class="grid gap-3 md:grid-cols-4">
                  <MetricCard
                    label="TSR / Pass@1"
                    :value="
                      summary.tsr_pass_at_1 != null
                        ? `${Math.round(summary.tsr_pass_at_1 * 100)}%`
                        : '-'
                    "
                    :hint="`L1 规则通过率 ${summary.l1_pass_rate != null ? Math.round(summary.l1_pass_rate * 100) : 0}%`"
                    icon="shield"
                    tone="success"
                  />
                  <MetricCard
                    label="TTFT 首字延迟 P50"
                    :value="
                      summary.ttft_ms?.p50 != null
                        ? `${summary.ttft_ms.p50} ms`
                        : '-'
                    "
                    :hint="`P95: ${summary.ttft_ms?.p95 ?? '-'} ms`"
                    icon="activity"
                    tone="primary"
                  />
                  <MetricCard
                    label="死循环率"
                    :value="
                      summary.loop_rate != null
                        ? `${Math.round(summary.loop_rate * 100)}%`
                        : '0%'
                    "
                    hint="Trace 信号检测"
                    icon="overview"
                    tone="warning"
                  />
                  <MetricCard
                    label="异常分层"
                    :value="`${summary.error_breakdown?.fail ?? 0} 错 / ${summary.error_breakdown?.runtime_error ?? 0} 故障`"
                    :hint="`裁判异常 ${summary.error_breakdown?.eval_error ?? 0}`"
                    icon="alert"
                    tone="primary"
                  />
                </section>

                <div class="space-y-2">
                  <div
                    v-for="rc in runCases"
                    :key="rc.id"
                    class="rounded-lg border border-gray-200 dark:border-dark-700 overflow-hidden text-xs bg-white dark:bg-dark-800"
                  >
                    <div
                      class="p-3 flex flex-wrap items-center justify-between gap-3"
                    >
                      <div class="flex flex-wrap items-center gap-2">
                        <span class="font-mono font-semibold">{{
                          rc.case_key
                        }}</span>
                        <span class="text-gray-400">#{{ rc.attempt_idx }}</span>
                        <StatusPill :tone="statusTone(rc.status)">{{
                          rc.status
                        }}</StatusPill>
                        <span
                          v-if="rc.overall_score != null"
                          class="font-semibold"
                        >
                          得分 {{ Math.round(rc.overall_score * 100) }}%
                        </span>
                        <span v-if="rc.ttft_ms != null" class="text-gray-500"
                          >TTFT {{ rc.ttft_ms }} ms</span
                        >
                        <span
                          v-if="rc.duration_ms != null"
                          class="text-gray-500"
                          >耗时 {{ rc.duration_ms }} ms</span
                        >
                        <span
                          v-if="
                            rc.error_category && rc.error_category !== 'none'
                          "
                          class="text-rose-500"
                        >
                          异常: {{ rc.error_category }}
                        </span>
                      </div>

                      <div class="flex flex-wrap items-center gap-1.5">
                        <BaseButton
                          v-if="rc.thread_id || rc.trace_ids?.length"
                          size="sm"
                          variant="secondary"
                          @click="
                            openMlflowTrace(rc, activeRun.target_project_id)
                          "
                        >
                          MLflow Trace ↗
                        </BaseButton>
                        <BaseButton
                          size="sm"
                          variant="secondary"
                          @click="
                            expandedCaseId =
                              expandedCaseId === rc.id ? null : rc.id
                          "
                        >
                          {{
                            expandedCaseId === rc.id
                              ? "收起白盒详情"
                              : "白盒证据详情"
                          }}
                        </BaseButton>
                      </div>
                    </div>

                    <div
                      v-if="expandedCaseId === rc.id"
                      class="p-3 bg-gray-50 dark:bg-dark-800/50 border-t border-gray-100 dark:border-dark-700 space-y-3"
                    >
                      <div class="grid gap-3 md:grid-cols-2">
                        <div class="space-y-1">
                          <div
                            class="font-semibold text-gray-600 dark:text-dark-300"
                          >
                            实际回复与多轮博弈对话流水
                          </div>
                          <div
                            class="p-2.5 rounded bg-white dark:bg-dark-900 border border-gray-200/70 dark:border-dark-700 whitespace-pre-wrap max-h-56 overflow-y-auto space-y-2"
                          >
                            <div
                              v-if="caseTranscript(rc).length"
                              class="space-y-1.5 border-b border-gray-100 dark:border-dark-800 pb-2"
                            >
                              <div
                                v-for="(turn, idx) in caseTranscript(rc)"
                                :key="idx"
                                class="text-[11px]"
                              >
                                <span
                                  class="font-mono font-semibold text-primary-600"
                                >
                                  [{{ turn.role }}]
                                </span>
                                <span>{{
                                  String(turn.content || "").slice(0, 400)
                                }}</span>
                              </div>
                            </div>
                            <div>
                              {{
                                (rc.results as any)?.final_answer ||
                                "尚无输出正文"
                              }}
                            </div>
                          </div>
                        </div>
                        <div class="space-y-1">
                          <div
                            class="font-semibold text-gray-600 dark:text-dark-300"
                          >
                            分级打分与裁判理由 (L1 + L2)
                          </div>
                          <div class="space-y-1.5 max-h-56 overflow-y-auto">
                            <div
                              v-for="m in caseMetrics(rc)"
                              :key="String(m.name)"
                              class="p-2 rounded bg-white dark:bg-dark-900 border border-gray-200/70 dark:border-dark-700 flex items-start justify-between gap-2"
                            >
                              <div>
                                <span class="font-mono font-semibold"
                                  >[{{ m.layer }}] {{ m.name }}</span
                                >
                                <p
                                  v-if="m.reason"
                                  class="text-[11px] text-gray-500 mt-0.5"
                                >
                                  {{ m.reason }}
                                </p>
                              </div>
                              <StatusPill
                                :tone="m.passed ? 'success' : 'danger'"
                              >
                                {{
                                  `${m.passed ? "PASS" : "FAIL"} (${m.score ?? "-"})`
                                }}
                              </StatusPill>
                            </div>
                          </div>
                        </div>
                      </div>

                      <div
                        v-if="
                          Array.isArray((rc.results as any)?.tool_events) &&
                          (rc.results as any).tool_events.length
                        "
                        class="p-2.5 rounded bg-white dark:bg-dark-900 border border-gray-200/70 dark:border-dark-700 space-y-1.5"
                      >
                        <div
                          class="font-semibold text-gray-600 dark:text-dark-300"
                        >
                          白盒工具调用链 ({{
                            (rc.results as any).tool_events.length
                          }}
                          步)
                        </div>
                        <div class="flex flex-wrap gap-1.5">
                          <span
                            v-for="(te, tidx) in (rc.results as any)
                              .tool_events"
                            :key="tidx"
                            class="px-2 py-0.5 rounded border font-mono text-[11px]"
                            :class="
                              te.status === 'executed'
                                ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
                                : te.status === 'blocked'
                                  ? 'bg-amber-50 border-amber-200 text-amber-700'
                                  : 'bg-rose-50 border-rose-200 text-rose-700'
                            "
                          >
                            {{ te.name }} [{{ te.status }}]
                          </span>
                        </div>
                      </div>

                      <div
                        v-if="(rc.results as any)?.simulation"
                        class="p-2.5 rounded bg-indigo-50/40 dark:bg-indigo-950/20 border border-indigo-200/70 dark:border-indigo-900/50 space-y-1 text-[11px]"
                      >
                        <div
                          class="font-semibold text-indigo-700 dark:text-indigo-300"
                        >
                          动态博弈与中断协商轴 (user_mode={{
                            (rc.results as any).simulation.user_mode
                          }}
                          · 停机原因={{
                            (rc.results as any).simulation.stop_reason
                          }})
                        </div>
                        <div class="text-gray-600 dark:text-dark-300 font-mono">
                          澄清表单
                          {{
                            (
                              (rc.results as any).simulation
                                .clarification_rounds || []
                            ).length
                          }}
                          轮 · Plan 审阅
                          {{
                            (
                              (rc.results as any).simulation
                                .plan_review_rounds || []
                            ).length
                          }}
                          轮 · 工具审批
                          {{
                            (
                              (rc.results as any).simulation
                                .approval_decisions || []
                            ).length
                          }}
                          次 · 延迟夹具
                          {{
                            (
                              (rc.results as any).simulation
                                .injected_fixtures || []
                            ).length
                          }}
                          批 · 事实披露
                          {{
                            (
                              (rc.results as any).simulation.disclosed_events ||
                              []
                            ).length
                          }}
                          条
                        </div>
                      </div>

                      <div
                        class="flex flex-wrap items-center justify-end gap-2 pt-2 border-t border-gray-200/70 dark:border-dark-700"
                      >
                        <span class="text-gray-500">L3 人工抽检标定:</span>
                        <div class="w-56">
                          <BaseInput
                            :model-value="reviewNotes[rc.id] ?? ''"
                            placeholder="填写人工复核说明..."
                            @update:model-value="
                              (v) => (reviewNotes[rc.id] = v)
                            "
                          />
                        </div>
                        <BaseButton
                          size="sm"
                          variant="secondary"
                          @click="
                            emit(
                              'review',
                              rc.id,
                              'pass',
                              reviewNotes[rc.id] ?? '',
                            )
                          "
                        >
                          标为通过
                        </BaseButton>
                        <BaseButton
                          size="sm"
                          variant="danger"
                          @click="
                            emit(
                              'review',
                              rc.id,
                              'fail',
                              reviewNotes[rc.id] ?? '',
                            )
                          "
                        >
                          标为失败
                        </BaseButton>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </template>
          </div>
        </div>
      </div>
    </SurfaceCard>
  </div>
</template>

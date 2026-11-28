<script setup lang="ts">
import { computed, ref, watch } from "vue";
import BaseButton from "@/components/base/BaseButton.vue";
import SurfaceCard from "@/components/base/SurfaceCard.vue";
import EmptyState from "@/components/platform/EmptyState.vue";
import MetricCard from "@/components/platform/MetricCard.vue";
import StatusPill from "@/components/platform/StatusPill.vue";
import RunEvidenceDetail from "@/modules/evaluation/components/RunEvidenceDetail.vue";
import type {
  EvalRunCaseItem,
  EvalRunItem,
  EvalRunProgress,
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
  deleteRun: [run: EvalRunItem];
  openLogs: [run: EvalRunItem];
  openSuiteHistory: [suiteId: string, suiteName: string, items: EvalRunItem[]];
}>();

const selectedCompareIds = ref<string[]>([]);
const expandedSuites = ref<Record<string, boolean>>({});
const expandedRunId = ref<string | null>(props.activeRun?.id ?? null);

watch(
  () => props.activeRun?.id,
  (newId) => {
    if (newId) {
      expandedRunId.value = newId;
    } else if (!props.runs.some((r) => r.id === expandedRunId.value)) {
      expandedRunId.value = null;
    }
  },
  { immediate: true },
);

watch(
  () => props.runs,
  (rows) => {
    const existing = new Set(rows.map((r) => r.id));
    selectedCompareIds.value = selectedCompareIds.value.filter((id) =>
      existing.has(id),
    );
  },
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

function runScore(r: EvalRunItem): number | null {
  const m = r.summary_metrics as Record<string, unknown> | undefined;
  const val = m?.overall_score ?? m?.tsr_pass_at_1;
  return typeof val === "number" ? val : null;
}

function runProgress(r: EvalRunItem): EvalRunProgress {
  const m = r.summary_metrics as Record<string, any> | undefined;
  const p = m?.progress as Partial<EvalRunProgress> | undefined;
  if (p && typeof p.total === "number") {
    return {
      total: p.total,
      active_total: p.active_total ?? p.total,
      done: p.done ?? 0,
      completed: p.completed ?? 0,
      failed: p.failed ?? 0,
      error: p.error ?? 0,
      running: p.running ?? 0,
      pending: p.pending ?? 0,
      paused: p.paused ?? 0,
      cancelled: p.cancelled ?? 0,
      skipped_incompatible: p.skipped_incompatible ?? 0,
      percent: p.percent ?? 0,
    };
  }
  const total = typeof m?.total_cases === "number" ? m.total_cases : 0;
  return {
    total,
    active_total: total,
    done: 0,
    completed: 0,
    failed: 0,
    error: 0,
    running: 0,
    pending: total,
    paused: 0,
    cancelled: 0,
    skipped_incompatible: 0,
    percent: 0,
  };
}

function latestLogLine(r: EvalRunItem): string | null {
  const arr = (r.summary_metrics as Record<string, any> | undefined)
    ?.recent_logs;
  if (Array.isArray(arr) && arr.length > 0) {
    return String(arr[arr.length - 1]);
  }
  return null;
}

const inFlightStatuses = new Set(["queued", "running", "rescoring", "paused"]);

const inFlightRuns = computed(() =>
  props.runs
    .filter((r) => inFlightStatuses.has(r.status))
    .sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? "")),
);

const historyRuns = computed(() =>
  props.runs.filter((r) => !inFlightStatuses.has(r.status)),
);

const runningCount = computed(
  () =>
    props.runs.filter(
      (r) =>
        r.status === "running" ||
        r.status === "queued" ||
        r.status === "rescoring",
    ).length,
);

const averageScore = computed(() => {
  const vals = historyRuns.value
    .map(runScore)
    .filter((v): v is number => v !== null);
  if (!vals.length) return "-";
  return `${Math.round((vals.reduce((a, b) => a + b, 0) / vals.length) * 100)}%`;
});

const bestPassRate = computed(() => {
  const vals = historyRuns.value
    .map((r) => (r.summary_metrics as Record<string, unknown>)?.tsr_pass_at_1)
    .filter((v): v is number => typeof v === "number");
  if (!vals.length) return "0%";
  return `${Math.round(Math.max(...vals) * 100)}%`;
});

const groupedRuns = computed(() => {
  const suiteNameById = new Map(props.suites.map((s) => [s.id, s.name]));
  const map = new Map<string, EvalRunItem[]>();
  for (const run of historyRuns.value) {
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
  if (historyRuns.value.length >= 2) {
    const sorted = [...historyRuns.value].sort((a, b) =>
      (b.created_at ?? "").localeCompare(a.created_at ?? ""),
    );
    emit("compare", sorted[1].id, sorted[0].id);
  }
}

function quickCompareRun(run: EvalRunItem, groupItems: EvalRunItem[]) {
  const peer =
    groupItems.find((item) => item.id !== run.id) ??
    historyRuns.value.find((item) => item.id !== run.id);
  if (peer) {
    emit("compare", peer.id, run.id);
  } else {
    emit("compare", run.id, run.id);
  }
}

function statusTone(status: string) {
  if (status === "completed" || status === "success") return "success";
  if (status === "failed" || status === "error" || status === "cancelled")
    return "danger";
  if (status === "running" || status === "queued" || status === "rescoring")
    return "info";
  return "warning";
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

    <!-- 模块 1：正在进行的打擂队列 (Active Running Queue) -->
    <SurfaceCard v-if="inFlightRuns.length" class="p-4 space-y-3">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <span class="size-2 rounded-full bg-amber-500 animate-ping" />
          <h3 class="text-sm font-semibold">
            正在进行的打擂队列 ({{ inFlightRuns.length }})
          </h3>
        </div>
        <span class="text-xs text-gray-500">
          支持实时进度追踪、Case 完成度核查与终端日志流
        </span>
      </div>

      <div class="space-y-3">
        <div
          v-for="r in inFlightRuns"
          :key="r.id"
          class="rounded-xl border border-amber-300/60 dark:border-amber-700/50 bg-amber-50/20 dark:bg-amber-950/10 overflow-hidden"
        >
          <div class="h-1 w-full bg-amber-100 dark:bg-dark-800">
            <div
              class="h-full bg-amber-500 transition-all duration-300"
              :style="{ width: `${runProgress(r).percent}%` }"
            />
          </div>

          <div class="p-3.5 space-y-2.5 text-xs">
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div class="space-y-1">
                <div class="flex flex-wrap items-center gap-2">
                  <span class="font-mono font-semibold text-sm">
                    打擂 #{{ r.id.slice(0, 8) }}
                  </span>
                  <StatusPill :tone="statusTone(r.status)">
                    {{ r.status }} · {{ runProgress(r).percent }}%
                  </StatusPill>
                  <StatusPill tone="neutral">{{
                    r.target_graph_id
                  }}</StatusPill>
                  <span
                    v-if="r.suite_name"
                    class="font-medium text-gray-700 dark:text-dark-200"
                  >
                    {{ r.suite_name }}
                  </span>
                </div>
                <div class="text-[11px] text-gray-500 font-mono">
                  已完成 {{ runProgress(r).done }}/{{
                    runProgress(r).active_total ?? runProgress(r).total
                  }}
                  题 · 执行中 {{ runProgress(r).running }} · 待执行
                  {{ runProgress(r).pending }} · 失败/异常
                  {{ runProgress(r).failed + runProgress(r).error }} · 并发
                  {{ r.concurrency }}
                </div>
              </div>

              <div class="flex flex-wrap items-center gap-1.5">
                <BaseButton
                  size="sm"
                  variant="secondary"
                  @click="emit('openLogs', r)"
                >
                  📋 实时日志
                </BaseButton>
                <BaseButton
                  size="sm"
                  :variant="isRunExpanded(r.id) ? 'primary' : 'secondary'"
                  @click="toggleRunEvidence(r.id)"
                >
                  {{ isRunExpanded(r.id) ? "收起详情 ▲" : "进度详情 ▼" }}
                </BaseButton>
                <BaseButton
                  v-if="r.status === 'running' || r.status === 'queued'"
                  size="sm"
                  variant="secondary"
                  @click="emit('control', r.id, 'pause')"
                >
                  ⏸ 暂停
                </BaseButton>
                <BaseButton
                  v-if="r.status === 'paused'"
                  size="sm"
                  variant="secondary"
                  @click="emit('control', r.id, 'resume')"
                >
                  ▶ 继续
                </BaseButton>
                <BaseButton
                  v-if="r.status !== 'rescoring'"
                  size="sm"
                  variant="danger"
                  @click="emit('control', r.id, 'cancel')"
                >
                  中止
                </BaseButton>
                <BaseButton
                  v-if="r.status === 'paused'"
                  size="sm"
                  variant="danger"
                  @click="emit('deleteRun', r)"
                >
                  🗑 删除
                </BaseButton>
              </div>
            </div>

            <div
              class="h-1.5 w-full rounded-full bg-gray-200 dark:bg-dark-700 overflow-hidden"
            >
              <div
                class="h-full bg-primary-600 transition-all duration-300"
                :style="{ width: `${runProgress(r).percent}%` }"
              />
            </div>

            <div
              v-if="latestLogLine(r)"
              class="px-2.5 py-1.5 rounded bg-slate-900/90 text-slate-200 font-mono text-[11px] truncate"
            >
              &gt; {{ latestLogLine(r) }}
            </div>
          </div>

          <RunEvidenceDetail
            v-if="isRunExpanded(r.id) && activeRun"
            :active-run="activeRun"
            :run-cases="runCases"
            @collapse="toggleRunEvidence(r.id)"
            @control="(id, action) => emit('control', id, action)"
            @review="
              (rcId, verdict, reason) => emit('review', rcId, verdict, reason)
            "
            @open-diagnosis="(id) => emit('openDiagnosis', id)"
            @open-logs="(targetRun) => emit('openLogs', targetRun)"
          />
        </div>
      </div>
    </SurfaceCard>

    <!-- 模块 2：历史打擂成果归档 -->
    <SurfaceCard class="p-4 space-y-3">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 class="text-sm font-semibold">
            历史打擂成果归档 ({{ groupedRuns.length }} 个评测集)
          </h3>
          <p class="text-xs text-gray-500">
            按评测集聚合历史最高分、各指标趋势对比与逐题取证（支持删除无效记录、查看实时日志或勾选两场横向
            PK）
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
            :disabled="
              selectedCompareIds.length !== 2 && historyRuns.length < 2
            "
            @click="triggerCompare"
          >
            {{
              selectedCompareIds.length === 2
                ? "横向对撞已选 2 场 PK"
                : historyRuns.length >= 2
                  ? "对比最近两场 PK"
                  : `横向跨场次对撞 PK (${selectedCompareIds.length}/2)`
            }}
          </BaseButton>
        </div>
      </div>

      <EmptyState
        v-if="!groupedRuns.length"
        title="尚无已归档评测记录"
        description="请从“题库资产全景”或“考题表格汇总”点击“发起评测打擂”启动并发评测，运行完成后将在此归档。"
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
              <BaseButton
                size="sm"
                variant="secondary"
                @click="
                  emit(
                    'openSuiteHistory',
                    group.suiteId,
                    group.suiteName,
                    group.items,
                  )
                "
              >
                📊 历史指标对比
              </BaseButton>
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
                    <div class="flex flex-wrap items-center gap-2">
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
                        v-if="run.version_num"
                        class="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-dark-700 font-mono text-[10px]"
                      >
                        v{{ run.version_num }}
                      </span>
                      <span v-if="run.target_model_name" class="text-gray-500">
                        {{ run.target_model_name }}
                      </span>
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

                <div class="flex flex-wrap items-center gap-2">
                  <div class="text-right font-mono mr-1">
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
                    @click="emit('openLogs', run)"
                  >
                    📋 日志
                  </BaseButton>
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
                    :disabled="historyRuns.length < 2"
                    @click="quickCompareRun(run, group.items)"
                  >
                    + 对比
                  </BaseButton>
                  <BaseButton
                    size="sm"
                    :variant="isRunExpanded(run.id) ? 'primary' : 'secondary'"
                    @click="toggleRunEvidence(run.id)"
                  >
                    {{ isRunExpanded(run.id) ? "收起取证 ▲" : "查看取证 ▼" }}
                  </BaseButton>
                  <BaseButton
                    size="sm"
                    variant="danger"
                    title="彻底删除此场评测结果"
                    @click="emit('deleteRun', run)"
                  >
                    🗑 删除
                  </BaseButton>
                </div>
              </div>

              <RunEvidenceDetail
                v-if="isRunExpanded(run.id) && activeRun"
                :active-run="activeRun"
                :run-cases="runCases"
                @collapse="toggleRunEvidence(run.id)"
                @control="(id, action) => emit('control', id, action)"
                @review="
                  (rcId, verdict, reason) =>
                    emit('review', rcId, verdict, reason)
                "
                @open-diagnosis="(id) => emit('openDiagnosis', id)"
                @open-logs="(targetRun) => emit('openLogs', targetRun)"
              />
            </template>
          </div>
        </div>
      </div>
    </SurfaceCard>
  </div>
</template>

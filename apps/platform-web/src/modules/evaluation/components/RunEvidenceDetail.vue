<script setup lang="ts">
import { computed, ref, watch } from "vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseInput from "@/components/base/BaseInput.vue";
import MetricCard from "@/components/platform/MetricCard.vue";
import StatusPill from "@/components/platform/StatusPill.vue";
import { buildMlflowTraceUrl } from "@/services/observability/langfuse-url";
import type {
  EvalRunCaseItem,
  EvalRunItem,
} from "@/services/evaluation/studio";

const props = defineProps<{
  activeRun: EvalRunItem;
  runCases: EvalRunCaseItem[];
}>();

const emit = defineEmits<{
  collapse: [];
  control: [
    runId: string,
    action: "pause" | "resume" | "retry_failed" | "rescore" | "cancel",
  ];
  review: [runCaseId: string, verdict: "pass" | "fail", reason: string];
  openDiagnosis: [runId: string];
  openLogs: [run: EvalRunItem];
}>();

type CaseStatusFilter = "all" | "running" | "pending" | "completed" | "issue";

const expandedCaseId = ref<string | null>(null);
const reviewNotes = ref<Record<string, string>>({});
const caseFilter = ref<CaseStatusFilter>("all");
const caseSearch = ref("");

watch(
  () => props.runCases,
  (cases) => {
    if (cases && cases.length === 1) {
      expandedCaseId.value = cases[0].id;
    }
  },
  { immediate: true },
);

const summary = computed(
  () => (props.activeRun.summary_metrics ?? {}) as Record<string, any>,
);

const caseCounts = computed(() => {
  const counts = {
    total: props.runCases.length,
    running: 0,
    pending: 0,
    completed: 0,
    issue: 0,
  };
  for (const rc of props.runCases) {
    if (rc.status === "running") counts.running += 1;
    else if (rc.status === "pending" || rc.status === "paused")
      counts.pending += 1;
    else if (rc.status === "completed") counts.completed += 1;
    else counts.issue += 1;
  }
  return counts;
});

const filteredRunCases = computed(() => {
  const kw = caseSearch.value.trim().toLowerCase();
  return props.runCases.filter((rc) => {
    if (caseFilter.value === "running" && rc.status !== "running") return false;
    if (
      caseFilter.value === "pending" &&
      rc.status !== "pending" &&
      rc.status !== "paused"
    )
      return false;
    if (caseFilter.value === "completed" && rc.status !== "completed")
      return false;
    if (
      caseFilter.value === "issue" &&
      ["running", "pending", "paused", "completed"].includes(rc.status)
    )
      return false;
    if (kw && !rc.case_key.toLowerCase().includes(kw)) return false;
    return true;
  });
});

function statusTone(status: string) {
  if (status === "completed" || status === "success") return "success";
  if (status === "failed" || status === "error" || status === "cancelled")
    return "danger";
  if (status === "running" || status === "queued" || status === "rescoring")
    return "info";
  return "warning";
}

function caseStatusLabel(status: string) {
  if (status === "running") return "执行中...";
  if (status === "pending") return "待执行";
  if (status === "completed") return "已完成";
  if (status === "failed") return "未达标";
  if (status === "error") return "异常";
  if (status === "paused") return "已暂停";
  if (status === "cancelled") return "已中止";
  if (status === "skipped_incompatible") return "不兼容跳过";
  return status;
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

function barPct(count: number) {
  if (!caseCounts.value.total) return "0%";
  return `${Math.round((count / caseCounts.value.total) * 1000) / 10}%`;
}
</script>

<template>
  <div
    class="p-4 bg-gray-50/80 dark:bg-dark-900/80 border-t border-b border-primary-200/50 dark:border-primary-900/40 space-y-4"
  >
    <div class="flex flex-wrap items-center justify-between gap-2">
      <div class="flex flex-wrap items-center gap-2">
        <h3 class="text-sm font-semibold">
          批次白盒取证 · #{{ activeRun.id.slice(0, 8) }}
        </h3>
        <StatusPill :tone="statusTone(activeRun.status)">{{
          activeRun.status
        }}</StatusPill>
        <span
          v-if="activeRun.version_num"
          class="px-1.5 py-0.5 rounded bg-gray-200/80 dark:bg-dark-700 font-mono text-[11px]"
        >
          v{{ activeRun.version_num }}
        </span>
        <span
          v-if="activeRun.target_model_name"
          class="text-xs text-gray-500 font-mono"
        >
          {{ activeRun.target_model_name }}
        </span>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <BaseButton
          size="sm"
          variant="ghost"
          class="text-gray-500 hover:text-gray-700 dark:hover:text-dark-200"
          @click="emit('collapse')"
        >
          收起取证 ▲
        </BaseButton>
        <BaseButton
          size="sm"
          variant="secondary"
          @click="emit('openLogs', activeRun)"
        >
          📋 实时日志
        </BaseButton>
        <BaseButton
          size="sm"
          variant="secondary"
          :disabled="
            activeRun.status !== 'running' && activeRun.status !== 'queued'
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
            activeRun.status === 'running' || activeRun.status === 'queued'
          "
          @click="emit('control', activeRun.id, 'retry_failed')"
        >
          仅重跑失败题
        </BaseButton>
        <BaseButton
          size="sm"
          variant="secondary"
          :disabled="
            activeRun.status === 'running' || activeRun.status === 'queued'
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
          summary.ttft_ms?.p50 != null ? `${summary.ttft_ms.p50} ms` : '-'
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

    <!-- 用例执行进度看板 (Case Progress Matrix) -->
    <div
      class="p-3 rounded-lg border border-gray-200 dark:border-dark-700 bg-white dark:bg-dark-800/80 space-y-2.5 text-xs"
    >
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div class="font-semibold text-gray-800 dark:text-dark-100">
          用例执行进度明细 ({{ caseCounts.completed + caseCounts.issue }}/{{
            caseCounts.total
          }}
          已收口 · {{ caseCounts.running }} 执行中 ·
          {{ caseCounts.pending }} 未开始)
        </div>
        <div class="w-48">
          <BaseInput v-model="caseSearch" placeholder="过滤 case_key..." />
        </div>
      </div>

      <div
        v-if="caseCounts.total > 0"
        class="h-2 w-full rounded-full bg-gray-100 dark:bg-dark-700 overflow-hidden flex"
      >
        <div
          class="bg-emerald-500 transition-all duration-300"
          :style="{ width: barPct(caseCounts.completed) }"
          title="已完成通过"
        />
        <div
          class="bg-rose-500 transition-all duration-300"
          :style="{ width: barPct(caseCounts.issue) }"
          title="未达标/异常/中止"
        />
        <div
          class="bg-sky-500 animate-pulse transition-all duration-300"
          :style="{ width: barPct(caseCounts.running) }"
          title="正在执行"
        />
      </div>

      <div class="flex flex-wrap items-center gap-1.5">
        <button
          v-for="tab in [
            { id: 'all', label: `全部 (${caseCounts.total})` },
            { id: 'running', label: `运行中 (${caseCounts.running})` },
            { id: 'pending', label: `待执行 (${caseCounts.pending})` },
            { id: 'completed', label: `已通过 (${caseCounts.completed})` },
            { id: 'issue', label: `未通过/异常 (${caseCounts.issue})` },
          ]"
          :key="tab.id"
          type="button"
          class="px-2.5 py-1 rounded-md border text-[11px] font-medium transition-colors"
          :class="
            caseFilter === tab.id
              ? 'bg-primary-600 border-primary-600 text-white'
              : 'border-gray-200 dark:border-dark-700 text-gray-600 dark:text-dark-300 hover:bg-gray-50 dark:hover:bg-dark-700'
          "
          @click="caseFilter = tab.id as CaseStatusFilter"
        >
          {{ tab.label }}
        </button>
      </div>
    </div>

    <div class="space-y-2">
      <div
        v-for="rc in filteredRunCases"
        :key="rc.id"
        class="rounded-lg border border-gray-200 dark:border-dark-700 overflow-hidden text-xs bg-white dark:bg-dark-800"
      >
        <div class="p-3 flex flex-wrap items-center justify-between gap-3">
          <div class="flex flex-wrap items-center gap-2">
            <span class="font-mono font-semibold">{{ rc.case_key }}</span>
            <span class="text-gray-400">#{{ rc.attempt_idx }}</span>
            <StatusPill :tone="statusTone(rc.status)">
              <span v-if="rc.status === 'running'" class="animate-pulse"
                >●
              </span>
              {{ caseStatusLabel(rc.status) }}
            </StatusPill>
            <span v-if="rc.overall_score != null" class="font-semibold">
              得分 {{ Math.round(rc.overall_score * 100) }}%
            </span>
            <span v-if="rc.ttft_ms != null" class="text-gray-500">
              TTFT {{ rc.ttft_ms }} ms
            </span>
            <span v-if="rc.duration_ms != null" class="text-gray-500">
              耗时 {{ rc.duration_ms }} ms
            </span>
            <span v-if="rc.status === 'pending'" class="text-gray-400 italic">
              排队等待执行槽位...
            </span>
            <span
              v-if="rc.error_category && rc.error_category !== 'none'"
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
              @click="openMlflowTrace(rc, activeRun.target_project_id)"
            >
              MLflow Trace ↗
            </BaseButton>
            <BaseButton
              size="sm"
              variant="secondary"
              @click="expandedCaseId = expandedCaseId === rc.id ? null : rc.id"
            >
              {{ expandedCaseId === rc.id ? "收起白盒详情" : "白盒证据详情" }}
            </BaseButton>
          </div>
        </div>

        <div
          v-if="expandedCaseId === rc.id"
          class="p-3 bg-gray-50 dark:bg-dark-800/50 border-t border-gray-100 dark:border-dark-700 space-y-3"
        >
          <div class="grid gap-3 md:grid-cols-2">
            <div class="space-y-1">
              <div class="font-semibold text-gray-600 dark:text-dark-300">
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
                    <span class="font-mono font-semibold text-primary-600">
                      [{{ turn.role }}]
                    </span>
                    <span>{{ String(turn.content || "").slice(0, 400) }}</span>
                  </div>
                </div>
                <div>
                  {{ (rc.results as any)?.final_answer || "尚无输出正文" }}
                </div>
              </div>
            </div>
            <div class="space-y-1">
              <div class="font-semibold text-gray-600 dark:text-dark-300">
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
                    <p v-if="m.reason" class="text-[11px] text-gray-500 mt-0.5">
                      {{ m.reason }}
                    </p>
                  </div>
                  <StatusPill :tone="m.passed ? 'success' : 'danger'">
                    {{ `${m.passed ? "PASS" : "FAIL"} (${m.score ?? "-"})` }}
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
            <div class="font-semibold text-gray-600 dark:text-dark-300">
              白盒工具调用链 ({{ (rc.results as any).tool_events.length }} 步)
            </div>
            <div class="flex flex-wrap gap-1.5">
              <span
                v-for="(te, tidx) in (rc.results as any).tool_events"
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
            <div class="font-semibold text-indigo-700 dark:text-indigo-300">
              动态博弈与中断协商轴 (user_mode={{
                (rc.results as any).simulation.user_mode
              }}
              · 停机原因={{ (rc.results as any).simulation.stop_reason }})
            </div>
            <div class="text-gray-600 dark:text-dark-300 font-mono">
              澄清表单
              {{
                ((rc.results as any).simulation.clarification_rounds || [])
                  .length
              }}
              轮 · Plan 审阅
              {{
                ((rc.results as any).simulation.plan_review_rounds || []).length
              }}
              轮 · 工具审批
              {{
                ((rc.results as any).simulation.approval_decisions || []).length
              }}
              次 · 延迟夹具
              {{
                ((rc.results as any).simulation.injected_fixtures || []).length
              }}
              批 · 事实披露
              {{
                ((rc.results as any).simulation.disclosed_events || []).length
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
                @update:model-value="(v) => (reviewNotes[rc.id] = v)"
              />
            </div>
            <BaseButton
              size="sm"
              variant="secondary"
              @click="emit('review', rc.id, 'pass', reviewNotes[rc.id] ?? '')"
            >
              标为通过
            </BaseButton>
            <BaseButton
              size="sm"
              variant="danger"
              @click="emit('review', rc.id, 'fail', reviewNotes[rc.id] ?? '')"
            >
              标为失败
            </BaseButton>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

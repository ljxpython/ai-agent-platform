<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { getActivePinia } from "pinia";
import { useRoute, useRouter } from "vue-router";
import BaseButton from "@/components/base/BaseButton.vue";
import ConfirmDialog from "@/components/base/ConfirmDialog.vue";
import PageHeader from "@/components/layout/PageHeader.vue";
import StateBanner from "@/components/platform/StateBanner.vue";
import { useAuthorization } from "@/composables/useAuthorization";
import CaseEditorPanel from "@/modules/evaluation/components/CaseEditorPanel.vue";
import ComparisonPkDialog from "@/modules/evaluation/components/ComparisonPkDialog.vue";
import DatasetPanoramaPanel from "@/modules/evaluation/components/DatasetPanoramaPanel.vue";
import EvaluationExpertDrawer from "@/modules/evaluation/components/EvaluationExpertDrawer.vue";
import LaunchRunModal from "@/modules/evaluation/components/LaunchRunModal.vue";
import PatrolScheduleModal from "@/modules/evaluation/components/PatrolScheduleModal.vue";
import PatrolSchedulesPanel from "@/modules/evaluation/components/PatrolSchedulesPanel.vue";
import RunLogTerminalDialog from "@/modules/evaluation/components/RunLogTerminalDialog.vue";
import RunResultsPanel from "@/modules/evaluation/components/RunResultsPanel.vue";
import SuiteHistoryMetricsDialog from "@/modules/evaluation/components/SuiteHistoryMetricsDialog.vue";
import { useEvaluationStudio } from "@/modules/evaluation/composables/useEvaluationStudio";
import { env } from "@/config/env";
import { listAgents } from "@/services/agents/agents.service";
import {
  isFaultInjectionTestModel,
  pickPreferredDeepSeekModelId,
  type CaseUpsertPayload,
  type EvalRunItem,
  type EvalSuiteItem,
  type PatrolCreatePayload,
  type PatrolScheduleItem,
  type PatrolUpdatePayload,
} from "@/services/evaluation/studio";
import { listRuntimeProjects } from "@/services/projects/projects.service";
import { listRuntimeModels } from "@/services/runtime/runtime.service";
import type { RuntimeModelItem } from "@/types/management";

type EvalTab = "panorama" | "editor" | "runs" | "patrols";

const route = useRoute();
const router = useRouter();
const projectId = computed(() => String(route.params.projectId || ""));
const authorization = getActivePinia() ? useAuthorization() : null;
const canManagePatrols = computed(() =>
  authorization
    ? authorization.can("project.evaluation.manage", projectId.value)
    : true,
);
const studio = useEvaluationStudio(projectId);

const activeTab = ref<EvalTab>("panorama");
const showLaunchModal = ref(false);
const showPkModal = ref(false);
const showExpertDrawer = ref(false);
const expertKind = ref<"eval_copilot" | "eval_diagnosis">("eval_copilot");
const expertRefId = ref("");
const modalSubmitError = ref("");

const projectOptions = ref<Array<{ label: string; value: string }>>([]);
const agentOptions = ref<Array<{ label: string; value: string }>>([]);
const modelOptions = ref<
  Array<{ label: string; value: string; isBroken?: boolean }>
>([]);
const runtimeModels = ref<RuntimeModelItem[]>([]);
const defaultModelId = ref("");
const selectedCaseKeys = ref<string[]>([]);
const logTerminalRun = ref<EvalRunItem | null>(null);
const showLogDialog = ref(false);
const deleteConfirmRun = ref<EvalRunItem | null>(null);
const showPatrolModal = ref(false);
const editingPatrol = ref<PatrolScheduleItem | null>(null);
const patrolModalError = ref("");
const deleteConfirmPatrol = ref<PatrolScheduleItem | null>(null);
const showHistoryDialog = ref(false);
const historySuiteName = ref("");
const historySuiteRuns = ref<EvalRunItem[]>([]);

let pollTimer: ReturnType<typeof setInterval> | null = null;

watch(
  () => studio.activeSuite.value?.id,
  () => {
    selectedCaseKeys.value = [];
  },
);

function syncTabFromRoute() {
  const metaTab = route.meta?.evalTab as EvalTab | undefined;
  if (metaTab) {
    activeTab.value = metaTab;
  }
}

watch(
  () => route.meta?.evalTab,
  () => syncTabFromRoute(),
  { immediate: true },
);

watch(
  () => activeTab.value,
  async (tab) => {
    if (
      tab === "editor" &&
      !studio.activeSuite.value &&
      studio.suites.value.length > 0
    ) {
      await studio.openSuite(studio.suites.value[0].id);
    }
    if (
      tab === "runs" &&
      !studio.activeRun.value &&
      studio.runs.value.length > 0
    ) {
      await studio.openRun(studio.runs.value[0].id);
    }
  },
);

const hasInFlightRun = computed(() =>
  studio.runs.value.some(
    (r) =>
      r.status === "queued" ||
      r.status === "running" ||
      r.status === "rescoring",
  ),
);

watch(hasInFlightRun, (active) => {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
  if (active) {
    pollTimer = setInterval(() => {
      void studio.pollRunningRuns();
    }, 2500);
  }
});

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer);
});

async function loadTargetOptions(targetPid: string) {
  if (!targetPid) return;
  try {
    const [agentPage, modelsRes] = await Promise.all([
      listAgents(targetPid, { limit: 100 }),
      listRuntimeModels(targetPid),
    ]);
    agentOptions.value = (agentPage.items ?? []).map((a) => ({
      label: `${a.name} (${a.graph_id})`,
      value: a.id,
    }));
    const models = modelsRes.models ?? [];
    defaultModelId.value = pickPreferredDeepSeekModelId(models);
    runtimeModels.value = models.filter(
      (m) => m.enabled && !isFaultInjectionTestModel(m),
    );
    modelOptions.value = models
      .filter((m) => m.enabled)
      .map((m) => ({
        label: `[${m.provider}] ${m.display_name} (${m.model})`,
        value: m.id,
        isBroken: isFaultInjectionTestModel(m),
      }));
  } catch {
    agentOptions.value = [];
  }
}

onMounted(async () => {
  syncTabFromRoute();
  await studio.refreshAll();
  try {
    const projects = await listRuntimeProjects();
    projectOptions.value = projects.map((p) => ({
      label: `${p.name} (${p.id.slice(0, 8)})`,
      value: p.id,
    }));
  } catch {
    if (projectId.value) {
      projectOptions.value = [
        {
          label: `当前项目 (${projectId.value.slice(0, 8)})`,
          value: projectId.value,
        },
      ];
    }
  }
  await loadTargetOptions(projectId.value);
  const itemId = String(route.params.itemId || "");
  const queryRunId = String(route.query?.runId || "");
  if (itemId) {
    await studio.openSuite(itemId);
    activeTab.value = "editor";
  } else if (activeTab.value === "editor" && studio.suites.value.length > 0) {
    await studio.openSuite(studio.suites.value[0].id);
  } else if (activeTab.value === "runs" && queryRunId) {
    await studio.openRun(queryRunId);
  } else if (activeTab.value === "runs" && studio.runs.value.length > 0) {
    await studio.openRun(studio.runs.value[0].id);
  }
});

function switchTab(tab: EvalTab) {
  activeTab.value = tab;
  const routeNames: Record<EvalTab, string> = {
    panorama: "workspace-evaluation",
    editor: "workspace-evaluation-cases",
    runs: "workspace-evaluation-runs",
    patrols: "workspace-evaluation-patrols",
  };
  void router?.push?.({
    name: routeNames[tab],
    params: { projectId: projectId.value },
  });
}

async function handleOpenSuite(suiteId: string) {
  await studio.openSuite(suiteId);
  activeTab.value = "editor";
}

async function handleLaunchModal(suite: EvalSuiteItem) {
  modalSubmitError.value = "";
  await studio.openSuite(suite.id);
  showLaunchModal.value = true;
}

async function handleRerunBySuiteId(suiteId: string) {
  const suite = studio.suites.value.find((s) => s.id === suiteId);
  if (suite) {
    await handleLaunchModal(suite);
  }
}

async function handleLaunchSubmit(
  payload: Parameters<typeof studio.launchRun>[0],
) {
  modalSubmitError.value = "";
  const created = await studio.launchRun(payload);
  if (!created) {
    modalSubmitError.value = studio.error.value || "发起评测失败";
    return;
  }
  showLaunchModal.value = false;
  switchTab("runs");
}

async function handleMatrixSubmit(
  payload: Parameters<typeof studio.launchMatrixRun>[0],
) {
  modalSubmitError.value = "";
  const created = await studio.launchMatrixRun(payload);
  if (!created) {
    modalSubmitError.value = studio.error.value || "发起矩阵打擂失败";
    return;
  }
  showLaunchModal.value = false;
  switchTab("runs");
}

async function handleCompare(baselineId: string, candidateId: string) {
  const res = await studio.loadComparison(baselineId, candidateId);
  if (res) {
    showHistoryDialog.value = false;
    showPkModal.value = true;
  }
}

function handleOpenRunLogs(run: EvalRunItem) {
  logTerminalRun.value = run;
  showLogDialog.value = true;
}

function handleOpenSuiteHistory(
  _suiteId: string,
  suiteName: string,
  items: EvalRunItem[],
) {
  historySuiteName.value = suiteName;
  historySuiteRuns.value = items;
  showHistoryDialog.value = true;
}

function handleRequestDeleteRun(run: EvalRunItem) {
  deleteConfirmRun.value = run;
}

async function confirmDeleteRun() {
  if (!deleteConfirmRun.value) return;
  const targetId = deleteConfirmRun.value.id;
  deleteConfirmRun.value = null;
  await studio.removeRun(targetId);
}

function handleOpenCreatePatrol() {
  patrolModalError.value = "";
  editingPatrol.value = null;
  showPatrolModal.value = true;
}

function handleOpenEditPatrol(item: PatrolScheduleItem) {
  patrolModalError.value = "";
  editingPatrol.value = item;
  showPatrolModal.value = true;
}

async function handleSavePatrol(
  payload: PatrolCreatePayload | PatrolUpdatePayload,
  editingId: string | null,
) {
  patrolModalError.value = "";
  const saved = editingId
    ? await studio.editPatrol(editingId, payload as PatrolUpdatePayload)
    : await studio.addPatrol(payload as PatrolCreatePayload);
  if (!saved) {
    patrolModalError.value = studio.error.value || "保存巡检配置失败";
    return;
  }
  showPatrolModal.value = false;
  editingPatrol.value = null;
}

async function handleTogglePatrol(item: PatrolScheduleItem) {
  await studio.editPatrol(item.id, { enabled: !item.enabled });
}

async function handleTriggerPatrol(item: PatrolScheduleItem) {
  const res = await studio.runPatrolNow(item.id);
  if (res?.run) {
    switchTab("runs");
  }
}

async function confirmDeletePatrol() {
  if (!deleteConfirmPatrol.value) return;
  const targetId = deleteConfirmPatrol.value.id;
  deleteConfirmPatrol.value = null;
  await studio.removePatrol(targetId);
}

async function handleViewPatrolRun(runId: string) {
  await studio.openRun(runId);
  switchTab("runs");
}

function handleExpertDrawer(
  kind: "eval_copilot" | "eval_diagnosis",
  refId: string,
) {
  expertKind.value = kind;
  expertRefId.value = refId;
  showExpertDrawer.value = true;
}

async function handleAdoptCopilotCases(items: CaseUpsertPayload[]) {
  if (!studio.activeSuite.value || !items.length) return;
  await studio.importCasesBatch(studio.activeSuite.value.id, items);
  showExpertDrawer.value = false;
}

async function handleExpertCasesUpdated() {
  if (studio.activeSuite.value) {
    await studio.openSuite(studio.activeSuite.value.id);
  }
  await studio.refreshAll();
}

async function handleExpertTrialRunUpdated() {
  await studio.refreshAll();
}

async function handleImportJsonlSuite(payload: {
  name: string;
  suite_type: EvalSuiteItem["suite_type"];
  default_graph_id: EvalSuiteItem["default_graph_id"];
  items: CaseUpsertPayload[];
}) {
  const created = await studio.addSuite({
    name: payload.name,
    description: `JSONL 导入 (${payload.items.length} 题)`,
    suite_type: payload.suite_type,
    default_graph_id: payload.default_graph_id,
  });
  if (created && payload.items.length) {
    await studio.importCasesBatch(created.id, payload.items);
    activeTab.value = "editor";
  }
}

async function handleConvertSessions(payload: {
  name: string;
  thread_ids: string[];
  source_project_id: string;
  default_graph_id: EvalSuiteItem["default_graph_id"];
}) {
  const detail = await studio.convertSessionsToSuite(payload);
  if (detail) activeTab.value = "editor";
}

function openMlflowDashboard() {
  const url = `${env.mlflowBaseUrl.replace(/\/+$/, "")}/#/experiments`;
  window.open(url, "_blank", "noopener");
}
</script>

<template>
  <div class="pw-page space-y-5">
    <PageHeader
      eyebrow="AI 评测中心"
      title="独立评测工坊与白盒诊断平台"
      description="支持题库血缘全景、内联高密度考题编辑、多图并发打擂 (1~5)、SSE 首字延迟 (TTFT) 实测与 7 维版本 PK。"
    >
      <template #actions>
        <div class="flex flex-wrap items-center gap-2">
          <BaseButton
            size="sm"
            :variant="activeTab === 'panorama' ? 'primary' : 'secondary'"
            @click="switchTab('panorama')"
          >
            题库资产全景
          </BaseButton>
          <BaseButton
            size="sm"
            :variant="activeTab === 'editor' ? 'primary' : 'secondary'"
            @click="switchTab('editor')"
          >
            考题表格汇总
          </BaseButton>
          <BaseButton
            size="sm"
            :variant="activeTab === 'runs' ? 'primary' : 'secondary'"
            @click="switchTab('runs')"
          >
            打擂任务大厅
          </BaseButton>
          <BaseButton
            size="sm"
            :variant="activeTab === 'patrols' ? 'primary' : 'secondary'"
            @click="switchTab('patrols')"
          >
            定时巡检
          </BaseButton>
          <BaseButton
            size="sm"
            variant="secondary"
            @click="openMlflowDashboard"
          >
            MLflow 大屏 ↗
          </BaseButton>
        </div>
      </template>
    </PageHeader>

    <StateBanner
      v-if="studio.error.value"
      variant="danger"
      title="评测服务操作异常"
      :description="studio.error.value"
      dismissible
      @close="studio.error.value = ''"
    />

    <StateBanner
      v-if="studio.notice.value"
      variant="success"
      title="操作已同步"
      :description="studio.notice.value"
      dismissible
      @close="studio.notice.value = ''"
    />

    <DatasetPanoramaPanel
      v-if="activeTab === 'panorama'"
      :project-id="projectId"
      :suites="studio.suites.value"
      :total-cases="studio.totalCasesCount.value"
      :published-count="studio.publishedSuitesCount.value"
      :runs-count="studio.runs.value.length"
      :agent-options="agentOptions"
      @open-suite="handleOpenSuite"
      @launch-suite="handleLaunchModal"
      @delete-suite="studio.removeSuite"
      @create-suite="studio.addSuite"
      @convert-sessions="handleConvertSessions"
      @import-jsonl-suite="handleImportJsonlSuite"
    />

    <CaseEditorPanel
      v-else-if="activeTab === 'editor'"
      :suites="studio.suites.value"
      :suite="studio.activeSuite.value"
      :cases="studio.suiteCases.value"
      :versions="studio.suiteVersions.value"
      :selected-case-keys="selectedCaseKeys"
      :busy="studio.busyAction.value"
      @update:selected-case-keys="(k) => (selectedCaseKeys = k)"
      @switch-suite="(id) => studio.openSuite(id)"
      @save-case="(p) => studio.saveCase(studio.activeSuite.value!.id, p)"
      @save-batch="
        (items) => studio.importCasesBatch(studio.activeSuite.value!.id, items)
      "
      @delete-case="(k) => studio.removeCase(studio.activeSuite.value!.id, k)"
      @publish-version="() => studio.publishSuite(studio.activeSuite.value!.id)"
      @launch-suite="handleLaunchModal"
      @open-copilot="
        () => handleExpertDrawer('eval_copilot', studio.activeSuite.value!.id)
      "
    />

    <PatrolSchedulesPanel
      v-else-if="activeTab === 'patrols'"
      :patrols="studio.patrols.value"
      :runs="studio.runs.value"
      :can-manage="canManagePatrols"
      :busy="studio.busyAction.value"
      @create="handleOpenCreatePatrol"
      @edit="handleOpenEditPatrol"
      @toggle-enabled="handleTogglePatrol"
      @trigger-now="handleTriggerPatrol"
      @delete="(item) => (deleteConfirmPatrol = item)"
      @view-run="handleViewPatrolRun"
    />

    <RunResultsPanel
      v-else
      :runs="studio.runs.value"
      :suites="studio.suites.value"
      :active-run="studio.activeRun.value"
      :run-cases="studio.runCases.value"
      @select-run="studio.openRun"
      @control="studio.sendRunControl"
      @compare="handleCompare"
      @review="studio.reviewCase"
      @rerun-suite="handleRerunBySuiteId"
      @toggle-sandbox="() => studio.toggleSandbox(true)"
      @open-diagnosis="(id) => handleExpertDrawer('eval_diagnosis', id)"
      @delete-run="handleRequestDeleteRun"
      @open-logs="handleOpenRunLogs"
      @open-suite-history="handleOpenSuiteHistory"
    />

    <PatrolScheduleModal
      :show="showPatrolModal"
      :project-id="projectId"
      :editing-patrol="editingPatrol"
      :suites="studio.suites.value"
      :project-options="projectOptions"
      :agent-options="agentOptions"
      :model-options="modelOptions"
      :default-model-id="defaultModelId"
      :submit-error="patrolModalError"
      :busy="studio.busyAction.value"
      :preview-cron="studio.checkPatrolCron"
      @close="showPatrolModal = false"
      @target-project-change="loadTargetOptions"
      @save="handleSavePatrol"
    />

    <ConfirmDialog
      :show="Boolean(deleteConfirmPatrol)"
      danger
      title="确认删除此定时巡检规则？"
      :message="
        deleteConfirmPatrol
          ? `即将删除巡检规则「${deleteConfirmPatrol.name}」。删除后将停止后续定时触发，但历史产生的巡检打擂记录会完整保留在大厅中。`
          : ''
      "
      confirm-text="确认删除"
      @confirm="confirmDeletePatrol"
      @cancel="deleteConfirmPatrol = null"
    />

    <ConfirmDialog
      :show="Boolean(deleteConfirmRun)"
      danger
      title="确认彻底删除此打擂结果？"
      :message="
        deleteConfirmRun
          ? `即将删除打擂 #${deleteConfirmRun.id.slice(0, 8)}（题库：${deleteConfirmRun.suite_name || deleteConfirmRun.suite_id.slice(0, 8)}，状态：${deleteConfirmRun.status}）。删除后将清除数据库中的评分、用例证据摘要、人工标定与执行日志，不可撤销。`
          : ''
      "
      confirm-text="彻底删除"
      @confirm="confirmDeleteRun"
      @cancel="deleteConfirmRun = null"
    />

    <RunLogTerminalDialog
      :show="showLogDialog"
      :run="logTerminalRun"
      :fetch-logs="studio.fetchRunLogs"
      @close="showLogDialog = false"
    />

    <SuiteHistoryMetricsDialog
      :show="showHistoryDialog"
      :suite-name="historySuiteName"
      :runs="historySuiteRuns"
      @close="showHistoryDialog = false"
      @compare-two="handleCompare"
    />

    <LaunchRunModal
      :show="showLaunchModal"
      :suite="studio.activeSuite.value"
      :versions="studio.suiteVersions.value"
      :project-options="projectOptions"
      :agent-options="agentOptions"
      :model-options="modelOptions"
      :default-model-id="defaultModelId"
      :readiness="studio.readiness.value"
      :readiness-loading="studio.readinessLoading.value"
      :readiness-error="studio.readinessError.value"
      :submit-error="modalSubmitError"
      :busy="studio.busyAction.value"
      :selected-case-keys="selectedCaseKeys"
      @close="showLaunchModal = false"
      @target-project-change="loadTargetOptions"
      @check-readiness="studio.runReadiness"
      @launch="handleLaunchSubmit"
      @launch-matrix="handleMatrixSubmit"
    />

    <ComparisonPkDialog
      :show="showPkModal"
      :comparison="studio.comparison.value"
      :runs="studio.runs.value"
      @close="showPkModal = false"
      @switch-compare="handleCompare"
    />

    <EvaluationExpertDrawer
      :show="showExpertDrawer"
      :project-id="projectId"
      :kind="expertKind"
      :ref-id="expertRefId"
      :default-model-id="defaultModelId"
      :model-options="modelOptions"
      :models="runtimeModels"
      @close="showExpertDrawer = false"
      @adopt-cases="handleAdoptCopilotCases"
      @cases-updated="handleExpertCasesUpdated"
      @trial-run-updated="handleExpertTrialRunUpdated"
    />
  </div>
</template>

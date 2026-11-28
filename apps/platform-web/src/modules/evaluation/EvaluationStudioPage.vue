<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import BaseButton from "@/components/base/BaseButton.vue";
import PageHeader from "@/components/layout/PageHeader.vue";
import StateBanner from "@/components/platform/StateBanner.vue";
import CaseEditorPanel from "@/modules/evaluation/components/CaseEditorPanel.vue";
import ComparisonPkDialog from "@/modules/evaluation/components/ComparisonPkDialog.vue";
import DatasetPanoramaPanel from "@/modules/evaluation/components/DatasetPanoramaPanel.vue";
import EvaluationExpertDrawer from "@/modules/evaluation/components/EvaluationExpertDrawer.vue";
import LaunchRunModal from "@/modules/evaluation/components/LaunchRunModal.vue";
import RunResultsPanel from "@/modules/evaluation/components/RunResultsPanel.vue";
import { useEvaluationStudio } from "@/modules/evaluation/composables/useEvaluationStudio";
import { env } from "@/config/env";
import { listAgents } from "@/services/agents/agents.service";
import {
  isFaultInjectionTestModel,
  pickPreferredDeepSeekModelId,
  type CaseUpsertPayload,
  type EvalSuiteItem,
} from "@/services/evaluation/studio";
import { listRuntimeProjects } from "@/services/projects/projects.service";
import { listRuntimeModels } from "@/services/runtime/runtime.service";
import type { RuntimeModelItem } from "@/types/management";

type EvalTab = "panorama" | "editor" | "runs";

const route = useRoute();
const router = useRouter();
const projectId = computed(() => String(route.params.projectId || ""));
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

let pollTimer: ReturnType<typeof setInterval> | null = null;

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
    (r) => r.status === "queued" || r.status === "running",
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
  if (itemId) {
    await studio.openSuite(itemId);
    activeTab.value = "editor";
  } else if (activeTab.value === "editor" && studio.suites.value.length > 0) {
    await studio.openSuite(studio.suites.value[0].id);
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
  activeTab.value = "runs";
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
  activeTab.value = "runs";
}

async function handleCompare(baselineId: string, candidateId: string) {
  const res = await studio.loadComparison(baselineId, candidateId);
  if (res) showPkModal.value = true;
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
      :busy="studio.busyAction.value"
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

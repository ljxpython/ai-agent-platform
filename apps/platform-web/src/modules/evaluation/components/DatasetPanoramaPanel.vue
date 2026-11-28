<script setup lang="ts">
import { computed, ref } from "vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseDialog from "@/components/base/BaseDialog.vue";
import BaseInput from "@/components/base/BaseInput.vue";
import BaseSelect from "@/components/base/BaseSelect.vue";
import SurfaceCard from "@/components/base/SurfaceCard.vue";
import EmptyState from "@/components/platform/EmptyState.vue";
import MetricCard from "@/components/platform/MetricCard.vue";
import StatusPill from "@/components/platform/StatusPill.vue";
import PickSessionMaterials from "@/modules/evaluation/components/PickSessionMaterials.vue";
import type {
  CaseUpsertPayload,
  EvalSuiteItem,
} from "@/services/evaluation/studio";

const props = defineProps<{
  projectId: string;
  suites: EvalSuiteItem[];
  totalCases: number;
  publishedCount: number;
  runsCount: number;
  agentOptions: Array<{ label: string; value: string }>;
}>();

const emit = defineEmits<{
  openSuite: [suiteId: string];
  launchSuite: [suite: EvalSuiteItem];
  deleteSuite: [suiteId: string];
  createSuite: [
    payload: {
      name: string;
      description: string;
      suite_type: EvalSuiteItem["suite_type"];
      default_graph_id: EvalSuiteItem["default_graph_id"];
    },
  ];
  convertSessions: [
    payload: {
      name: string;
      thread_ids: string[];
      source_project_id: string;
      default_graph_id: EvalSuiteItem["default_graph_id"];
    },
  ];
  importJsonlSuite: [
    payload: {
      name: string;
      suite_type: EvalSuiteItem["suite_type"];
      default_graph_id: EvalSuiteItem["default_graph_id"];
      items: CaseUpsertPayload[];
    },
  ];
}>();

const keyword = ref("");
const typeFilter = ref("all");
const scopeTab = ref<"all" | "project" | "benchmark">("all");
const expandedIds = ref<Record<string, boolean>>({});
const showCreateModal = ref(false);
const showPickSessions = ref(false);
const showSessionConfirmModal = ref(false);
const showImportModal = ref(false);

const selectedThreadIds = ref<string[]>([]);
const sessionSuiteName = ref("线上会话精选回归集");
const sessionPickAgentId = ref("");

const draftName = ref("");
const draftDesc = ref("");
const draftType = ref<EvalSuiteItem["suite_type"]>("curated");
const draftGraph = ref<EvalSuiteItem["default_graph_id"]>("dearflow_agent");

const importName = ref("JSONL 导入评测集");
const importText = ref("");
const importError = ref("");

const typeOptions = [
  { label: "全部类型", value: "all" },
  { label: "黄金集 (golden)", value: "golden" },
  { label: "回归集 (regression)", value: "regression" },
  { label: "精选集 (curated)", value: "curated" },
  { label: "基准集 (benchmark)", value: "benchmark" },
];

const graphOptions = [
  { label: "Dear Agent (dearflow_agent)", value: "dearflow_agent" },
  { label: "Python 示教 (showcase_demo)", value: "showcase_demo" },
  { label: "参考助手 (reference_agent)", value: "reference_agent" },
  { label: "标准工作流 (workflow_demo)", value: "workflow_demo" },
];

const filteredSuites = computed(() =>
  props.suites.filter((s) => {
    const matchScope =
      scopeTab.value === "all" ||
      (scopeTab.value === "benchmark" && s.suite_type === "benchmark") ||
      (scopeTab.value === "project" && s.suite_type !== "benchmark");
    const matchType =
      typeFilter.value === "all" || s.suite_type === typeFilter.value;
    const q = keyword.value.trim().toLowerCase();
    const matchText =
      !q ||
      s.name.toLowerCase().includes(q) ||
      s.description.toLowerCase().includes(q) ||
      (s.sample_cases ?? []).some((c) => c.question.toLowerCase().includes(q));
    return matchScope && matchType && matchText;
  }),
);

const projectSuitesCount = computed(
  () => props.suites.filter((s) => s.suite_type !== "benchmark").length,
);
const benchmarkSuitesCount = computed(
  () => props.suites.filter((s) => s.suite_type === "benchmark").length,
);

function openSessionPicker() {
  if (!sessionPickAgentId.value && props.agentOptions.length) {
    sessionPickAgentId.value = props.agentOptions[0].value;
  }
  showPickSessions.value = true;
}

function handleSessionsSelected(ids: string[]) {
  showPickSessions.value = false;
  if (!ids.length) return;
  selectedThreadIds.value = ids;
  showSessionConfirmModal.value = true;
}

function submitSessionsConvert() {
  if (!selectedThreadIds.value.length || !sessionSuiteName.value.trim()) return;
  emit("convertSessions", {
    name: sessionSuiteName.value.trim(),
    thread_ids: selectedThreadIds.value,
    source_project_id: props.projectId,
    default_graph_id: draftGraph.value,
  });
  showSessionConfirmModal.value = false;
}

function submitCreate() {
  if (!draftName.value.trim()) return;
  emit("createSuite", {
    name: draftName.value.trim(),
    description: draftDesc.value.trim(),
    suite_type: draftType.value,
    default_graph_id: draftGraph.value,
  });
  draftName.value = "";
  draftDesc.value = "";
  showCreateModal.value = false;
}

function submitImportJsonl() {
  importError.value = "";
  const lines = importText.value
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);
  if (!lines.length || !importName.value.trim()) {
    importError.value = "请输入题库名称与至少一行 JSONL 用例。";
    return;
  }
  const parsed: CaseUpsertPayload[] = [];
  for (let i = 0; i < lines.length; i++) {
    try {
      const row = JSON.parse(lines[i]) as Record<string, unknown>;
      const q = String(row.question ?? row.query ?? row.input ?? "");
      const gt = String(row.ground_truth ?? row.expected_output ?? "");
      parsed.push({
        case_key: String(
          row.case_key || row.id || `import_${String(i + 1).padStart(3, "0")}`,
        ),
        split: row.split === "holdout" ? "holdout" : "dev",
        turns: Array.isArray(row.turns)
          ? row.turns
          : [{ role: "user", content: q }],
        simulation: (row.simulation as Record<string, unknown> | null) ?? null,
        expectations:
          (row.expectations as Record<string, unknown>) ??
          (gt ? { expected_answer: gt } : {}),
        metrics: Array.isArray(row.metrics) ? row.metrics : ["completion"],
      });
    } catch {
      importError.value = `第 ${i + 1} 行 JSON 格式错误。`;
      return;
    }
  }
  emit("importJsonlSuite", {
    name: importName.value.trim(),
    suite_type: draftType.value,
    default_graph_id: draftGraph.value,
    items: parsed,
  });
  importText.value = "";
  showImportModal.value = false;
}
</script>

<template>
  <div class="space-y-4">
    <section class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <MetricCard
        label="纳管评测集"
        :value="suites.length"
        :hint="`专属 ${projectSuitesCount} · 基准 ${benchmarkSuitesCount}`"
        icon="overview"
        tone="primary"
      />
      <MetricCard
        label="累计考题数"
        :value="totalCases"
        hint="支持 Dev + Holdout 分区"
        icon="table"
        tone="success"
      />
      <MetricCard
        label="已冻结版本"
        :value="publishedCount"
        hint="不可变 SHA256 快照"
        icon="shield"
        tone="warning"
      />
      <MetricCard
        label="历史打擂场次"
        :value="runsCount"
        hint="并发执行 + 7 维成绩"
        icon="activity"
        tone="primary"
      />
    </section>

    <SurfaceCard class="p-4 space-y-3">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="flex flex-wrap items-center gap-2">
          <div
            class="inline-flex rounded-lg border border-gray-200 dark:border-dark-700 p-0.5 text-xs"
          >
            <button
              type="button"
              class="px-3 py-1 rounded-md font-medium transition-colors"
              :class="
                scopeTab === 'all'
                  ? 'bg-primary-600 text-white'
                  : 'text-gray-600 dark:text-dark-300'
              "
              @click="scopeTab = 'all'"
            >
              全部 ({{ suites.length }})
            </button>
            <button
              type="button"
              class="px-3 py-1 rounded-md font-medium transition-colors"
              :class="
                scopeTab === 'project'
                  ? 'bg-primary-600 text-white'
                  : 'text-gray-600 dark:text-dark-300'
              "
              @click="scopeTab = 'project'"
            >
              专属题库 ({{ projectSuitesCount }})
            </button>
            <button
              type="button"
              class="px-3 py-1 rounded-md font-medium transition-colors"
              :class="
                scopeTab === 'benchmark'
                  ? 'bg-primary-600 text-white'
                  : 'text-gray-600 dark:text-dark-300'
              "
              @click="scopeTab = 'benchmark'"
            >
              通用基准 ({{ benchmarkSuitesCount }})
            </button>
          </div>
          <div class="w-40">
            <BaseSelect v-model="typeFilter" :options="typeOptions" />
          </div>
          <div class="w-64">
            <BaseInput
              v-model="keyword"
              placeholder="搜索题库名、描述或考题..."
            />
          </div>
        </div>

        <div class="flex flex-wrap items-center gap-2">
          <BaseButton
            size="sm"
            variant="secondary"
            :disabled="!agentOptions.length"
            @click="openSessionPicker"
          >
            从线上会话导入
          </BaseButton>
          <BaseButton
            size="sm"
            variant="secondary"
            @click="showImportModal = true"
          >
            导入 JSONL
          </BaseButton>
          <BaseButton
            size="sm"
            variant="primary"
            @click="showCreateModal = true"
          >
            + 新建空白题库
          </BaseButton>
        </div>
      </div>
    </SurfaceCard>

    <EmptyState
      v-if="!filteredSuites.length"
      title="暂无匹配的评测集"
      description="你可以点击右上角从线上会话导入、导入 JSONL 或新建空白题库。"
    />

    <div v-else class="space-y-3">
      <SurfaceCard
        v-for="suite in filteredSuites"
        :key="suite.id"
        class="p-4 space-y-3 pw-card-hover"
      >
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="space-y-1">
            <div class="flex flex-wrap items-center gap-2">
              <h3
                class="text-sm font-semibold text-gray-900 dark:text-dark-100"
              >
                {{ suite.name }}
              </h3>
              <StatusPill tone="info">{{ suite.suite_type }}</StatusPill>
              <StatusPill tone="neutral"
                >{{ suite.case_count ?? 0 }} 道考题</StatusPill
              >
              <StatusPill v-if="suite.source_project_name" tone="success">
                来源: {{ suite.source_project_name }}
              </StatusPill>
            </div>
            <div
              class="flex flex-wrap items-center gap-3 text-xs text-gray-500 dark:text-dark-400"
            >
              <span
                >默认 Graph:
                <strong class="font-mono">{{
                  suite.default_graph_id
                }}</strong></span
              >
              <span v-if="suite.latest_version">
                · 冻结版本: v{{ suite.latest_version.version_num }} ({{
                  suite.latest_version.content_hash.slice(0, 8)
                }})
              </span>
              <span v-if="suite.runs_count"
                >· 历史打擂 {{ suite.runs_count }} 场</span
              >
              <span
                v-if="suite.best_score != null"
                class="text-emerald-600 dark:text-emerald-400 font-semibold"
              >
                · 最高综合分 {{ Math.round(suite.best_score * 100) }}%
              </span>
            </div>
            <p
              v-if="suite.description"
              class="text-xs text-gray-500 dark:text-dark-300"
            >
              {{ suite.description }}
            </p>
          </div>

          <div class="flex items-center gap-2 shrink-0">
            <BaseButton
              size="sm"
              variant="danger"
              @click="emit('deleteSuite', suite.id)"
            >
              删除
            </BaseButton>
            <BaseButton
              size="sm"
              variant="secondary"
              @click="emit('openSuite', suite.id)"
            >
              前往表格查看全部 {{ suite.case_count ?? 0 }} 题 →
            </BaseButton>
            <BaseButton
              size="sm"
              variant="primary"
              @click="emit('launchSuite', suite)"
            >
              前往评测打擂 →
            </BaseButton>
          </div>
        </div>

        <div
          v-if="(suite.sample_cases?.length ?? 0) > 0"
          class="rounded-lg bg-gray-50/80 dark:bg-dark-800/50 border border-gray-100 dark:border-dark-700 p-3 space-y-2"
        >
          <div
            class="flex items-center justify-between text-[11px] text-gray-500"
          >
            <span>
              考题样例预览（前 {{ suite.sample_cases?.length }} 题 ·
              点击右侧按钮进入全量表格编辑）
            </span>
            <button
              type="button"
              class="text-primary-600 hover:underline"
              @click="expandedIds[suite.id] = !expandedIds[suite.id]"
            >
              {{ expandedIds[suite.id] ? "收起样例详情" : "展开样例详情" }}
            </button>
          </div>
          <div class="grid gap-2 md:grid-cols-3">
            <div
              v-for="sample in suite.sample_cases"
              :key="sample.id"
              class="p-2.5 rounded-md bg-white dark:bg-dark-900 border border-gray-200/70 dark:border-dark-700 text-xs space-y-1"
            >
              <div class="flex items-center justify-between gap-2">
                <span class="font-mono font-semibold truncate">{{
                  sample.case_key
                }}</span>
                <StatusPill
                  :tone="sample.split === 'holdout' ? 'warning' : 'neutral'"
                >
                  {{ sample.split }}
                </StatusPill>
              </div>
              <p class="text-gray-700 dark:text-dark-200 line-clamp-2">
                {{ sample.question || "（待编辑问题）" }}
              </p>
              <p
                v-if="expandedIds[suite.id] && sample.ground_truth"
                class="text-[11px] text-emerald-700 dark:text-emerald-300 line-clamp-2 pt-1 border-t border-gray-100 dark:border-dark-800"
              >
                期望: {{ sample.ground_truth }}
              </p>
            </div>
          </div>
        </div>
      </SurfaceCard>
    </div>

    <BaseDialog
      :show="showCreateModal"
      title="新建空白评测集"
      @close="showCreateModal = false"
    >
      <div class="space-y-4">
        <div>
          <label class="block text-xs font-medium mb-1">评测集名称</label>
          <BaseInput
            v-model="draftName"
            placeholder="如：核心工具与多轮澄清黄金集"
          />
        </div>
        <div>
          <label class="block text-xs font-medium mb-1">描述说明</label>
          <BaseInput v-model="draftDesc" placeholder="简述覆盖的业务边界" />
        </div>
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-xs font-medium mb-1">资产类型</label>
            <BaseSelect
              v-model="draftType"
              :options="typeOptions.filter((o) => o.value !== 'all')"
            />
          </div>
          <div>
            <label class="block text-xs font-medium mb-1">默认目标 Graph</label>
            <BaseSelect v-model="draftGraph" :options="graphOptions" />
          </div>
        </div>
        <div class="flex justify-end gap-2 pt-2">
          <BaseButton variant="secondary" @click="showCreateModal = false"
            >取消</BaseButton
          >
          <BaseButton variant="primary" @click="submitCreate"
            >确认创建</BaseButton
          >
        </div>
      </div>
    </BaseDialog>

    <PickSessionMaterials
      :show="showPickSessions"
      :project-id="projectId"
      :agent-id="sessionPickAgentId"
      @close="showPickSessions = false"
      @select="handleSessionsSelected"
    />

    <BaseDialog
      :show="showSessionConfirmModal"
      title="将所选会话转化并沉淀为题库"
      @close="showSessionConfirmModal = false"
    >
      <div class="space-y-4 text-xs">
        <p class="text-gray-600 dark:text-dark-300">
          已选择
          <strong>{{ selectedThreadIds.length }}</strong>
          条真实会话，系统将提取问答轮次生成可编辑考题并保留源会话血缘。
        </p>
        <div>
          <label class="block font-medium mb-1">新评测集名称</label>
          <BaseInput v-model="sessionSuiteName" />
        </div>
        <div>
          <label class="block font-medium mb-1">默认目标 Graph</label>
          <BaseSelect v-model="draftGraph" :options="graphOptions" />
        </div>
        <div class="flex justify-end gap-2">
          <BaseButton
            variant="secondary"
            @click="showSessionConfirmModal = false"
            >取消</BaseButton
          >
          <BaseButton variant="primary" @click="submitSessionsConvert"
            >生成题库并编辑</BaseButton
          >
        </div>
      </div>
    </BaseDialog>

    <BaseDialog
      :show="showImportModal"
      title="批量导入 JSONL 考题"
      @close="showImportModal = false"
    >
      <div class="space-y-3 text-xs">
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block font-medium mb-1">新建题库名称</label>
            <BaseInput v-model="importName" />
          </div>
          <div>
            <label class="block font-medium mb-1">默认目标 Graph</label>
            <BaseSelect v-model="draftGraph" :options="graphOptions" />
          </div>
        </div>
        <div>
          <label class="block font-medium mb-1">
            每行一条 JSON（支持 <code>question</code> /
            <code>ground_truth</code> / <code>case_key</code>）
          </label>
          <textarea
            v-model="importText"
            rows="6"
            class="pw-input w-full font-mono"
            placeholder='{"case_key":"c1","question":"如何重置密码？","ground_truth":"前往安全设置页面修改"}'
          />
        </div>
        <p v-if="importError" class="text-rose-600">{{ importError }}</p>
        <div class="flex justify-end gap-2">
          <BaseButton variant="secondary" @click="showImportModal = false"
            >取消</BaseButton
          >
          <BaseButton variant="primary" @click="submitImportJsonl"
            >导入并建库</BaseButton
          >
        </div>
      </div>
    </BaseDialog>
  </div>
</template>

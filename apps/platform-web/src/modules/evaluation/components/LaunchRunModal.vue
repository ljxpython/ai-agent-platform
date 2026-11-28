<script setup lang="ts">
import { computed, ref, watch } from "vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseDialog from "@/components/base/BaseDialog.vue";
import BaseSelect from "@/components/base/BaseSelect.vue";
import StateBanner from "@/components/platform/StateBanner.vue";
import type {
  EvalSuiteItem,
  EvalSuiteVersionSummary,
  ReadinessResult,
} from "@/services/evaluation/studio";

const props = defineProps<{
  show: boolean;
  suite: EvalSuiteItem | null;
  versions: EvalSuiteVersionSummary[];
  projectOptions: Array<{ label: string; value: string }>;
  agentOptions: Array<{ label: string; value: string }>;
  modelOptions: Array<{ label: string; value: string; isBroken?: boolean }>;
  defaultModelId: string;
  readiness: ReadinessResult | null;
  readinessLoading?: boolean;
  readinessError?: string;
  submitError?: string;
  busy?: boolean;
}>();

const emit = defineEmits<{
  close: [];
  targetProjectChange: [targetProjectId: string];
  checkReadiness: [
    payload: {
      suite_id: string;
      target_project_id: string;
      agent_id: string;
      model_id: string;
      judge_model_id: string | null;
      embedding_model_id: string | null;
    },
  ];
  launch: [
    payload: {
      suite_id: string;
      version_id: string;
      target_project_id: string;
      agent_id: string;
      model_id: string;
      judge_model_id: string | null;
      embedding_model_id: string | null;
      concurrency: number;
      repeat_k: number;
      confirm_non_sandbox: boolean;
      skip_incompatible: boolean;
    },
  ];
  launchMatrix: [
    payload: {
      suite_id: string;
      version_id: string;
      target_project_id: string;
      judge_model_id: string | null;
      embedding_model_id: string | null;
      concurrency: number;
      repeat_k: number;
      confirm_non_sandbox: boolean;
      variants: Array<{ agent_id: string; model_id: string; label?: string }>;
    },
  ];
}>();

const launchMode = ref<"single" | "matrix">("single");
const targetProjectId = ref("");
const versionId = ref("");
const agentId = ref("");
const modelId = ref("");
const matrixModelIds = ref<string[]>([]);
const judgeModelId = ref("");
const embeddingModelId = ref("");
const concurrency = ref("3");
const repeatK = ref("1");
const confirmNonSandbox = ref(false);
const skipIncompatible = ref(false);

const versionOptions = computed(() =>
  props.versions.map((v) => ({
    label: `v${v.version_num} (${v.case_count} 题 · ${v.content_hash.slice(0, 8)})`,
    value: v.id,
  })),
);

const selectableModels = computed(() =>
  props.modelOptions.filter((m) => !m.isBroken),
);

const concurrencyOptions = [
  { label: "1（串行低负载）", value: "1" },
  { label: "2（稳健低并发）", value: "2" },
  { label: "3（默认推荐）", value: "3" },
  { label: "4（中高并发）", value: "4" },
  { label: "5（单机上限）", value: "5" },
];

const repeatOptions = [
  { label: "1 次 (Pass@1)", value: "1" },
  { label: "3 次 (Pass^3)", value: "3" },
  { label: "5 次 (Pass^5)", value: "5" },
];

function triggerReadiness() {
  const probeModel =
    launchMode.value === "matrix"
      ? matrixModelIds.value[0] || modelId.value
      : modelId.value;
  if (!props.suite || !targetProjectId.value || !agentId.value || !probeModel)
    return;
  emit("checkReadiness", {
    suite_id: props.suite.id,
    target_project_id: targetProjectId.value,
    agent_id: agentId.value,
    model_id: probeModel,
    judge_model_id: judgeModelId.value || null,
    embedding_model_id: embeddingModelId.value || null,
  });
}

watch(
  () => targetProjectId.value,
  (pid) => {
    if (pid) {
      confirmNonSandbox.value = false;
      emit("targetProjectChange", pid);
    }
  },
);

watch(
  () => props.show,
  (open) => {
    if (!open) return;
    confirmNonSandbox.value = false;
    skipIncompatible.value = false;
    if (!targetProjectId.value && props.projectOptions.length) {
      targetProjectId.value = props.projectOptions[0].value;
    }
    if (
      props.versions.length &&
      !props.versions.some((v) => v.id === versionId.value)
    ) {
      versionId.value = props.versions[0].id;
    }
    if (!agentId.value && props.agentOptions.length) {
      const preferred =
        props.agentOptions.find((a) =>
          a.label.includes(props.suite?.default_graph_id || ""),
        ) ?? props.agentOptions[0];
      agentId.value = preferred.value;
    }
    const fallbackId =
      props.defaultModelId || selectableModels.value[0]?.value || "";
    if (
      !modelId.value ||
      !selectableModels.value.some((m) => m.value === modelId.value)
    ) {
      modelId.value = fallbackId;
    }
    if (
      !judgeModelId.value ||
      !selectableModels.value.some((m) => m.value === judgeModelId.value)
    ) {
      judgeModelId.value = fallbackId;
    }
    if (!matrixModelIds.value.length && fallbackId) {
      matrixModelIds.value = [fallbackId];
    }
    triggerReadiness();
  },
);

watch(
  () => [
    targetProjectId.value,
    agentId.value,
    modelId.value,
    judgeModelId.value,
  ],
  () => {
    if (props.show) triggerReadiness();
  },
);

function toggleMatrixModel(id: string) {
  if (matrixModelIds.value.includes(id)) {
    matrixModelIds.value = matrixModelIds.value.filter((m) => m !== id);
  } else if (matrixModelIds.value.length < 6) {
    matrixModelIds.value = [...matrixModelIds.value, id];
  }
}

const canSubmit = computed(() => {
  if (
    !props.suite ||
    !versionId.value ||
    !targetProjectId.value ||
    !agentId.value
  )
    return false;
  if (launchMode.value === "single" && !modelId.value) return false;
  if (launchMode.value === "matrix" && matrixModelIds.value.length === 0)
    return false;
  if (props.readinessLoading || props.readinessError || !props.readiness)
    return false;
  if (!props.readiness.is_sandbox && !confirmNonSandbox.value) return false;
  if (props.readiness.incompatible_cases.length > 0 && !skipIncompatible.value)
    return false;
  return !props.busy;
});

function submitLaunch() {
  if (!props.suite || !canSubmit.value) return;
  if (launchMode.value === "matrix") {
    emit("launchMatrix", {
      suite_id: props.suite.id,
      version_id: versionId.value,
      target_project_id: targetProjectId.value,
      judge_model_id: judgeModelId.value || null,
      embedding_model_id: embeddingModelId.value || null,
      concurrency: Number(concurrency.value),
      repeat_k: Number(repeatK.value),
      confirm_non_sandbox: confirmNonSandbox.value,
      variants: matrixModelIds.value.map((mid) => ({
        agent_id: agentId.value,
        model_id: mid,
        label:
          selectableModels.value.find((m) => m.value === mid)?.label ||
          mid.slice(0, 8),
      })),
    });
    return;
  }
  emit("launch", {
    suite_id: props.suite.id,
    version_id: versionId.value,
    target_project_id: targetProjectId.value,
    agent_id: agentId.value,
    model_id: modelId.value,
    judge_model_id: judgeModelId.value || null,
    embedding_model_id: embeddingModelId.value || null,
    concurrency: Number(concurrency.value),
    repeat_k: Number(repeatK.value),
    confirm_non_sandbox: confirmNonSandbox.value,
    skip_incompatible: skipIncompatible.value,
  });
}
</script>

<template>
  <BaseDialog
    :show="show"
    :title="`发起并发评测 / 矩阵打擂 · ${suite?.name ?? ''}`"
    width="wide"
    @close="emit('close')"
  >
    <div class="space-y-4">
      <div class="flex items-center justify-between gap-2 text-xs">
        <div
          class="inline-flex rounded-lg border border-gray-200 dark:border-dark-700 p-0.5"
        >
          <button
            type="button"
            class="px-3 py-1 rounded-md font-medium"
            :class="
              launchMode === 'single'
                ? 'bg-primary-600 text-white'
                : 'text-gray-600 dark:text-dark-300'
            "
            @click="launchMode = 'single'"
          >
            单配置基准开考
          </button>
          <button
            type="button"
            class="px-3 py-1 rounded-md font-medium"
            :class="
              launchMode === 'matrix'
                ? 'bg-primary-600 text-white'
                : 'text-gray-600 dark:text-dark-300'
            "
            @click="launchMode = 'matrix'"
          >
            多模型矩阵打擂 (Matrix)
          </button>
        </div>
        <BaseButton size="sm" variant="secondary" @click="triggerReadiness">
          重新执行 Readiness Guard
        </BaseButton>
      </div>

      <StateBanner
        v-if="versionOptions.length === 0"
        variant="warning"
        title="该评测集尚未冻结发布版本"
        description="请先进入“考题表格汇总”添加考题并点击“冻结发布”，才能发起不可变版本的并发评测。"
      />

      <div class="grid gap-3 md:grid-cols-2">
        <div>
          <label class="block text-xs font-medium mb-1">冻结题库版本</label>
          <BaseSelect v-model="versionId" :options="versionOptions" />
        </div>
        <div>
          <label class="block text-xs font-medium mb-1"
            >目标隔离执行项目 (Target Project)</label
          >
          <BaseSelect v-model="targetProjectId" :options="projectOptions" />
        </div>
        <div>
          <label class="block text-xs font-medium mb-1"
            >被测 Agent（支持多 Graph）</label
          >
          <BaseSelect v-model="agentId" :options="agentOptions" />
        </div>
        <div v-if="launchMode === 'single'">
          <label class="block text-xs font-medium mb-1"
            >被测推理模型（默认优先 xiaok DeepSeek）</label
          >
          <BaseSelect v-model="modelId" :options="selectableModels" />
        </div>
        <div>
          <label class="block text-xs font-medium mb-1"
            >DeepEval 裁判模型（直连平台网关）</label
          >
          <BaseSelect v-model="judgeModelId" :options="selectableModels" />
        </div>
        <div>
          <label class="block text-xs font-medium mb-1"
            >Case 并发度 (1~5)</label
          >
          <BaseSelect v-model="concurrency" :options="concurrencyOptions" />
        </div>
        <div>
          <label class="block text-xs font-medium mb-1"
            >每题重复次数 (Pass^k)</label
          >
          <BaseSelect v-model="repeatK" :options="repeatOptions" />
        </div>
      </div>

      <div v-if="launchMode === 'matrix'" class="space-y-2">
        <label class="block text-xs font-medium"
          >选择参战对比的模型矩阵 (已选 {{ matrixModelIds.length }}/6)</label
        >
        <div class="grid gap-2 sm:grid-cols-2 max-h-36 overflow-y-auto p-1">
          <button
            v-for="m in selectableModels"
            :key="m.value"
            type="button"
            class="px-2.5 py-2 rounded-lg border text-left text-xs flex items-center justify-between"
            :class="
              matrixModelIds.includes(m.value)
                ? 'border-primary-500 bg-primary-50/70 dark:bg-primary-950/30 text-primary-700 dark:text-primary-200'
                : 'border-gray-200 dark:border-dark-700'
            "
            @click="toggleMatrixModel(m.value)"
          >
            <span class="truncate">{{ m.label }}</span>
            <span>{{ matrixModelIds.includes(m.value) ? "✓" : "+" }}</span>
          </button>
        </div>
      </div>

      <StateBanner
        v-if="readinessLoading"
        variant="info"
        title="正在自动校验目标靶场与模型就绪度..."
        description="请稍候，校验完成后将解除开考限制。"
      />

      <StateBanner
        v-if="readinessError"
        variant="danger"
        title="就绪度校验失败"
        :description="readinessError"
      />

      <StateBanner
        v-if="submitError"
        variant="danger"
        title="发起评测失败"
        :description="submitError"
      />

      <StateBanner
        v-if="readiness && readiness.is_sandbox"
        variant="success"
        title="已匹配专用隔离评测靶场"
        :description="`目标图 ${readiness.graph_id} 与所有 ${versionOptions.length ? '当前版本' : ''}用例均已通过兼容性校验。`"
      />

      <StateBanner
        v-if="readiness && !readiness.is_sandbox"
        variant="warning"
        title="非专用测试靶场风险提示"
        :description="
          readiness.sandbox_warning ||
          '所选项目非专用评测沙箱，将向该项目写入会话、预算与追踪数据。'
        "
      />

      <label
        v-if="readiness && !readiness.is_sandbox"
        class="flex items-center gap-2 text-xs text-amber-700 dark:text-amber-300 cursor-pointer"
      >
        <input v-model="confirmNonSandbox" type="checkbox" class="rounded" />
        <span
          >我已确认知晓风险，允许在所选业务/普通项目中隔离新建评测会话执行</span
        >
      </label>

      <StateBanner
        v-if="readiness && readiness.incompatible_cases.length > 0"
        variant="danger"
        title="目标 Graph 能力与部分用例断言不兼容"
        :description="`目标图 ${readiness.graph_id} 不支持 ${readiness.incompatible_cases.map((c) => c.case_key).join(', ')} 所需的沙箱或工具能力。`"
      />

      <label
        v-if="readiness && readiness.incompatible_cases.length > 0"
        class="flex items-center gap-2 text-xs text-rose-700 dark:text-rose-300 cursor-pointer"
      >
        <input v-model="skipIncompatible" type="checkbox" class="rounded" />
        <span>自动跳过不兼容用例并标记为 skipped_incompatible</span>
      </label>

      <div
        class="flex justify-end gap-2 pt-2 border-t border-gray-100 dark:border-dark-700"
      >
        <BaseButton variant="secondary" @click="emit('close')">取消</BaseButton>
        <BaseButton
          variant="primary"
          :disabled="!canSubmit"
          @click="submitLaunch"
        >
          {{
            busy
              ? "正在提交..."
              : launchMode === "matrix"
                ? "启动矩阵并发打擂"
                : "开始并发评测"
          }}
        </BaseButton>
      </div>
    </div>
  </BaseDialog>
</template>

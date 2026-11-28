<script setup lang="ts">
import { computed, ref, watch } from "vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseDialog from "@/components/base/BaseDialog.vue";
import BaseSelect from "@/components/base/BaseSelect.vue";
import StateBanner from "@/components/platform/StateBanner.vue";
import {
  getSuiteDetail,
  type CronPreviewResult,
  type EvalCaseItem,
  type EvalSuiteItem,
  type EvalSuiteVersionSummary,
  type PatrolCreatePayload,
  type PatrolScheduleItem,
  type PatrolUpdatePayload,
} from "@/services/evaluation/studio";

const props = defineProps<{
  show: boolean;
  projectId: string;
  editingPatrol: PatrolScheduleItem | null;
  suites: EvalSuiteItem[];
  projectOptions: Array<{ label: string; value: string }>;
  agentOptions: Array<{ label: string; value: string }>;
  modelOptions: Array<{ label: string; value: string; isBroken?: boolean }>;
  defaultModelId: string;
  submitError?: string;
  busy?: boolean;
  previewCron: (
    cronExpr: string,
    timezone?: string,
  ) => Promise<CronPreviewResult | null>;
}>();

const emit = defineEmits<{
  close: [];
  targetProjectChange: [targetProjectId: string];
  save: [
    payload: PatrolCreatePayload | PatrolUpdatePayload,
    editingId: string | null,
  ];
}>();

const CRON_PRESETS = [
  { label: "每小时整点", value: "0 * * * *" },
  { label: "每天 03:00", value: "0 3 * * *" },
  { label: "工作日 09:00", value: "0 9 * * 1-5" },
  { label: "每 15 分钟", value: "*/15 * * * *" },
];

const name = ref("");
const suiteId = ref("");
const versionPolicy = ref<"latest_published" | "pinned">("latest_published");
const versionId = ref("");
const targetProjectId = ref("");
const targetAgentId = ref("");
const targetModelId = ref("");
const judgeModelId = ref("");
const cronExpr = ref("0 3 * * *");
const timezone = ref("Asia/Shanghai");
const enabled = ref(true);
const concurrencyPolicy = ref<"forbid" | "allow">("forbid");
const concurrency = ref("2");
const confirmNonSandbox = ref(true);
const skipIncompatible = ref(true);
const notifyOnRecovery = ref(true);
const minTsrPct = ref("70");
const minL1Pct = ref("90");
const dropThresholdPct = ref("5");
const consecutiveAlertThreshold = ref("1");
const selectedCaseKeys = ref<string[]>([]);

const suiteVersions = ref<EvalSuiteVersionSummary[]>([]);
const suiteCases = ref<EvalCaseItem[]>([]);
const cronPreview = ref<CronPreviewResult | null>(null);
const cronError = ref("");

const isEditing = computed(() => Boolean(props.editingPatrol));
const suiteOptions = computed(() =>
  props.suites.map((s) => ({ label: s.name, value: s.id })),
);
const versionOptions = computed(() =>
  suiteVersions.value.map((v) => ({
    label: `v${v.version_num} (${v.case_count} 题 · ${v.content_hash.slice(0, 8)})`,
    value: v.id,
  })),
);
const selectableModels = computed(() =>
  props.modelOptions.filter((m) => !m.isBroken),
);

async function loadSuiteAssets(sid: string) {
  if (!sid || !props.projectId) {
    suiteVersions.value = [];
    suiteCases.value = [];
    return;
  }
  try {
    const detail = await getSuiteDetail(props.projectId, sid);
    suiteVersions.value = detail.versions ?? [];
    suiteCases.value = detail.cases ?? [];
    if (!versionId.value && suiteVersions.value.length > 0) {
      versionId.value = suiteVersions.value[0].id;
    }
  } catch {
    suiteVersions.value = [];
    suiteCases.value = [];
  }
}

async function runCronPreview() {
  cronError.value = "";
  if (!cronExpr.value.trim()) return;
  try {
    const res = await props.previewCron(cronExpr.value.trim(), timezone.value);
    cronPreview.value = res;
  } catch (err) {
    cronPreview.value = null;
    cronError.value = err instanceof Error ? err.message : "Cron 表达式无效";
  }
}

watch(
  () => props.show,
  async (open) => {
    if (!open) return;
    const ed = props.editingPatrol;
    if (ed) {
      name.value = ed.name;
      suiteId.value = ed.suite_id;
      versionPolicy.value = ed.version_policy || "latest_published";
      versionId.value = ed.version_id || "";
      targetProjectId.value = ed.target_project_id;
      targetAgentId.value =
        ed.target_agent_id || props.agentOptions[0]?.value || "";
      targetModelId.value =
        ed.target_model_id ||
        props.defaultModelId ||
        selectableModels.value[0]?.value ||
        "";
      judgeModelId.value = ed.judge_model_id || props.defaultModelId || "";
      cronExpr.value = ed.cron_expr;
      timezone.value = ed.timezone || "Asia/Shanghai";
      enabled.value = ed.enabled;
      concurrencyPolicy.value = ed.concurrency_policy || "forbid";
      concurrency.value = String(ed.concurrency ?? 2);
      confirmNonSandbox.value = ed.confirm_non_sandbox ?? true;
      skipIncompatible.value = ed.skip_incompatible ?? true;
      notifyOnRecovery.value = ed.notify_on_recovery ?? true;
      minTsrPct.value = String(
        Math.round((ed.gate_config?.min_tsr ?? 0.7) * 100),
      );
      minL1Pct.value = String(
        Math.round((ed.gate_config?.min_l1_pass_rate ?? 0.9) * 100),
      );
      dropThresholdPct.value = String(
        Math.round((ed.gate_config?.regression_drop_threshold ?? 0.05) * 100),
      );
      consecutiveAlertThreshold.value = String(
        ed.gate_config?.consecutive_alert_threshold ?? 1,
      );
      selectedCaseKeys.value = [...(ed.case_keys ?? [])];
    } else {
      name.value = "";
      suiteId.value = props.suites[0]?.id || "";
      versionPolicy.value = "latest_published";
      versionId.value = "";
      targetProjectId.value =
        props.projectId || props.projectOptions[0]?.value || "";
      targetAgentId.value = props.agentOptions[0]?.value || "";
      targetModelId.value =
        props.defaultModelId || selectableModels.value[0]?.value || "";
      judgeModelId.value =
        props.defaultModelId || selectableModels.value[0]?.value || "";
      cronExpr.value = "0 3 * * *";
      timezone.value = "Asia/Shanghai";
      enabled.value = true;
      concurrencyPolicy.value = "forbid";
      concurrency.value = "2";
      confirmNonSandbox.value = true;
      skipIncompatible.value = true;
      notifyOnRecovery.value = true;
      minTsrPct.value = "70";
      minL1Pct.value = "90";
      dropThresholdPct.value = "5";
      consecutiveAlertThreshold.value = "1";
      selectedCaseKeys.value = [];
    }
    await loadSuiteAssets(suiteId.value);
    await runCronPreview();
  },
);

watch(suiteId, async (sid) => {
  if (!props.show) return;
  versionId.value = "";
  if (!isEditing.value) selectedCaseKeys.value = [];
  await loadSuiteAssets(sid);
});

watch(targetProjectId, (pid) => {
  if (props.show && pid) {
    emit("targetProjectChange", pid);
  }
});

function toggleCaseKey(key: string) {
  if (selectedCaseKeys.value.includes(key)) {
    selectedCaseKeys.value = selectedCaseKeys.value.filter((k) => k !== key);
  } else {
    selectedCaseKeys.value = [...selectedCaseKeys.value, key];
  }
}

function submit() {
  const gateConfig = {
    min_tsr: Math.min(1, Math.max(0, Number(minTsrPct.value || 70) / 100)),
    min_l1_pass_rate: Math.min(
      1,
      Math.max(0, Number(minL1Pct.value || 90) / 100),
    ),
    max_loop_rate: 0.1,
    max_p95_ttft_ms: null,
    regression_drop_threshold: Math.min(
      1,
      Math.max(0, Number(dropThresholdPct.value || 5) / 100),
    ),
    ttft_spike_ratio: 0.5,
    consecutive_alert_threshold: Math.max(
      1,
      Math.min(10, Number(consecutiveAlertThreshold.value || 1)),
    ),
  };
  const common = {
    name: name.value.trim(),
    version_policy: versionPolicy.value,
    version_id:
      versionPolicy.value === "pinned" ? versionId.value || null : null,
    target_project_id: targetProjectId.value,
    target_agent_id: targetAgentId.value,
    target_model_id: targetModelId.value,
    judge_model_id: judgeModelId.value || null,
    case_keys: [...selectedCaseKeys.value],
    concurrency: Number(concurrency.value || 2),
    repeat_k: 1,
    skip_incompatible: skipIncompatible.value,
    confirm_non_sandbox: confirmNonSandbox.value,
    cron_expr: cronExpr.value.trim(),
    timezone: timezone.value.trim() || "Asia/Shanghai",
    enabled: enabled.value,
    concurrency_policy: concurrencyPolicy.value,
    gate_config: gateConfig,
    notify_on_recovery: notifyOnRecovery.value,
  };
  if (props.editingPatrol) {
    emit("save", common, props.editingPatrol.id);
  } else {
    emit("save", { ...common, suite_id: suiteId.value }, null);
  }
}
</script>

<template>
  <BaseDialog
    :show="show"
    :title="
      isEditing ? `编辑定时巡检 · ${editingPatrol?.name}` : '新建定时巡检规则'
    "
    width="wide"
    @close="emit('close')"
  >
    <div class="space-y-4 text-xs">
      <StateBanner
        v-if="submitError"
        variant="danger"
        title="保存巡检配置失败"
        :description="submitError"
      />

      <div class="grid gap-4 md:grid-cols-2">
        <div class="space-y-3">
          <div>
            <label class="block font-medium mb-1">巡检名称</label>
            <input
              v-model="name"
              type="text"
              placeholder="例如：夜间黄金集核心冒烟巡检"
              class="w-full rounded-lg border border-gray-300 dark:border-dark-600 bg-white dark:bg-dark-900 px-3 py-1.5"
            />
          </div>

          <div>
            <label class="block font-medium mb-1">关联评测集</label>
            <BaseSelect
              v-model="suiteId"
              :options="suiteOptions"
              :disabled="isEditing"
            />
          </div>

          <div class="grid grid-cols-2 gap-2">
            <div>
              <label class="block font-medium mb-1">版本追踪策略</label>
              <BaseSelect
                v-model="versionPolicy"
                :options="[
                  { label: '始终最新冻结版', value: 'latest_published' },
                  { label: '锁定指定版本', value: 'pinned' },
                ]"
              />
            </div>
            <div>
              <label class="block font-medium mb-1">锁定版本</label>
              <BaseSelect
                v-model="versionId"
                :options="versionOptions"
                :disabled="versionPolicy !== 'pinned'"
              />
            </div>
          </div>

          <div>
            <label class="block font-medium mb-1">目标隔离执行项目</label>
            <BaseSelect v-model="targetProjectId" :options="projectOptions" />
          </div>

          <div class="grid grid-cols-2 gap-2">
            <div>
              <label class="block font-medium mb-1">目标 Agent</label>
              <BaseSelect v-model="targetAgentId" :options="agentOptions" />
            </div>
            <div>
              <label class="block font-medium mb-1">被测模型</label>
              <BaseSelect v-model="targetModelId" :options="selectableModels" />
            </div>
          </div>

          <div class="grid grid-cols-2 gap-2">
            <div>
              <label class="block font-medium mb-1">DeepEval 裁判模型</label>
              <BaseSelect v-model="judgeModelId" :options="selectableModels" />
            </div>
            <div>
              <label class="block font-medium mb-1">并发度</label>
              <BaseSelect
                v-model="concurrency"
                :options="[
                  { label: '1 (串行)', value: '1' },
                  { label: '2 (稳健推荐)', value: '2' },
                  { label: '3 (标准)', value: '3' },
                  { label: '4', value: '4' },
                  { label: '5 (上限)', value: '5' },
                ]"
              />
            </div>
          </div>
        </div>

        <div class="space-y-3">
          <div>
            <label class="block font-medium mb-1">Cron 调度频率预设</label>
            <div class="flex flex-wrap gap-1.5 mb-2">
              <button
                v-for="p in CRON_PRESETS"
                :key="p.value"
                type="button"
                class="px-2 py-1 rounded border text-[11px]"
                :class="
                  cronExpr === p.value
                    ? 'border-primary-600 bg-primary-50 dark:bg-primary-950/40 text-primary-700 dark:text-primary-300 font-medium'
                    : 'border-gray-200 dark:border-dark-700 text-gray-600 dark:text-dark-300'
                "
                @click="
                  cronExpr = p.value;
                  runCronPreview();
                "
              >
                {{ p.label }}
              </button>
            </div>
            <div class="flex gap-2">
              <input
                v-model="cronExpr"
                type="text"
                placeholder="分 时 日 月 周 (如 0 3 * * *)"
                class="flex-1 font-mono rounded-lg border border-gray-300 dark:border-dark-600 bg-white dark:bg-dark-900 px-2.5 py-1.5"
                @blur="runCronPreview"
              />
              <BaseButton size="sm" variant="secondary" @click="runCronPreview">
                预览时间
              </BaseButton>
            </div>
            <div v-if="cronError" class="mt-1 text-[11px] text-rose-600">
              {{ cronError }}
            </div>
            <div
              v-else-if="cronPreview?.next_runs?.length"
              class="mt-1.5 p-2 rounded bg-gray-50 dark:bg-dark-800/70 space-y-0.5 text-[11px]"
            >
              <div class="text-gray-500">
                未来 5 次执行 ({{ cronPreview.timezone }})：
              </div>
              <div
                v-for="t in cronPreview.next_runs"
                :key="t"
                class="font-mono text-gray-700 dark:text-dark-200"
              >
                • {{ new Date(t).toLocaleString() }}
              </div>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-2">
            <div>
              <label class="block font-medium mb-1">并发重叠策略</label>
              <BaseSelect
                v-model="concurrencyPolicy"
                :options="[
                  { label: 'Forbid（上一轮未完跳过）', value: 'forbid' },
                  { label: 'Allow（允许并行入队）', value: 'allow' },
                ]"
              />
            </div>
            <div>
              <label class="block font-medium mb-1">时区</label>
              <BaseSelect
                v-model="timezone"
                :options="[
                  { label: 'Asia/Shanghai (北京时间)', value: 'Asia/Shanghai' },
                  { label: 'UTC', value: 'UTC' },
                ]"
              />
            </div>
          </div>

          <div
            class="rounded-lg border border-gray-200 dark:border-dark-700 p-2.5 space-y-2"
          >
            <div class="font-medium">门禁与相对基线退化告警阈值</div>
            <div class="grid grid-cols-2 gap-2 text-[11px]">
              <label class="space-y-0.5">
                <span class="text-gray-500">TSR 最低门槛 (%)</span>
                <input
                  v-model="minTsrPct"
                  type="number"
                  min="0"
                  max="100"
                  class="w-full rounded border border-gray-300 dark:border-dark-600 bg-white dark:bg-dark-900 px-2 py-1"
                />
              </label>
              <label class="space-y-0.5">
                <span class="text-gray-500">L1 规则最低通过率 (%)</span>
                <input
                  v-model="minL1Pct"
                  type="number"
                  min="0"
                  max="100"
                  class="w-full rounded border border-gray-300 dark:border-dark-600 bg-white dark:bg-dark-900 px-2 py-1"
                />
              </label>
              <label class="space-y-0.5">
                <span class="text-gray-500">相对上次通过跌幅触发退化 (%)</span>
                <input
                  v-model="dropThresholdPct"
                  type="number"
                  min="0"
                  max="100"
                  class="w-full rounded border border-gray-300 dark:border-dark-600 bg-white dark:bg-dark-900 px-2 py-1"
                />
              </label>
              <label class="space-y-0.5">
                <span class="text-gray-500">连续失败 N 次触发告警</span>
                <input
                  v-model="consecutiveAlertThreshold"
                  type="number"
                  min="1"
                  max="10"
                  class="w-full rounded border border-gray-300 dark:border-dark-600 bg-white dark:bg-dark-900 px-2 py-1"
                />
              </label>
            </div>
          </div>
        </div>
      </div>

      <div
        v-if="suiteCases.length"
        class="rounded-lg border border-gray-200 dark:border-dark-700 p-3 space-y-2"
      >
        <div class="flex items-center justify-between">
          <span class="font-medium">
            巡检考题范围（{{
              selectedCaseKeys.length
                ? `已选 ${selectedCaseKeys.length} 题冒烟`
                : `全量 ${suiteCases.length} 题`
            }}）
          </span>
          <button
            v-if="selectedCaseKeys.length"
            type="button"
            class="text-primary-600 hover:underline text-[11px]"
            @click="selectedCaseKeys = []"
          >
            重置为全量
          </button>
        </div>
        <div class="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto">
          <label
            v-for="c in suiteCases"
            :key="c.case_key"
            class="inline-flex items-center gap-1 px-2 py-0.5 rounded border border-gray-200 dark:border-dark-700 cursor-pointer text-[11px]"
          >
            <input
              type="checkbox"
              :checked="selectedCaseKeys.includes(c.case_key)"
              @change="toggleCaseKey(c.case_key)"
            />
            <span class="font-mono">{{ c.case_key }}</span>
          </label>
        </div>
      </div>

      <div class="flex flex-wrap items-center gap-4 text-xs">
        <label class="inline-flex items-center gap-1.5 cursor-pointer">
          <input v-model="enabled" type="checkbox" />
          <span>创建后立即启用调度</span>
        </label>
        <label class="inline-flex items-center gap-1.5 cursor-pointer">
          <input v-model="notifyOnRecovery" type="checkbox" />
          <span>异常自愈通过时发送恢复通知</span>
        </label>
        <label class="inline-flex items-center gap-1.5 cursor-pointer">
          <input v-model="confirmNonSandbox" type="checkbox" />
          <span>确认目标项目执行授权</span>
        </label>
      </div>

      <div class="text-[11px] text-gray-500">
        告警通知将自动写入平台站内信，并复用「告警与通知推送配置」中订阅了
        <code>eval_degraded</code> 的飞书/Webhook 渠道进行防抖分发。
      </div>

      <div
        class="flex justify-end gap-2 pt-2 border-t border-gray-200 dark:border-dark-700"
      >
        <BaseButton size="sm" variant="secondary" @click="emit('close')">
          取消
        </BaseButton>
        <BaseButton
          size="sm"
          variant="primary"
          :disabled="
            busy ||
            !name.trim() ||
            !suiteId ||
            !targetProjectId ||
            !targetAgentId ||
            !targetModelId ||
            (versionPolicy === 'pinned' && !versionId)
          "
          @click="submit"
        >
          {{ busy ? "保存中..." : isEditing ? "保存修改" : "创建巡检规则" }}
        </BaseButton>
      </div>
    </div>
  </BaseDialog>
</template>

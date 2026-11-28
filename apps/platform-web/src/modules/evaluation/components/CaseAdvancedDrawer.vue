<script setup lang="ts">
import { ref, watch } from "vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseDrawer from "@/components/base/BaseDrawer.vue";
import BaseInput from "@/components/base/BaseInput.vue";
import BaseSelect from "@/components/base/BaseSelect.vue";
import type {
  CaseUpsertPayload,
  EvalCaseItem,
} from "@/services/evaluation/studio";

const props = defineProps<{
  show: boolean;
  item: EvalCaseItem | null;
}>();

const emit = defineEmits<{
  close: [];
  save: [payload: CaseUpsertPayload];
}>();

const caseKey = ref("");
const split = ref<"dev" | "holdout">("dev");
const mode = ref<"fixed" | "simulation">("fixed");
const promptText = ref("");
const expectedAnswer = ref("");
const simGoal = ref("");
const simUserMode = ref<
  | "cooperative"
  | "terse"
  | "impatient_reversal"
  | "skeptical_challenger"
  | "ambiguous_changer"
>("cooperative");
const hiddenFactsText = ref("[]");
const delayedFixturesText = ref("[]");
const interruptStrategyText = ref("{}");
const artifactsJson = ref("[]");
const toolConstraintsText = ref("{}");
const selectedMetrics = ref<string[]>(["completion"]);

const availableMetrics = [
  { id: "completion", label: "L1 · completion (任务完成)" },
  { id: "artifact_correct", label: "L1 · artifact_correct (产物校验)" },
  { id: "protected_unchanged", label: "L1 · protected_unchanged (源夹具保护)" },
  { id: "approval", label: "L1 · approval (审批防偷跑)" },
  {
    id: "cross_project_denied",
    label: "L1 · cross_project_denied (跨项目隔离)",
  },
  { id: "tool_constraints", label: "L1 · tool_constraints (工具边界)" },
  {
    id: "clarification_requested",
    label: "L1 · clarification_requested (主动追问)",
  },
  { id: "retrieved", label: "L1 · retrieved (检索取证)" },
  { id: "RefusalAssertion", label: "L1 · RefusalAssertion (拒答合规)" },
  {
    id: "CounterfactualAssertion",
    label: "L1 · CounterfactualAssertion (反事实纠偏)",
  },
  { id: "Faithfulness", label: "L2 · Faithfulness (忠实度)" },
  { id: "ContextualRecall", label: "L2 · ContextualRecall (检索召回)" },
  {
    id: "ConversationalGEval",
    label: "L2 · ConversationalGEval (多轮博弈评价)",
  },
  { id: "KnowledgeRetention", label: "L2 · KnowledgeRetention (多轮终态记忆)" },
  { id: "ToolCorrectness", label: "L2 · ToolCorrectness (工具选择合规)" },
  { id: "BusinessFacts", label: "L2 · BusinessFacts (业务事实)" },
  { id: "StepEfficiency", label: "L2 · StepEfficiency (步骤效率)" },
];

watch(
  () => props.item,
  (val) => {
    if (!val) return;
    caseKey.value = val.case_key;
    split.value = val.split;
    mode.value = val.simulation ? "simulation" : "fixed";
    const firstTurn = val.turns[0] as Record<string, unknown> | undefined;
    promptText.value = String(firstTurn?.content ?? "");
    expectedAnswer.value = String(val.expectations?.expected_answer ?? "");
    simGoal.value = String(val.simulation?.goal ?? "");
    simUserMode.value =
      (val.simulation?.user_mode as typeof simUserMode.value) || "cooperative";
    hiddenFactsText.value = JSON.stringify(
      val.simulation?.hidden_facts ?? [],
      null,
      2,
    );
    delayedFixturesText.value = JSON.stringify(
      val.simulation?.delayed_fixtures ?? [],
      null,
      2,
    );
    interruptStrategyText.value = JSON.stringify(
      val.simulation?.interrupt_strategy ?? {},
      null,
      2,
    );
    artifactsJson.value = JSON.stringify(
      val.expectations?.artifacts ?? [],
      null,
      2,
    );
    toolConstraintsText.value = JSON.stringify(
      val.expectations?.tool_constraints ?? {},
      null,
      2,
    );
    const parsedMetrics = (val.metrics ?? [])
      .map((m) => (typeof m === "string" ? m : String(m.name ?? "")))
      .filter(Boolean);
    selectedMetrics.value = parsedMetrics.length
      ? parsedMetrics
      : ["completion"];
  },
  { immediate: true },
);

function toggleMetric(name: string) {
  if (selectedMetrics.value.includes(name)) {
    selectedMetrics.value = selectedMetrics.value.filter((x) => x !== name);
  } else {
    selectedMetrics.value = [...selectedMetrics.value, name];
  }
}

function safeJsonParse(raw: string, fallback: unknown) {
  try {
    return JSON.parse(raw);
  } catch {
    return fallback;
  }
}

function handleSave() {
  if (!caseKey.value.trim()) return;
  const artifacts = safeJsonParse(artifactsJson.value || "[]", []);
  const hiddenFacts = safeJsonParse(hiddenFactsText.value || "[]", []);
  const delayedFixtures = safeJsonParse(delayedFixturesText.value || "[]", []);
  const interruptStrategy = safeJsonParse(
    interruptStrategyText.value || "{}",
    {},
  );
  const toolConstraints = safeJsonParse(toolConstraintsText.value || "{}", {});

  emit("save", {
    case_key: caseKey.value.trim(),
    split: split.value,
    turns: promptText.value.trim()
      ? [{ role: "user", content: promptText.value.trim() }]
      : (props.item?.turns ?? []),
    simulation:
      mode.value === "simulation"
        ? {
            goal: simGoal.value,
            user_mode: simUserMode.value,
            max_turns: 6,
            hidden_facts: hiddenFacts,
            delayed_fixtures: delayedFixtures,
            interrupt_strategy: interruptStrategy,
          }
        : null,
    expectations: {
      ...(expectedAnswer.value.trim()
        ? { expected_answer: expectedAnswer.value.trim() }
        : {}),
      ...(Array.isArray(artifacts)
        ? artifacts.length > 0
          ? { artifacts }
          : {}
        : artifacts &&
            Object.keys(artifacts as Record<string, unknown>).length > 0
          ? { artifacts }
          : {}),
      ...(toolConstraints &&
      Object.keys(toolConstraints as Record<string, unknown>).length > 0
        ? { tool_constraints: toolConstraints }
        : {}),
    },
    metrics: (selectedMetrics.value.length
      ? selectedMetrics.value
      : ["completion"]
    ).map((name) => ({
      name,
    })),
    metadata: props.item?.metadata ?? {},
  });
  emit("close");
}
</script>

<template>
  <BaseDrawer
    :show="show"
    :title="`Agent 高级断言与仿真配置 · ${item?.case_key ?? ''}`"
    width="wide"
    @close="emit('close')"
  >
    <div class="space-y-4 text-xs">
      <div class="grid gap-3 md:grid-cols-2">
        <div>
          <label class="block font-medium mb-1">用例标识 (case_key)</label>
          <BaseInput v-model="caseKey" />
        </div>
        <div>
          <label class="block font-medium mb-1">分区 (Dev / Holdout)</label>
          <BaseSelect
            v-model="split"
            :options="[
              { label: '开发集 (dev)', value: 'dev' },
              { label: '盲测集 (holdout)', value: 'holdout' },
            ]"
          />
        </div>
      </div>

      <div>
        <label class="block font-medium mb-1">执行形态</label>
        <BaseSelect
          v-model="mode"
          :options="[
            { label: '固定脚本轮次 (Single/Multi-turn)', value: 'fixed' },
            { label: '中文动态用户博弈 (Simulation)', value: 'simulation' },
          ]"
        />
      </div>

      <div>
        <label class="block font-medium mb-1"
          >首轮用户输入（固定轮次及仿真首句）</label
        >
        <textarea v-model="promptText" rows="3" class="pw-input w-full" />
      </div>

      <div
        v-if="mode === 'simulation'"
        class="space-y-3 p-3 rounded-lg bg-gray-50 dark:bg-dark-800/60 border border-gray-200 dark:border-dark-700"
      >
        <div class="grid gap-3 md:grid-cols-2">
          <div>
            <label class="block font-medium mb-1">仿真任务目标 (goal)</label>
            <BaseInput
              v-model="simGoal"
              placeholder="描述模拟用户的终极任务目标"
            />
          </div>
          <div>
            <label class="block font-medium mb-1">模拟用户人格</label>
            <BaseSelect
              v-model="simUserMode"
              :options="[
                { label: '配合型 (cooperative)', value: 'cooperative' },
                {
                  label: '严谨质疑型 (skeptical_challenger)',
                  value: 'skeptical_challenger',
                },
                {
                  label: '含糊补改型 (ambiguous_changer)',
                  value: 'ambiguous_changer',
                },
                { label: '简短追问型 (terse)', value: 'terse' },
                {
                  label: '中途改口型 (impatient_reversal)',
                  value: 'impatient_reversal',
                },
              ]"
            />
          </div>
        </div>
        <div>
          <label class="block font-medium mb-1"
            >隐藏事实清单 (hidden_facts JSON)</label
          >
          <textarea
            v-model="hiddenFactsText"
            rows="2"
            class="pw-input w-full font-mono"
          />
        </div>
        <div>
          <label class="block font-medium mb-1"
            >延迟夹具文件 (delayed_fixtures JSON)</label
          >
          <textarea
            v-model="delayedFixturesText"
            rows="2"
            class="pw-input w-full font-mono"
          />
        </div>
        <div>
          <label class="block font-medium mb-1"
            >中断与审批策略 (interrupt_strategy JSON)</label
          >
          <textarea
            v-model="interruptStrategyText"
            rows="2"
            class="pw-input w-full font-mono"
          />
        </div>
      </div>

      <div>
        <label class="block font-medium mb-1"
          >黄金答案摘要 (expected_answer)</label
        >
        <textarea v-model="expectedAnswer" rows="3" class="pw-input w-full" />
      </div>

      <div>
        <label class="block font-medium mb-1.5"
          >分级指标勾选 (L1 硬规则 + L2 DeepEval)</label
        >
        <div class="grid gap-2 sm:grid-cols-2">
          <button
            v-for="m in availableMetrics"
            :key="m.id"
            type="button"
            class="px-2.5 py-2 rounded-lg border text-left transition-colors flex items-center justify-between"
            :class="
              selectedMetrics.includes(m.id)
                ? 'border-primary-500 bg-primary-50/70 dark:bg-primary-950/30 text-primary-700 dark:text-primary-200'
                : 'border-gray-200 dark:border-dark-700 hover:bg-gray-50 dark:hover:bg-dark-800'
            "
            @click="toggleMetric(m.id)"
          >
            <span>{{ m.label }}</span>
            <span class="font-mono text-[10px]">
              {{ selectedMetrics.includes(m.id) ? "已选" : "+" }}
            </span>
          </button>
        </div>
      </div>

      <div>
        <label class="block font-medium mb-1"
          >物理产物基线断言 (expectations.artifacts JSON)</label
        >
        <textarea
          v-model="artifactsJson"
          rows="3"
          class="pw-input w-full font-mono"
        />
      </div>

      <div>
        <label class="block font-medium mb-1"
          >工具调用与参数边界约束 (expectations.tool_constraints JSON)</label
        >
        <textarea
          v-model="toolConstraintsText"
          rows="3"
          class="pw-input w-full font-mono"
        />
      </div>

      <div
        class="flex justify-end gap-2 pt-3 border-t border-gray-100 dark:border-dark-700"
      >
        <BaseButton variant="secondary" @click="emit('close')">取消</BaseButton>
        <BaseButton variant="primary" @click="handleSave"
          >应用并保存此题</BaseButton
        >
      </div>
    </div>
  </BaseDrawer>
</template>

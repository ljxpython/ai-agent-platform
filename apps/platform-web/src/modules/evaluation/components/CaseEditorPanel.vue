<script setup lang="ts">
import { computed, ref, watch } from "vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseInput from "@/components/base/BaseInput.vue";
import BaseSelect from "@/components/base/BaseSelect.vue";
import SurfaceCard from "@/components/base/SurfaceCard.vue";
import EmptyState from "@/components/platform/EmptyState.vue";
import StatusPill from "@/components/platform/StatusPill.vue";
import CaseAdvancedDrawer from "@/modules/evaluation/components/CaseAdvancedDrawer.vue";
import type {
  CaseUpsertPayload,
  EvalCaseItem,
  EvalSuiteItem,
  EvalSuiteVersionSummary,
} from "@/services/evaluation/studio";

interface EditableRow {
  case_key: string;
  split: "dev" | "holdout";
  question: string;
  ground_truth: string;
  isNew?: boolean;
  dirty?: boolean;
  raw: EvalCaseItem;
}

const props = defineProps<{
  suites: EvalSuiteItem[];
  suite: EvalSuiteItem | null;
  cases: EvalCaseItem[];
  versions: EvalSuiteVersionSummary[];
  busy?: boolean;
}>();

const emit = defineEmits<{
  switchSuite: [suiteId: string];
  saveCase: [payload: CaseUpsertPayload];
  saveBatch: [items: CaseUpsertPayload[]];
  deleteCase: [caseKey: string];
  publishVersion: [];
  launchSuite: [suite: EvalSuiteItem];
  openCopilot: [];
}>();

const keyword = ref("");
const rows = ref<EditableRow[]>([]);
const drawerItem = ref<EvalCaseItem | null>(null);
const showAdvancedDrawer = ref(false);

const suiteSelectOptions = computed(() =>
  props.suites.map((s) => ({
    label: `${s.name} (${s.case_count ?? 0} 题)`,
    value: s.id,
  })),
);

const currentSuiteId = computed({
  get: () => props.suite?.id ?? "",
  set: (val: string) => {
    if (val && val !== props.suite?.id) emit("switchSuite", val);
  },
});

function toEditableRow(c: EvalCaseItem): EditableRow {
  const firstTurn = c.turns?.[0] as Record<string, unknown> | undefined;
  const question = c.simulation
    ? String(c.simulation.goal ?? "")
    : String(firstTurn?.content ?? "");
  return {
    case_key: c.case_key,
    split: c.split,
    question,
    ground_truth: String(c.expectations?.expected_answer ?? ""),
    dirty: false,
    raw: c,
  };
}

watch(
  () => props.cases,
  (list) => {
    rows.value = list.map(toEditableRow);
  },
  { immediate: true },
);

const filteredRows = computed(() => {
  const q = keyword.value.trim().toLowerCase();
  if (!q) return rows.value;
  return rows.value.filter(
    (r) =>
      r.case_key.toLowerCase().includes(q) ||
      r.question.toLowerCase().includes(q) ||
      r.ground_truth.toLowerCase().includes(q),
  );
});

const dirtyCount = computed(() => rows.value.filter((r) => r.dirty).length);
const devCount = computed(
  () => rows.value.filter((r) => r.split === "dev").length,
);
const holdoutCount = computed(
  () => rows.value.filter((r) => r.split === "holdout").length,
);

function addInlineRow() {
  const nextKey = `case_${String(rows.value.length + 1).padStart(3, "0")}`;
  const blankRaw: EvalCaseItem = {
    id: `draft-${Date.now()}`,
    suite_id: props.suite?.id ?? "",
    case_key: nextKey,
    split: "dev",
    schema_version: "3",
    required_capabilities: [],
    turns: [{ role: "user", content: "" }],
    simulation: null,
    expectations: { expected_answer: "" },
    metrics: [{ name: "completion" }],
    metadata: {},
    updated_at: null,
  };
  rows.value = [
    ...rows.value,
    {
      case_key: nextKey,
      split: "dev",
      question: "",
      ground_truth: "",
      isNew: true,
      dirty: true,
      raw: blankRaw,
    },
  ];
}

function rowToPayload(row: EditableRow): CaseUpsertPayload {
  const sim = row.raw.simulation
    ? { ...row.raw.simulation, goal: row.question }
    : null;
  const turns = sim
    ? []
    : [
        { role: "user", content: row.question },
        ...(row.raw.turns?.slice(1) ?? []),
      ];
  return {
    case_key: row.case_key.trim(),
    split: row.split,
    turns,
    simulation: sim,
    expectations: {
      ...(row.raw.expectations ?? {}),
      expected_answer: row.ground_truth,
    },
    metrics:
      row.raw.metrics && row.raw.metrics.length
        ? row.raw.metrics
        : [{ name: "completion" }],
    metadata: row.raw.metadata ?? {},
  };
}

function saveAllDirty() {
  const payloads = rows.value
    .filter((r) => r.dirty && r.case_key.trim())
    .map(rowToPayload);
  if (!payloads.length) return;
  emit("saveBatch", payloads);
}

function openAdvanced(row: EditableRow) {
  drawerItem.value = {
    ...row.raw,
    case_key: row.case_key,
    split: row.split,
    turns: row.raw.simulation
      ? row.raw.turns
      : [
          { role: "user", content: row.question },
          ...(row.raw.turns?.slice(1) ?? []),
        ],
    expectations: {
      ...(row.raw.expectations ?? {}),
      expected_answer: row.ground_truth,
    },
  };
  showAdvancedDrawer.value = true;
}

function removeRow(row: EditableRow) {
  if (row.isNew) {
    rows.value = rows.value.filter((r) => r.case_key !== row.case_key);
    return;
  }
  emit("deleteCase", row.case_key);
}
</script>

<template>
  <div class="space-y-4">
    <SurfaceCard class="p-4 space-y-3">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="flex flex-wrap items-center gap-2.5">
          <span class="text-xs font-medium text-gray-500">当前评测集:</span>
          <div class="w-64">
            <BaseSelect
              v-model="currentSuiteId"
              :options="suiteSelectOptions"
              placeholder="请先选择评测集"
            />
          </div>
          <template v-if="suite">
            <StatusPill tone="neutral">开发集 {{ devCount }}</StatusPill>
            <StatusPill tone="warning">盲测集 {{ holdoutCount }}</StatusPill>
            <StatusPill :tone="versions[0] ? 'success' : 'info'">
              {{
                versions[0]
                  ? `最新冻结 v${versions[0].version_num} (${versions[0].content_hash.slice(0, 8)})`
                  : "未冻结草稿"
              }}
            </StatusPill>
          </template>
        </div>

        <div class="flex flex-wrap items-center gap-2">
          <div class="w-52">
            <BaseInput v-model="keyword" placeholder="搜索问题或答案..." />
          </div>
          <BaseButton
            size="sm"
            variant="secondary"
            :disabled="!suite"
            @click="addInlineRow"
          >
            + 添加考题
          </BaseButton>
          <BaseButton
            size="sm"
            variant="secondary"
            :disabled="!suite || dirtyCount === 0 || busy"
            @click="saveAllDirty"
          >
            {{ dirtyCount > 0 ? `保存改动 (${dirtyCount})` : "表格已同步" }}
          </BaseButton>
          <BaseButton
            size="sm"
            variant="secondary"
            :disabled="!suite"
            @click="emit('openCopilot')"
          >
            AI 出题专家
          </BaseButton>
          <BaseButton
            size="sm"
            variant="primary"
            :disabled="!suite || rows.length === 0 || busy"
            @click="emit('publishVersion')"
          >
            冻结发布 v{{ (versions[0]?.version_num ?? 0) + 1 }}
          </BaseButton>
          <BaseButton
            v-if="suite"
            size="sm"
            variant="primary"
            @click="emit('launchSuite', suite)"
          >
            发起评测打擂 →
          </BaseButton>
        </div>
      </div>
    </SurfaceCard>

    <EmptyState
      v-if="!suite"
      title="请先选择一个评测集"
      description="请在上方下拉框选择评测集，或前往“题库资产全景”新建或导入题库。"
    />

    <SurfaceCard v-else class="overflow-hidden">
      <div
        v-if="!filteredRows.length"
        class="p-10 text-center text-xs text-gray-500"
      >
        当前评测集暂无考题，点击右上方“+ 添加考题”或“AI 出题专家”快速生成。
      </div>
      <div v-else class="overflow-x-auto">
        <table class="w-full text-left text-xs">
          <thead>
            <tr
              class="border-b border-gray-200 dark:border-dark-700 bg-gray-50 dark:bg-dark-800/70 text-gray-500"
            >
              <th class="py-2.5 px-3 w-12 text-center">#</th>
              <th class="py-2.5 px-3 w-40">用例标识与分区</th>
              <th class="py-2.5 px-3 min-w-[260px]">
                提问问题 / 仿真目标 (内联可编辑)
              </th>
              <th class="py-2.5 px-3 min-w-[240px]">
                标准黄金答案 (Ground Truth)
              </th>
              <th class="py-2.5 px-3 w-44">指标与高级断言</th>
              <th class="py-2.5 px-3 w-36 text-right">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100 dark:divide-dark-800">
            <tr
              v-for="(row, idx) in filteredRows"
              :key="row.case_key"
              class="align-top hover:bg-gray-50/70 dark:hover:bg-dark-800/40"
              :class="row.dirty ? 'bg-amber-50/40 dark:bg-amber-950/10' : ''"
            >
              <td class="py-3 px-3 text-center font-mono text-gray-400">
                {{ idx + 1 }}
              </td>
              <td class="py-3 px-3 space-y-1.5">
                <input
                  v-model="row.case_key"
                  :disabled="!row.isNew"
                  class="pw-input w-full py-1 px-2 text-xs font-mono"
                  @input="row.dirty = true"
                />
                <div class="flex items-center gap-1.5">
                  <button
                    type="button"
                    class="text-[11px] px-1.5 py-0.5 rounded border border-gray-200 dark:border-dark-700"
                    @click="
                      row.split = row.split === 'dev' ? 'holdout' : 'dev';
                      row.dirty = true;
                    "
                  >
                    {{ row.split }}
                  </button>
                  <StatusPill :tone="row.raw.simulation ? 'info' : 'neutral'">
                    {{ row.raw.simulation ? "多轮博弈" : "单轮/脚本" }}
                  </StatusPill>
                </div>
              </td>
              <td class="py-2.5 px-3">
                <textarea
                  v-model="row.question"
                  rows="2"
                  placeholder="输入提问指令或仿真任务目标..."
                  class="pw-input w-full text-xs leading-relaxed resize-y"
                  @input="row.dirty = true"
                />
              </td>
              <td class="py-2.5 px-3">
                <textarea
                  v-model="row.ground_truth"
                  rows="2"
                  placeholder="输入黄金标准答案摘要..."
                  class="pw-input w-full text-xs font-mono leading-relaxed resize-y text-emerald-700 dark:text-emerald-300"
                  @input="row.dirty = true"
                />
              </td>
              <td class="py-3 px-3 space-y-1.5">
                <div class="flex flex-wrap gap-1">
                  <StatusPill
                    v-for="m in (row.raw.metrics || []).slice(0, 3)"
                    :key="typeof m === 'string' ? m : String(m.name)"
                    tone="neutral"
                  >
                    {{ typeof m === "string" ? m : String(m.name) }}
                  </StatusPill>
                </div>
                <div
                  v-if="(row.raw.expectations?.artifacts as unknown[])?.length"
                  class="text-[11px] text-primary-600"
                >
                  含
                  {{ (row.raw.expectations.artifacts as unknown[]).length }}
                  项物理产物断言
                </div>
              </td>
              <td class="py-3 px-3 text-right">
                <div class="flex items-center justify-end gap-1.5">
                  <BaseButton
                    size="sm"
                    variant="secondary"
                    @click="openAdvanced(row)"
                  >
                    高级
                  </BaseButton>
                  <BaseButton
                    size="sm"
                    variant="danger"
                    @click="removeRow(row)"
                  >
                    删
                  </BaseButton>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </SurfaceCard>

    <CaseAdvancedDrawer
      :show="showAdvancedDrawer"
      :item="drawerItem"
      @close="showAdvancedDrawer = false"
      @save="(payload) => emit('saveCase', payload)"
    />
  </div>
</template>

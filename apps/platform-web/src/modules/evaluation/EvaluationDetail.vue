<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseSelect from "@/components/base/BaseSelect.vue";
import SurfaceCard from "@/components/base/SurfaceCard.vue";
import PageHeader from "@/components/layout/PageHeader.vue";
import StateBanner from "@/components/platform/StateBanner.vue";
import MarkdownContent from "@/components/platform/MarkdownContent.vue";
import { useAuthorization } from "@/composables/useAuthorization";
import { useAuthStore } from "@/stores/auth";
import { useWorkspaceStore } from "@/stores/workspace";
import { getAgent } from "@/services/agents/agents.service";
import { listProjectMembers } from "@/services/members/members.service";
import {
  statusLabel,
  evaluationCheckLabels,
  workbenchCapabilities,
  type PendingAction,
  type Proposal,
  type Result,
} from "@/services/evaluation/workbench";
import { useWorkItem } from "./useWorkItem";
import CasePreview from "./CasePreview.vue";
import { proposalDiff } from "./proposalDiff";

const route = useRoute();
const auth = useAuthStore();
const workspace = useWorkspaceStore();
const agentName = ref("");
const { can } = useAuthorization();
const project = computed(() => String(route.params.projectId || ""));
const id = computed(() => String(route.params.itemId || ""));
const { item, busy, loading, error, pending, refresh, act } = useWorkItem(
  project,
  id,
);
watch(
  () => [project.value, item.value?.agent_id] as const,
  async ([current, agentId], _, onCleanup) => {
    let stale = false;
    onCleanup(() => {
      stale = true;
    });
    agentName.value = "";
    if (!agentId) return;
    const agent = await getAgent(current, agentId).catch(() => null);
    if (!stale) agentName.value = agent?.name || "Agent信息暂不可用";
  },
  { immediate: true },
);
const canExecute = computed(() =>
  can("project.evaluation.execute", project.value),
);
const canReview = computed(() =>
  can("project.evaluation.review", project.value),
);
const canManage = computed(() =>
  can("project.evaluation.manage", project.value),
);
const locked = computed(() => busy.value || !!pending.value);
const tab = ref("proposal");
const feedback = ref("");
const selected = ref<string[]>([]);
const version = computed(() => item.value?.versions?.slice(-1)[0]);
const differences = computed(() => {
  const previous = item.value?.versions?.slice(-2)[0];
  return previous &&
    version.value &&
    previous.revision !== version.value.revision
    ? proposalDiff(previous.proposal, version.value.proposal)
    : [];
});
const draft = ref<Proposal | null>(null);
const editing = ref(false);
const editReason = ref("");
const consent = ref(false);
const assistance = ref(true);
const regression = ref(true);
const hours = ref("24");
const model = ref("");
const revokeId = ref("");
const assignee = ref("");
const members = ref<{ value: string; label: string }[]>([]);
const selectedTask = ref("");
const compareTask = ref("");
const rescoreTask = ref("");
const disputeKind = ref("evidence_review");
const disputeReason = ref("");
const result = computed(
  () =>
    item.value?.results?.find((r) => r.task_id === selectedTask.value) ||
    item.value?.results?.slice(-1)[0],
);
const running = computed(() => [
  ...(item.value?.assistant_jobs || [])
    .filter((j) => ["reserved", "running", "cancelling"].includes(j.status))
    .map((j) => ({
      ...j,
      kind: "assistant",
      label:
        j.intent === "explain" || j.intent === "evidence_review"
          ? "AI结果分析"
          : "AI测试建议",
    })),
  ...(item.value?.operations || [])
    .filter((o) => !["completed", "cancelled", "error"].includes(o.stage))
    .map((o) => ({
      ...o,
      status: o.stage,
      kind: "evaluation",
      label: "Agent验证",
    })),
]);
const purposeLabel = (value: string) =>
  value === "evaluation_assistance" ? "AI分析与修订" : "固定题库和回归验证";
const date = (value: number) => new Date(value * 1000).toLocaleString();
const reviewerName = (value: string) =>
  members.value.find((m) => m.value === value)?.label ||
  (value === auth.user?.id ? "我" : value);
watch(
  () => version.value?.revision,
  () => {
    selected.value =
      version.value?.proposal.cases
        .filter(
          (c) =>
            !version.value?.proposal.case_missing_information?.[c.case_id]
              ?.length,
        )
        .map((c) => c.case_id) || [];
    editing.value = false;
    draft.value = null;
  },
);
watch(
  () => item.value?.status,
  (status) => {
    if (!status || status === "materials_unavailable") {
      feedback.value = "";
      disputeReason.value = "";
      draft.value = null;
      editing.value = false;
      editReason.value = "";
      selected.value = [];
    }
  },
);
watch(
  [project, id],
  async () => {
    const current = project.value;
    tab.value = "proposal";
    feedback.value = "";
    selectedTask.value = "";
    compareTask.value = "";
    consent.value = false;
    members.value = [];
    model.value = "";
    const capability = await workbenchCapabilities(current).catch(() => null);
    if (project.value === current)
      model.value = capability?.assistant_model || "未配置";
    if (canManage.value) {
      const values = await listProjectMembers(current).catch(() => []);
      if (project.value === current)
        members.value = values
          .filter((m) => ["project_admin", "project_editor"].includes(m.role))
          .map((m) => ({ value: m.user_id, label: m.username }));
    }
  },
  { immediate: true },
);
async function authorize() {
  for (const purpose of [
    assistance.value ? "evaluation_assistance" : "",
    regression.value ? "regression" : "",
  ].filter(Boolean)) {
    if (!item.value?.grants[purpose])
      await act("grant", {
        grant_id: crypto.randomUUID(),
        purpose,
        expires_in_hours: Number(hours.value),
        synthetic_attestation: consent.value,
      });
    if (error.value || pending.value) break;
  }
}
async function generate() {
  await act(version.value ? "revise" : "generate", {
    base_revision: item.value?.revision || 0,
    feedback:
      feedback.value.trim() ||
      "请根据问题及合成材料提出一小组有代表性的测试，明确正确预期和缺失口径。",
  });
  if (!error.value) feedback.value = "";
}
async function approve(action = "approve", sourceTask = "") {
  if (!version.value) return;
  await act(action, {
    revision: version.value.revision,
    content_hash: version.value.content_hash,
    selected_case_ids: selected.value,
    ...(sourceTask ? { source_task_id: sourceTask } : {}),
  });
  if (!error.value) tab.value = "results";
}
function edit() {
  draft.value = JSON.parse(JSON.stringify(version.value?.proposal));
  editing.value = true;
}
async function saveEdit() {
  if (!draft.value || !version.value) return;
  await act("edit", {
    base_revision: version.value.revision,
    proposal: draft.value,
    reason: editReason.value,
  });
  if (!error.value) editing.value = false;
}
async function decision(action: PendingAction, choice: string) {
  await act("tool_decision", {
    pending_action_id: action.id,
    parameters_hash: action.parameters_hash,
    revision: action.revision,
    decision: choice,
  });
}
async function dispute() {
  if (!result.value) return;
  await act("dispute", {
    task_id: result.value.task_id,
    judgment_revision: item.value?.judgments?.length || 0,
    kind: disputeKind.value,
    reason: disputeReason.value,
  });
  if (!error.value) disputeReason.value = "";
}
const taskOptions = computed(() =>
  (item.value?.results || []).map((r) => ({
    value: r.task_id,
    label: `${date(r.created_at)} · ${statusLabel(r.status)}`,
  })),
);
const actionLabel = (value: string) =>
  ({
    create: "提交问题",
    grant: "确认资料用途",
    generate: "请求AI方案",
    revise: "提出修改意见",
    edit: "编辑方案",
    approve: "批准并验证",
    run: "重新验证",
    cancel: "请求取消",
    assistant_bind: "关联助手运行",
    assistant_result: "保存AI建议",
    assistant_status: "核对助手终态",
    assign: "转交评审",
    tool_decision: "处理工具审批",
    dispute: "提出结果异议",
    regression: "加入回归集合",
    explain: "请求结果解释",
    compare: "比较运行",
    withdraw: "撤回问题",
    defer: "暂不处理",
  })[value] || value;
function canExplain(value: Result) {
  return (
    canExecute.value &&
    ["passed", "failed", "error", "cancelled"].includes(value.status) &&
    value.cases.length > 0
  );
}
</script>

<template>
  <main class="space-y-5">
    <RouterLink
      :to="{ name: 'workspace-evaluation', params: { projectId: project } }"
      class="text-sm text-primary-700 dark:text-primary-300"
      >返回评测与改进</RouterLink
    >
    <PageHeader
      :title="item?.title || '改进工作项'"
      :description="
        item?.next_action || '问题、方案、题库和每次验证都保留在这里。'
      "
    >
      <template #actions
        ><BaseButton
          variant="secondary"
          :disabled="busy || loading"
          @click="refresh()"
          >刷新</BaseButton
        ></template
      >
    </PageHeader>
    <p
      v-if="item && item.status !== 'materials_unavailable'"
      class="text-sm text-gray-500"
    >
      所属项目：{{
        workspace.projects.find((p) => p.id === project)?.name || "当前项目"
      }}
      · Agent：{{ agentName || "加载中" }} · 提交人：{{
        reviewerName(item.created_by)
      }}
    </p>
    <StateBanner
      v-if="error"
      variant="danger"
      title="本次操作未完成"
      :description="error"
    />
    <BaseButton
      v-if="pending"
      :disabled="busy"
      @click="act(pending.action, pending.command.data, true)"
      >核对并重试原请求</BaseButton
    >
    <p v-if="!item && loading" role="status">正在读取工作项…</p>
    <StateBanner
      v-if="item?.status === 'materials_unavailable'"
      variant="warning"
      title="资料已撤权、到期或暂时无法核实"
      description="问题正文、方案和结果已封闭。不会继续生成、发布或运行；旧授权不能用来恢复这些内容。"
    />
    <template v-if="item && item.status !== 'materials_unavailable'">
      <div class="flex flex-wrap items-center gap-3 text-sm" role="status">
        <strong>{{ statusLabel(item.status) }}</strong
        ><span>方案第 {{ item.revision }} 版</span
        ><span>更新于 {{ date(item.updated_at) }}</span>
      </div>
      <StateBanner
        v-if="item.source_changed"
        variant="warning"
        title="原回答的反馈已变化"
        description="请告诉AI按什么口径继续，生成新版本后再批准。旧方案与旧运行仍可查看。"
      />
      <SurfaceCard v-if="running.length" class="space-y-3">
        <div
          v-for="job in running"
          :key="job.id"
          class="flex flex-wrap items-center justify-between gap-3"
        >
          <div>
            <strong>{{ job.label }}</strong>
            <p class="mt-1 text-sm">
              {{ statusLabel(job.status) }} · 开始于 {{ date(job.created_at) }}
            </p>
          </div>
          <BaseButton
            v-if="canExecute && (job.created_by === auth.user?.id || canManage)"
            variant="danger"
            :disabled="locked || job.status === 'cancelling'"
            @click="act('cancel', { kind: job.kind, target_id: job.id })"
            >{{
              job.status === "cancelling" ? "等待停止确认" : "取消此任务"
            }}</BaseButton
          >
        </div>
        <p class="text-sm text-gray-500">
          可以离开页面，进度会保存。取消后会核对实际停止回执，已完成结果保留。
        </p>
      </SurfaceCard>
      <details :open="!item.grants.evaluation_assistance" class="pw-card p-5">
        <summary class="cursor-pointer font-semibold">管理资料使用</summary>
        <p class="my-3 text-sm">
          本工作项仅处理你主动提交的合成说明、文件和获准评测结果。AI分析使用受管模型
          {{
            model
          }}；聊天原文、工具原文和检索正文不默认外发。授权可分别撤销，派生方案和记录随之封闭。
        </p>
        <ul class="mb-3 space-y-2 text-sm">
          <li
            v-for="(grantId, purpose) in item.grants"
            :key="grantId"
            class="flex flex-wrap items-center gap-3"
          >
            <span>{{ purposeLabel(String(purpose)) }}：已授权</span
            ><BaseButton
              v-if="canManage"
              variant="ghost"
              size="sm"
              :disabled="locked"
              @click="revokeId = grantId"
              >撤销此用途</BaseButton
            >
          </li>
        </ul>
        <div
          v-if="revokeId"
          class="mb-4 space-y-3 rounded-xl border border-amber-300 p-4"
        >
          <p>
            撤销后，本工作项的方案、AI意见、题库和关联运行将封闭，并停止后续处理。此操作不撤销另行批准的线上巡检用途。
          </p>
          <BaseButton
            variant="danger"
            :disabled="locked"
            @click="
              act('revoke', { grant_id: revokeId });
              revokeId = '';
            "
            >确认撤销</BaseButton
          ><BaseButton variant="ghost" @click="revokeId = ''">返回</BaseButton>
        </div>
        <div
          v-if="
            canManage &&
            (!item.grants.evaluation_assistance || !item.grants.regression)
          "
          class="space-y-3"
        >
          <label v-if="!item.grants.evaluation_assistance" class="block"
            ><input v-model="assistance" type="checkbox" />
            允许AI整理、修订方案和解释结果</label
          >
          <label v-if="!item.grants.regression" class="block"
            ><input v-model="regression" type="checkbox" />
            允许固定题库和运行回归验证</label
          >
          <div class="max-w-xs">
            <label id="grant-hours">有效期</label
            ><BaseSelect
              v-model="hours"
              aria-labelledby="grant-hours"
              :options="[
                { value: '1', label: '1小时' },
                { value: '4', label: '4小时' },
                { value: '24', label: '24小时' },
              ]"
            />
          </div>
          <label class="block text-sm"
            ><input v-model="consent" type="checkbox" />
            我确认资料为合成内容，允许在相同字段、模型和用途内修订；每次批准仍绑定具体版本。</label
          >
          <BaseButton
            :disabled="locked || !consent || (!assistance && !regression)"
            @click="authorize"
            >确认选定用途</BaseButton
          >
        </div>
        <p v-else-if="!item.grants.evaluation_assistance" class="text-sm">
          请项目管理员在此确认资料用途后，再让AI生成建议。
        </p>
      </details>
      <nav aria-label="工作项内容" class="flex flex-wrap gap-2">
        <BaseButton
          v-for="option in [
            { id: 'proposal', label: '问题与方案' },
            { id: 'results', label: '运行与结果' },
            { id: 'history', label: '历史记录' },
          ]"
          :key="option.id"
          :variant="tab === option.id ? 'primary' : 'secondary'"
          :aria-current="tab === option.id ? 'page' : undefined"
          @click="tab = option.id"
          >{{ option.label }}</BaseButton
        >
      </nav>
      <div
        v-if="tab === 'proposal'"
        class="grid gap-5 xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]"
      >
        <div class="space-y-5">
          <SurfaceCard
            ><h2 class="mb-3 font-semibold">最初的问题</h2>
            <p class="whitespace-pre-wrap leading-7">
              {{ item.description }}
            </p></SurfaceCard
          >
          <SurfaceCard v-if="version" class="space-y-4">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <h2 class="text-lg font-semibold">
                {{ version.source === "ai" ? "AI建议" : "已编辑方案" }} · 第
                {{ version.revision }} 版
              </h2>
              <BaseButton
                v-if="canReview"
                variant="ghost"
                :disabled="locked"
                @click="edit"
                >编辑方案</BaseButton
              >
            </div>
            <p class="whitespace-pre-wrap leading-7">
              {{ version.proposal.summary }}
            </p>
            <div v-if="version.proposal.changes.length">
              <h3 class="font-medium">本版改了什么</h3>
              <ul class="mt-2 list-disc space-y-1 pl-5">
                <li v-for="change in version.proposal.changes" :key="change">
                  {{ change }}
                </li>
              </ul>
            </div>
            <div v-if="version.proposal.facts.length">
              <h3 class="font-medium">依据的事实</h3>
              <ul class="list-disc pl-5">
                <li v-for="fact in version.proposal.facts" :key="fact">
                  {{ fact }}
                </li>
              </ul>
            </div>
            <details v-if="differences.length" class="rounded-lg border p-3">
              <summary class="cursor-pointer font-medium">
                和上一版逐项比较（{{ differences.length }}处）
              </summary>
              <div
                v-for="difference in differences"
                :key="difference.label"
                class="mt-3 space-y-1 text-sm"
              >
                <strong>{{ difference.label }}</strong>
                <p class="whitespace-pre-wrap break-words">
                  之前：{{ difference.before }}
                </p>
                <p class="whitespace-pre-wrap break-words">
                  现在：{{ difference.after }}
                </p>
              </div>
            </details>
            <div v-if="version.proposal.hypotheses.length">
              <h3 class="font-medium">仍需验证的推测</h3>
              <ul class="list-disc pl-5">
                <li v-for="fact in version.proposal.hypotheses" :key="fact">
                  {{ fact }}
                </li>
              </ul>
            </div>
            <StateBanner
              v-if="version.proposal.missing_information.length"
              variant="warning"
              title="先补充这些口径，才能验证"
              :description="version.proposal.missing_information.join('；')"
            />
            <h3 class="font-semibold">这次验证哪些情况</h3>
            <div
              v-for="test in version.proposal.cases"
              :key="test.case_id"
              class="space-y-3 rounded-xl border border-gray-200 p-4 dark:border-dark-700"
            >
              <label class="flex items-center gap-2 font-medium"
                ><input
                  v-model="selected"
                  type="checkbox"
                  :value="test.case_id"
                  :disabled="
                    locked ||
                    !!version.proposal.case_missing_information?.[test.case_id]
                      ?.length
                  "
                />{{ test.case_id }}</label
              >
              <p
                v-if="
                  version.proposal.case_missing_information?.[test.case_id]
                    ?.length
                "
                class="text-sm text-amber-700"
              >
                本题暂不运行：{{
                  version.proposal.case_missing_information[test.case_id]?.join(
                    "；",
                  )
                }}
              </p>
              <CasePreview :test="test" />
            </div>
            <p v-if="version.proposal.excluded.length" class="text-sm">
              本方案不覆盖：{{ version.proposal.excluded.join("；") }}
            </p>
            <p class="text-sm">
              已选 {{ selected.length }} /
              {{ version.proposal.cases.length }}
              题。未选题不会发布；批准后本版内容固定。
            </p>
            <div class="flex flex-wrap gap-2">
              <BaseButton
                v-if="canReview"
                :disabled="
                  locked ||
                  !selected.length ||
                  !item.grants.regression ||
                  !!version.proposal.missing_information.length ||
                  item.source_changed ||
                  !!running.length
                "
                @click="approve()"
                >同意方案并验证</BaseButton
              ><BaseButton
                v-if="
                  canExecute &&
                  item.operations?.some((o) => o.revision === version?.revision)
                "
                variant="secondary"
                :disabled="locked || !!running.length"
                @click="approve('run')"
                >重跑已批准选题</BaseButton
              >
            </div>
            <div
              v-if="canReview && taskOptions.length"
              class="space-y-3 border-t pt-4"
            >
              <h3 class="font-medium">只改了评分标准？</h3>
              <p class="text-sm">
                选择旧运行，按本版标准重新评分。不会再次调用被测Agent；提问、文件或操作发生变化时系统会拒绝复用。
              </p>
              <BaseSelect
                v-model="rescoreTask"
                :options="taskOptions"
                aria-label="重新评分的旧运行"
                placeholder="选择要重新评分的运行"
              />
              <BaseButton
                variant="secondary"
                :disabled="
                  locked ||
                  !rescoreTask ||
                  !selected.length ||
                  !!running.length ||
                  !!item.source_changed ||
                  !!version.proposal.missing_information.length
                "
                @click="approve('approve', rescoreTask)"
                >同意新标准，仅重评旧证据</BaseButton
              >
            </div>
          </SurfaceCard>
          <SurfaceCard v-if="editing && draft" class="space-y-3">
            <h2 class="font-semibold">编辑后保存为新版本</h2>
            <label class="block"
              >方案摘要<textarea
                v-model="draft.summary"
                class="pw-input w-full"
                rows="3"
              />
            </label>
            <div
              v-for="test in draft.cases"
              :key="test.case_id"
              class="space-y-2"
            >
              <strong>{{ test.case_id }}</strong
              ><label
                v-for="(turn, index) in test.turns"
                :key="index"
                class="block"
                >第 {{ index + 1 }} 轮输入<textarea
                  v-model="turn.content"
                  class="pw-input w-full"
                  rows="2"
                /></label
              ><label
                v-for="(_, index) in test.expectations.answer_contains"
                :key="index"
                class="block"
                >预期包含<input
                  v-model="test.expectations.answer_contains![index]"
                  class="pw-input w-full"
              /></label>
            </div>
            <label class="block"
              >修改原因<input
                v-model="editReason"
                class="pw-input w-full"
                maxlength="2000" /></label
            ><BaseButton
              :disabled="locked || !editReason.trim()"
              @click="saveEdit"
              >保存新版本</BaseButton
            ><BaseButton variant="ghost" @click="editing = false"
              >取消编辑</BaseButton
            >
          </SurfaceCard>
        </div>
        <div class="space-y-5">
          <SurfaceCard class="space-y-4"
            ><h2 class="font-semibold">
              {{ version ? "告诉AI哪里需要改" : "让AI准备方案" }}
            </h2>
            <p class="text-sm text-gray-500">
              例如：“退款按发生月份算，再加一个拒绝写文件的测试。”不知道标准答案也可以先说清你希望验证的行为。
            </p>
            <textarea
              v-model="feedback"
              aria-label="给AI的修改意见"
              rows="5"
              maxlength="8000"
              class="pw-input w-full"
            /><BaseButton
              v-if="canExecute"
              :disabled="
                locked || !item.grants.evaluation_assistance || !!running.length
              "
              @click="generate"
              >{{ version ? "按意见修改方案" : "生成测试建议" }}</BaseButton
            >
            <p class="text-xs text-gray-500">
              AI建议由受管模型生成；业务口径仍由你评审。共享模型验证不是独立盲测。
            </p></SurfaceCard
          >
          <SurfaceCard v-if="canManage" class="space-y-3"
            ><h2 class="font-semibold">评审负责人</h2>
            <p class="text-sm">
              在线工具审批只允许当前指派的人处理；未指派时由批准方案的人处理。
            </p>
            <BaseSelect
              v-model="assignee"
              :options="members"
              placeholder="选择项目评审人"
              aria-label="评审负责人"
            /><BaseButton
              variant="secondary"
              :disabled="locked || !assignee"
              @click="act('assign', { assignee })"
              >转交评审</BaseButton
            >
            <p v-if="item.assignee" class="text-sm">
              当前：{{ reviewerName(item.assignee) }}
            </p></SurfaceCard
          >
          <details class="pw-card p-5">
            <summary class="cursor-pointer">暂不处理这个问题</summary>
            <p class="my-3 text-sm">
              撤回问题不会撤销资料授权，也不会删除已运行历史。要禁止资料继续使用，请在上方“管理资料使用”撤销授权。
            </p>
            <BaseButton
              variant="secondary"
              :disabled="locked || !!running.length"
              @click="act('defer', { reason: '用户暂不处理' })"
              >暂不处理</BaseButton
            ><BaseButton
              variant="ghost"
              :disabled="locked || !!running.length"
              @click="act('withdraw', { reason: '用户撤回问题' })"
              >撤回问题</BaseButton
            >
          </details>
        </div>
      </div>
      <div v-if="tab === 'results'" class="space-y-5">
        <SurfaceCard v-if="!item.operations?.length"
          ><p>
            还没有运行。评审方案后点击“同意方案并验证”，题库和结果会出现在这里。
          </p></SurfaceCard
        >
        <SurfaceCard
          v-for="operation in item.operations"
          :key="operation.id"
          class="space-y-2"
          ><h2 class="font-semibold">
            第 {{ operation.revision }} 版方案 ·
            {{ statusLabel(operation.stage) }}
          </h2>
          <p class="text-sm">
            本次选题：{{ operation.selected_case_ids.join("、") }}
          </p>
          <p v-if="operation.excluded_case_ids?.length" class="text-sm">
            本次未选：{{
              operation.excluded_case_ids.join("、")
            }}。未选题不会运行。
          </p>
          <p v-if="operation.source_task_id" class="text-sm">
            本次仅对旧证据重新评分，没有重新运行Agent。
          </p>
          <details v-if="operation.dataset_id">
            <summary class="cursor-pointer font-medium">
              查看本次固定题库 v{{ operation.dataset_version }}
            </summary>
            <div
              v-for="test in item.versions
                ?.find((v) => v.revision === operation.revision)
                ?.proposal.cases.filter((c) =>
                  operation.selected_case_ids.includes(c.case_id),
                )"
              :key="test.case_id"
              class="mt-4 rounded-lg border p-4"
            >
              <h3 class="mb-3 font-medium">{{ test.case_id }}</h3>
              <CasePreview :test="test" />
            </div>
          </details>
          <details class="text-xs text-gray-500">
            <summary class="cursor-pointer">技术编号</summary>
            <p>题库：{{ operation.dataset_id || "准备中" }}</p>
            <p>运行：{{ operation.task_id || "尚未启动" }}</p>
          </details></SurfaceCard
        >
        <BaseSelect
          v-if="taskOptions.length"
          v-model="selectedTask"
          :options="taskOptions"
          placeholder="选择一次运行（默认最新）"
          aria-label="选择运行"
        />
        <template v-if="result">
          <SurfaceCard class="space-y-3"
            ><h2 class="text-lg font-semibold">
              {{ statusLabel(result.status) }} · 已处理 {{ result.completed }} /
              {{ result.total }} 题
            </h2>
            <p v-if="result.error" role="alert">{{ result.error }}</p>
            <p class="text-sm text-gray-500">
              规则和安全检查决定正式结果。AI解释、人工接受风险不会擦掉未通过项。
            </p>
            <div class="flex flex-wrap gap-2">
              <BaseButton
                v-if="canExplain(result)"
                :disabled="locked || !!running.length"
                @click="act('explain', { task_id: result.task_id })"
                >让AI解释结果</BaseButton
              ><BaseButton
                v-if="canReview"
                variant="secondary"
                :disabled="locked || item.regression_set"
                @click="act('regression', {})"
                >{{
                  item.regression_set ? "已加入回归集合" : "加入回归集合"
                }}</BaseButton
              >
            </div></SurfaceCard
          >
          <SurfaceCard
            v-for="approval in result.pending_actions.filter(
              (a) => a.status === 'pending',
            )"
            :key="approval.id"
            class="space-y-4"
          >
            <h2 class="text-lg font-semibold">
              需要你的决定：{{ approval.case_id }} 工具操作审批
            </h2>
            <p>
              负责人：{{ reviewerName(item.assignee || approval.assignee) }} ·
              截止 {{ date(approval.expires_at) }}
            </p>
            <div v-for="interrupt in approval.interrupts" :key="interrupt.id">
              <div
                v-for="(request, index) in interrupt.value.action_requests"
                :key="index"
                class="mt-3"
              >
                <strong>{{ request.name }}</strong>
                <dl>
                  <div
                    v-for="(value, key) in request.args"
                    :key="key"
                    class="mt-2"
                  >
                    <dt class="text-xs font-medium text-gray-500">
                      {{
                        key === "file_path"
                          ? "目标文件"
                          : key === "content"
                            ? "准备写入的内容"
                            : key
                      }}
                    </dt>
                    <dd class="break-words text-sm">
                      <MarkdownContent
                        v-if="key === 'content' && typeof value === 'string'"
                        :content="value"
                        disable-images
                      />
                      <template v-else>{{
                        typeof value === "string"
                          ? value
                          : JSON.stringify(value)
                      }}</template>
                    </dd>
                  </div>
                </dl>
              </div>
            </div>
            <p class="text-sm">
              这里只批准上述精确工具参数，不能代替其他操作的授权。过期后系统停止，不自动同意。
            </p>
            <div class="flex gap-3">
              <BaseButton
                :disabled="
                  locked ||
                  !canReview ||
                  (item.assignee || approval.assignee) !== auth.user?.id
                "
                @click="decision(approval, 'approve')"
                >批准本次操作</BaseButton
              ><BaseButton
                variant="danger"
                :disabled="
                  locked ||
                  !canReview ||
                  (item.assignee || approval.assignee) !== auth.user?.id
                "
                @click="decision(approval, 'reject')"
                >拒绝本次操作</BaseButton
              >
            </div>
          </SurfaceCard>
          <SurfaceCard
            v-for="test in result.cases"
            :id="`evidence-${test.case_id}`"
            :key="test.case_id"
            class="space-y-3"
            ><h2 class="font-semibold">
              {{ test.case_id }} · {{ statusLabel(test.status) }}
            </h2>
            <div v-for="(output, index) in test.outputs" :key="index">
              <h3 class="text-sm font-medium">第 {{ index + 1 }} 轮实际回答</h3>
              <MarkdownContent class="mt-1" :content="output" disable-images />
            </div>
            <details v-for="(file, path) in test.artifacts" :key="path">
              <summary class="cursor-pointer">
                查看已批准检查的文件：{{ path }}
              </summary>
              <p v-if="file.content === null" class="mt-2 text-sm">
                文件不存在。
              </p>
              <MarkdownContent
                v-else-if="String(path).endsWith('.md')"
                :content="file.content"
                disable-images
                class="mt-2"
              />
              <pre
                v-else
                class="mt-2 overflow-auto whitespace-pre-wrap break-words text-sm"
                >{{ file.content }}</pre
              >
              <p v-if="file.truncated" class="text-sm text-amber-700">
                仅展示前20,000字；AI解释使用同一片段，不能判断未展示部分。
              </p>
            </details>
            <ul class="space-y-3">
              <li v-for="metric in test.results" :key="metric.name">
                <strong class="text-sm"
                  >{{ statusLabel(metric.status) }} ·
                  {{
                    evaluationCheckLabels[metric.name] || metric.name
                  }}</strong
                >
                <p class="mt-1 text-sm">{{ metric.reason }}</p>
              </li>
            </ul>
            <p v-if="test.errors.length" class="text-sm text-red-600">
              缺失证据或执行异常：{{ test.errors.join("；") }}
            </p></SurfaceCard
          >
          <SurfaceCard
            v-if="result.evidence?.approved_standard"
            id="evidence-approved_standard"
            class="space-y-3"
          >
            <h2 class="font-semibold">这次运行实际使用的测试标准</h2>
            <p class="text-sm">
              {{ result.evidence.approved_standard.dataset_name }} · 固定题库第
              {{ result.evidence.approved_standard.version }}
              版。下面是当时批准的内容，后续修改不会覆盖它。
            </p>
            <details
              v-for="test in result.evidence.approved_standard.cases"
              :key="test.case_id"
            >
              <summary class="cursor-pointer">
                {{ test.case_id }} · 查看判断依据
              </summary>
              <ul class="mt-2 list-disc space-y-1 pl-5 text-sm">
                <li v-for="rule in test.business_rules" :key="rule">
                  {{ rule }}
                </li>
              </ul>
              <p v-if="test.expectations.rubric" class="mt-2 text-sm">
                {{ test.expectations.rubric }}
              </p>
              <p
                v-for="turn in test.turn_expectations"
                :key="turn.index"
                class="mt-2 text-sm"
              >
                第 {{ turn.index + 1 }} 轮：
                {{
                  turn.answer_equals != null
                    ? `精确回答 ${turn.answer_equals}`
                    : turn.answer_contains.join("；") || "按文件与行为规则检查"
                }}
              </p>
            </details>
            <p class="text-xs text-gray-500">
              {{ result.evidence.approved_standard.review_note }}
            </p>
          </SurfaceCard>
          <SurfaceCard
            v-for="judgment in item.judgments?.filter(
              (j) => j.task_id === result?.task_id,
            )"
            :key="judgment.revision"
            class="space-y-3"
            ><h2 class="font-semibold">
              {{
                judgment.source === "ai"
                  ? "AI建议（非独立人审）"
                  : "人工评审记录"
              }}
              · {{ date(judgment.at) }}
            </h2>
            <p>{{ judgment.explanation?.summary || judgment.reason }}</p>
            <ul v-if="judgment.explanation" class="list-disc space-y-2 pl-5">
              <li
                v-for="finding in judgment.explanation.findings"
                :key="finding"
              >
                {{ finding }}
              </li>
            </ul>
            <p
              v-if="judgment.explanation?.limitations.length"
              class="text-sm text-gray-500"
            >
              限制：{{ judgment.explanation.limitations.join("；") }}
            </p>
            <div class="flex flex-wrap gap-3">
              <a
                v-for="reference in judgment.explanation?.evidence_refs"
                :key="reference"
                :href="`#evidence-${reference.replace('case:', '')}`"
                class="text-sm text-primary-700"
                >{{
                  reference === "approved_standard"
                    ? "查看本次批准的标准"
                    : `查看 ${reference.replace("case:", "")} 证据`
                }}</a
              >
            </div></SurfaceCard
          >
          <SurfaceCard v-if="canExecute" class="space-y-3"
            ><h2 class="font-semibold">这个评价不对？</h2>
            <BaseSelect
              v-model="disputeKind"
              aria-label="异议处理方式"
              :options="[
                {
                  value: 'evidence_review',
                  label: 'AI复核同一份证据（不重跑工具）',
                },
                { value: 'change_standard', label: '修改测试标准，另起新版本' },
                {
                  value: 'accept_risk',
                  label: '保留失败，记录接受风险',
                  disabled: !canReview,
                },
              ]"
            /><textarea
              v-model="disputeReason"
              aria-label="异议理由"
              class="pw-input w-full"
              rows="3"
              placeholder="说明遗漏了哪项证据，或哪条业务标准需要调整。"
            /><BaseButton
              variant="secondary"
              :disabled="locked || !disputeReason.trim() || !!running.length"
              @click="dispute"
              >提交评审意见</BaseButton
            ></SurfaceCard
          >
          <SurfaceCard v-if="taskOptions.length > 1" class="space-y-3"
            ><h2 class="font-semibold">和之前的运行比较</h2>
            <BaseSelect
              v-model="compareTask"
              :options="taskOptions.filter((o) => o.value !== result?.task_id)"
              aria-label="比较基准运行"
              placeholder="选择另一运行"
            /><BaseButton
              variant="secondary"
              :disabled="locked || !compareTask"
              @click="
                act('compare', {
                  left_task_id: compareTask,
                  right_task_id: result.task_id,
                })
              "
              >核对是否可比较</BaseButton
            >
            <p v-if="item.comparison && !item.comparison.compatible">
              {{ item.comparison.reason }}
            </p>
            <div
              v-for="row in item.comparison?.cases"
              :key="row.case_id"
              class="text-sm"
            >
              <strong>{{ row.case_id }}</strong>
              <p>
                之前：{{
                  row.before
                    .map((m) => `${m.name} ${statusLabel(m.status)}`)
                    .join("；")
                }}
              </p>
              <p>
                本次：{{
                  row.after
                    .map((m) => `${m.name} ${statusLabel(m.status)}`)
                    .join("；")
                }}
              </p>
            </div></SurfaceCard
          >
        </template>
      </div>
      <div v-if="tab === 'history'" class="space-y-5">
        <SurfaceCard
          v-for="previous in [...(item.versions || [])].reverse()"
          :key="previous.revision"
          class="space-y-2"
          ><h2 class="font-semibold">
            第 {{ previous.revision }} 版 ·
            {{ previous.source === "ai" ? "AI建议" : "人工编辑" }}
          </h2>
          <p>{{ previous.proposal.summary }}</p>
          <ul class="list-disc pl-5">
            <li v-for="change in previous.proposal.changes" :key="change">
              {{ change }}
            </li>
          </ul>
          <details>
            <summary class="cursor-pointer text-sm">查看当时的完整方案</summary>
            <div
              v-for="test in previous.proposal.cases"
              :key="test.case_id"
              class="my-4 border-t pt-3"
            >
              <strong>{{ test.case_id }}</strong
              ><CasePreview :test="test" />
            </div></details
        ></SurfaceCard>
        <SurfaceCard
          ><h2 class="mb-4 font-semibold">操作记录</h2>
          <ol class="space-y-3">
            <li
              v-for="(event, index) in [...(item.history || [])].reverse()"
              :key="index"
              class="text-sm"
            >
              <strong>{{ actionLabel(event.action) }}</strong> ·
              {{ date(event.at) }}
              <p class="mt-1 text-gray-500">
                {{
                  event.source === "human"
                    ? reviewerName(event.actor_id)
                    : event.source === "ai"
                      ? "AI建议"
                      : "系统回执"
                }}
                {{ event.reason }}
              </p>
            </li>
          </ol></SurfaceCard
        >
      </div>
    </template>
  </main>
</template>

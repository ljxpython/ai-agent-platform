<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseSelect from "@/components/base/BaseSelect.vue";
import SurfaceCard from "@/components/base/SurfaceCard.vue";
import PageHeader from "@/components/layout/PageHeader.vue";
import StateBanner from "@/components/platform/StateBanner.vue";
import PaginationBar from "@/components/platform/PaginationBar.vue";
import { useAuthorization } from "@/composables/useAuthorization";
import { useAuthStore } from "@/stores/auth";
import { listAgents } from "@/services/agents/agents.service";
import {
  commandWorkItem,
  listWorkItems,
  readSummary,
  statusLabel,
  workbenchCapabilities,
  type Command,
  type Summary,
  type WorkItem,
} from "@/services/evaluation/workbench";
import { extractPlatformHttpError } from "@/utils/http-error";

const route = useRoute();
const router = useRouter();
const { can } = useAuthorization();
const auth = useAuthStore();
const group = ref("");
const project = computed(() => String(route.params.projectId || ""));
const entries = ref<WorkItem[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const query = ref("");
const status = ref("");
const error = ref("");
const busy = ref(false);
const loading = ref(false);
const enabled = ref(false);
const loaded = ref(false);
const summary = ref<Summary | null>(null);
const creating = ref(route.query.new === "1");
const title = ref("");
const description = ref("");
const agentId = ref("");
const agents = ref<{ value: string; label: string }[]>([]);
const fixture = ref<Record<string, string>>({});
const synthetic = ref(false);
const sourceInspectionId = ref("");
const filterAgent = ref("");
const filterCreator = ref("");
const pending = ref<Command | null>(null);
let epoch = 0;
const statuses = [
  "",
  "awaiting_authorization",
  "awaiting_review",
  "needs_information",
  "running",
  "completed",
  "error",
  "cancelled",
  "materials_unavailable",
].map((value) => ({ value, label: value ? statusLabel(value) : "全部状态" }));
async function load() {
  const current = epoch;
  loading.value = true;
  error.value = "";
  try {
    const capability = await workbenchCapabilities(project.value);
    if (current !== epoch) return;
    enabled.value = capability.workbench;
    loaded.value = true;
    if (!enabled.value) return;
    const result = await listWorkItems(project.value, {
      query: query.value,
      status: status.value,
      agent_id: filterAgent.value,
      created_by: filterCreator.value,
      group: group.value,
      offset: (page.value - 1) * pageSize.value,
      limit: pageSize.value,
    });
    if (current !== epoch) return;
    entries.value = result.items;
    total.value = result.total;
    if (can("project.evaluation.review", project.value)) {
      const value = await readSummary(project.value);
      if (current === epoch) summary.value = value;
    }
  } catch (cause) {
    if (current === epoch) {
      error.value = extractPlatformHttpError(cause).message;
      entries.value = [];
      summary.value = null;
    }
  } finally {
    if (current === epoch) loading.value = false;
  }
}
async function loadAgents() {
  const current = epoch;
  try {
    const value = await listAgents(project.value, { limit: 100 });
    if (current === epoch)
      agents.value = value.items
        .filter((a) => a.status === "active" && a.graph_id === "dearflow_agent")
        .map((a) => ({ value: a.id, label: a.name }));
  } catch (cause) {
    if (current === epoch)
      error.value = extractPlatformHttpError(cause).message;
  }
}
async function files(event: Event) {
  const current = epoch;
  const values = Array.from((event.target as HTMLInputElement).files || []);
  if (
    values.length > 20 ||
    values.reduce((size, file) => size + file.size, 0) > 200000
  ) {
    error.value = "最多20个合成文本文件，合计不超过200KB。";
    return;
  }
  const pairs = await Promise.all(
    values.map(async (file) => [file.name, await file.text()] as const),
  );
  if (current === epoch) fixture.value = Object.fromEntries(pairs);
}
async function create() {
  const current = epoch;
  busy.value = true;
  error.value = "";
  pending.value ||= {
    request_id: crypto.randomUUID(),
    data: {
      title: title.value,
      description: description.value,
      agent_id: agentId.value,
      fixture: { ...fixture.value },
      synthetic_attestation: synthetic.value,
      share_with_project_reviewers: synthetic.value,
      ...(sourceInspectionId.value
        ? { source_inspection_id: sourceInspectionId.value }
        : {}),
      ...(typeof route.query.thread === "string"
        ? {
            source_thread_id: route.query.thread,
            source_message_id: route.query.message,
          }
        : {}),
    },
  };
  try {
    const result = await commandWorkItem(
      project.value,
      null,
      "create",
      pending.value,
    );
    if (current !== epoch) return;
    pending.value = null;
    await router.push({
      name: "workspace-evaluation-detail",
      params: { projectId: project.value, itemId: result.id },
    });
  } catch (cause) {
    if (current !== epoch) return;
    const detail = extractPlatformHttpError(cause);
    error.value = detail.message;
    if (detail.status && detail.status >= 400 && detail.status < 500)
      pending.value = null;
  } finally {
    if (current === epoch) busy.value = false;
  }
}
watch(
  project,
  () => {
    epoch++;
    entries.value = [];
    summary.value = null;
    pending.value = null;
    title.value = "";
    description.value = "";
    fixture.value = {};
    synthetic.value = false;
    sourceInspectionId.value = "";
    filterAgent.value = "";
    filterCreator.value = "";
    agentId.value = "";
    enabled.value = false;
    loaded.value = false;
    page.value = 1;
    void load();
    void loadAgents();
  },
  { immediate: true },
);
watch([page, pageSize], () => void load());
onBeforeUnmount(() => epoch++);
</script>

<template>
  <main class="space-y-5">
    <PageHeader
      title="评测与改进"
      description="说清你想验证的问题，AI准备方案；你确认后，系统完成题库、验证和结果整理。"
    >
      <template #actions
        ><BaseButton
          v-if="enabled && can('project.evaluation.execute', project)"
          @click="creating = !creating"
          >{{ creating ? "收起新建" : "新建测试需求" }}</BaseButton
        ><BaseButton variant="secondary" :disabled="loading" @click="load"
          >刷新</BaseButton
        ></template
      >
    </PageHeader>
    <StateBanner
      v-if="error"
      variant="danger"
      title="暂时无法完成操作"
      :description="error"
    />
    <StateBanner
      v-if="loaded && !enabled"
      title="当前项目尚未启用评测工作台"
      description="原聊天和原评测入口仍可使用；请联系项目管理员确认本项目是否已接入。"
    />
    <template v-if="enabled">
      <div
        v-if="creating"
        class="grid gap-5 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]"
      >
        <SurfaceCard>
          <h2 class="mb-4 text-lg font-semibold">你希望 Agent 做对什么？</h2>
          <form class="space-y-4" @submit.prevent="create">
            <fieldset :disabled="busy || !!pending" class="space-y-4">
              <label class="block"
                >名称<input
                  v-model="title"
                  required
                  maxlength="120"
                  class="pw-input mt-1 w-full"
                  placeholder="例如：十月退款统计口径"
              /></label>
              <div>
                <label id="evaluation-agent-label">要验证的 Agent</label
                ><BaseSelect
                  v-model="agentId"
                  :options="agents"
                  aria-labelledby="evaluation-agent-label"
                  placeholder="选择当前项目的 Agent"
                />
              </div>
              <label class="block"
                >问题和业务口径<textarea
                  v-model="description"
                  required
                  rows="6"
                  maxlength="12000"
                  class="pw-input mt-1 w-full"
                  placeholder="例如：请验证31加24是否正确，并考虑用户追问再减10。由AI提出预期答案与测试步骤。"
                />
              </label>
              <label class="block"
                >合成文件（选填）<input
                  type="file"
                  multiple
                  accept=".csv,.txt,.md,.json"
                  class="mt-2 block w-full text-sm"
                  @change="files"
              /></label>
              <p
                v-if="Object.keys(fixture).length"
                class="text-sm text-gray-500"
              >
                已选择：{{ Object.keys(fixture).join("、") }}
              </p>
              <label class="flex items-start gap-2 text-sm"
                ><input
                  v-model="synthetic"
                  type="checkbox"
                  class="mt-1"
                />我确认提交的是虚构示例，允许当前项目评审者查看；不包含真实个人信息、业务秘密或密钥。</label
              >
            </fieldset>
            <BaseButton
              type="submit"
              :disabled="
                busy ||
                !title.trim() ||
                !description.trim() ||
                !agentId ||
                !synthetic
              "
              >{{
                busy ? "保存中…" : pending ? "核对并重试原提交" : "保存测试需求"
              }}</BaseButton
            >
          </form>
        </SurfaceCard>
        <SurfaceCard class="space-y-4">
          <h2 class="text-lg font-semibold">保存之后会发生什么</h2>
          <p>
            问题会成为一个可找回的工作项。先由项目管理员确认资料用途，AI再给出一小组有代表性的测试建议。
          </p>
          <p>
            你只需检查口径与风险，认可后点“同意方案并验证”。不认可就直接说哪里要改。
          </p>
          <p class="text-sm text-gray-500">
            合成文件是为测试编造的小样本。例如虚构订单号、金额和退款日期。这里的勾选只是提交确认，AI分析与回归的用途授权会分别说明。
          </p>
          <p v-if="route.query.thread" class="text-sm">
            本需求关联原回答的位置；聊天原文不会随此操作复制给评测助手。
          </p>
        </SurfaceCard>
      </div>
      <SurfaceCard v-if="summary" class="space-y-3">
        <h2 class="font-semibold">当前项目的验证情况</h2>
        <p>
          {{ summary.work_items }} 个可见工作项 · {{ summary.runs }} 次运行 ·
          {{ summary.completed_runs }} 次完成评测
        </p>
        <div class="flex flex-wrap gap-4 text-sm">
          <span v-for="(count, state) in summary.statuses" :key="state"
            >{{ statusLabel(String(state)) }} {{ count }}</span
          >
        </div>
        <p class="text-sm text-gray-500">{{ summary.notes.join(" ") }}</p>
        <p class="text-sm">线上巡检：{{ summary.inspection.reason }}</p>
        <p class="text-sm text-gray-500">{{ summary.inspection.notes }}</p>
        <ul v-if="summary.inspection.results?.length" class="space-y-3">
          <li
            v-for="inspection in summary.inspection.results"
            :key="inspection.id"
            class="flex flex-wrap items-center gap-3 text-sm"
          >
            <span
              >{{
                agents.find((a) => a.value === inspection.agent_id)?.label ||
                "项目Agent"
              }}
              · {{ inspection.policy_version }} · 得分 {{ inspection.score }} /
              1</span
            >
            <BaseButton
              variant="secondary"
              size="sm"
              @click="
                sourceInspectionId = inspection.id;
                agentId = inspection.agent_id;
                title = '核查巡检提示';
                description = `这次合成巡检在${inspection.policy_version}标准下得分${inspection.score}。请帮我设计有代表性的测试来核查任务完成情况。分数不能直接说明根因；业务场景需要补充后再验证。`;
                synthetic = false;
                creating = true;
              "
              >转为测试建议</BaseButton
            >
          </li>
        </ul>
      </SurfaceCard>
      <SurfaceCard>
        <nav aria-label="工作项分组" class="mb-4 flex flex-wrap gap-2">
          <BaseButton
            v-for="section in [
              { value: '', label: '全部工作项' },
              { value: 'decisions', label: '需要决定' },
              { value: 'active', label: '正在处理' },
              { value: 'results', label: '查看结果' },
              { value: 'regression', label: '回归集合' },
            ]"
            :key="section.value"
            :variant="group === section.value ? 'primary' : 'secondary'"
            @click="
              group = section.value;
              page = 1;
              load();
            "
            >{{ section.label }}</BaseButton
          >
        </nav>
        <form
          class="mb-4 flex flex-wrap items-end gap-3"
          @submit.prevent="
            page = 1;
            load();
          "
        >
          <label class="min-w-0 flex-1"
            >找回工作项<input
              v-model="query"
              class="pw-input mt-1 w-full"
              placeholder="输入问题名称"
              maxlength="120"
          /></label>
          <div class="w-44">
            <BaseSelect
              v-model="filterAgent"
              :options="[{ value: '', label: '全部Agent' }, ...agents]"
              aria-label="筛选Agent"
            />
          </div>
          <div class="w-44">
            <BaseSelect
              v-model="filterCreator"
              :options="[
                { value: '', label: '所有可见提交人' },
                { value: auth.user?.id || '', label: '我提交的' },
              ]"
              aria-label="筛选提交人"
            />
          </div>
          <div class="w-44">
            <BaseSelect
              v-model="status"
              :options="statuses"
              aria-label="工作项状态"
            />
          </div>
          <BaseButton type="submit" variant="secondary" :disabled="loading"
            >搜索</BaseButton
          >
        </form>
        <p v-if="loading && !entries.length" role="status" class="py-6">
          正在读取工作项…
        </p>
        <p v-else-if="!entries.length" class="py-6 text-gray-500">
          {{
            query || status
              ? "没有符合条件的工作项，请调整搜索条件。"
              : "还没有测试需求。新建一个问题，AI会帮你准备方案。"
          }}
        </p>
        <ul class="divide-y divide-gray-200 dark:divide-dark-700">
          <li v-for="entry in entries" :key="entry.id" class="py-4">
            <RouterLink
              :to="{
                name: 'workspace-evaluation-detail',
                params: { projectId: project, itemId: entry.id },
              }"
              class="block rounded-lg p-2 hover:bg-gray-50 focus-visible:outline focus-visible:outline-2 dark:hover:bg-dark-800"
            >
              <div class="flex flex-wrap justify-between gap-2">
                <strong>{{ entry.title }}</strong
                ><span class="text-sm">{{ statusLabel(entry.status) }}</span>
              </div>
              <p class="mt-2 text-sm text-gray-500">
                {{ entry.next_action || "打开查看资料状态" }}
              </p>
              <p class="mt-1 text-xs text-gray-500">
                {{
                  agents.find((a) => a.value === entry.agent_id)?.label ||
                  "项目Agent"
                }}
                · {{ new Date(entry.updated_at * 1000).toLocaleString() }} ·
                {{ entry.operations?.length || 0 }} 次验证
              </p>
            </RouterLink>
          </li>
        </ul>
        <PaginationBar
          v-model:page="page"
          v-model:page-size="pageSize"
          :total="total"
          :disabled="loading"
        />
      </SurfaceCard>
    </template>
  </main>
</template>

<script setup lang="ts">
import { computed, onScopeDispose, ref, shallowRef, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import BaseSelect from "@/components/base/BaseSelect.vue";
import SurfaceCard from "@/components/base/SurfaceCard.vue";
import PageHeader from "@/components/layout/PageHeader.vue";
import StateBanner from "@/components/platform/StateBanner.vue";
import StatusPill from "@/components/platform/StatusPill.vue";
import { useAuthorization } from "@/composables/useAuthorization";
import { useWorkspaceProjectContext } from "@/composables/useWorkspaceProjectContext";
import {
  createAgent,
  getAgent,
  getAgentParameterSchema,
  updateAgent,
} from "@/services/agents/agents.service";
import {
  contextFields,
  parseAgentContext,
  type ContextField,
} from "@/services/agents/context";
import type { Agent, AgentContext } from "@/services/agents/types";
import { listGraphsPage } from "@/services/graphs/graphs.service";
import {
  listRuntimeModels,
  listRuntimeTools,
} from "@/services/runtime/runtime.service";
import { listToolRestrictions } from "@/services/runtime-policies/runtime-policies.service";
import type {
  ManagementGraph,
  RuntimeModelItem,
  RuntimeToolItem,
  ToolRestrictionItem,
} from "@/types/management";

const EXECUTION_MODES = [
  { value: "flash", label: "Flash（极速响应）" },
  { value: "standard", label: "Standard（标准模式）" },
  { value: "pro", label: "Pro（深度推理）" },
  { value: "ultra", label: "Ultra（顶配全能）" },
] as const;

const route = useRoute();
const router = useRouter();
const { activeProjectId } = useWorkspaceProjectContext();
const { can } = useAuthorization();

const isNew = computed(
  () => !route.params.agentId || route.params.agentId === "new",
);
const agentId = computed(() =>
  typeof route.params.agentId === "string" && route.params.agentId !== "new"
    ? route.params.agentId
    : "",
);
const basePath = computed(
  () => `/workspace/projects/${encodeURIComponent(activeProjectId.value)}`,
);
const editable = computed(() =>
  can("project.assistant.write", activeProjectId.value),
);

const original = shallowRef<Agent | null>(null);
const graphId = ref("");
const name = ref("");
const description = ref("");
const status = ref<Agent["status"]>("active");
const context = ref<Record<string, unknown>>({});
const graphs = ref<ManagementGraph[]>([]);
const models = ref<RuntimeModelItem[]>([]);
const tools = ref<RuntimeToolItem[]>([]);
const restrictions = ref<ToolRestrictionItem[]>([]);
const fields = ref<ContextField[]>([]);
const loading = ref(true);
const saving = ref(false);
const schemaLoading = ref(false);
const schemaError = ref("");
const error = ref("");
const notice = ref("");
const copiedId = ref(false);
let epoch = 0;
let schemaEpoch = 0;

// 下拉框选项计算属性
const graphOptions = computed(() => {
  const list = graphs.value.map((g) => ({
    value: g.graph_id,
    label: `${g.display_name || g.graph_id} (${g.graph_id})`,
  }));
  if (
    original.value &&
    !graphs.value.some((g) => g.graph_id === graphId.value)
  ) {
    list.unshift({
      value: graphId.value,
      label: `${graphId.value}（当前不可用）`,
    });
  }
  return list;
});

const currentGraphItem = computed(() =>
  graphs.value.find((g) => g.graph_id === graphId.value),
);

// 当前 Graph 下声明的工具
const declaredToolsForGraph = computed(() => {
  const currentGraph = graphId.value?.trim();
  if (!currentGraph) return [];
  return tools.value.filter((t) => (t.graph_ids || []).includes(currentGraph));
});

// 当前 Graph 适用的禁用规则映射 (key: tool_name)
const restrictionsForCurrentGraph = computed(() => {
  const currentGraph = graphId.value?.trim();
  if (!currentGraph) return new Map<string, ToolRestrictionItem[]>();
  const map = new Map<string, ToolRestrictionItem[]>();
  for (const r of restrictions.value) {
    if (r.graph_id === currentGraph) {
      const list = map.get(r.tool_name) || [];
      list.push(r);
      map.set(r.tool_name, list);
    }
  }
  return map;
});

function getToolRestriction(toolKey: string): ToolRestrictionItem | null {
  const matches = restrictionsForCurrentGraph.value.get(toolKey);
  if (!matches || matches.length === 0) return null;
  // 优先匹配全员项目级禁用，其次取单人禁用
  return matches.find((r) => r.subject_type === "project") || matches[0];
}

// 统计当前声明工具的可用与禁用数量
const toolsStats = computed(() => {
  let restricted = 0;
  let available = 0;
  for (const t of declaredToolsForGraph.value) {
    if (getToolRestriction(t.tool_key)) {
      restricted++;
    } else {
      available++;
    }
  }
  return { available, restricted };
});

const statusOptions = [
  { value: "active", label: "启用 (Active)" },
  { value: "disabled", label: "停用 (Disabled)" },
];

const modelOptions = computed(() => [
  { value: "", label: "使用项目默认模型" },
  ...models.value.map((m) => ({
    value: m.id,
    label: `${m.display_name} (${m.model || m.provider})`,
  })),
]);

const currentModelItem = computed(() =>
  models.value.find((m) => m.id === context.value.model_id),
);

const executionModeOptions = [
  { value: "", label: "使用默认模式" },
  ...EXECUTION_MODES,
];

function fill(agent: Agent) {
  original.value = agent;
  graphId.value = agent.graph_id;
  name.value = agent.name;
  description.value = agent.description;
  status.value = agent.status;
  const cleanContext = { ...agent.context };
  delete (cleanContext as any).tools;
  delete (cleanContext as any).enable_tools;
  context.value = cleanContext;
}

async function load() {
  const requestEpoch = ++epoch;
  ++schemaEpoch;
  original.value = null;
  graphId.value = "";
  context.value = {};
  fields.value = [];
  name.value = "";
  description.value = "";
  status.value = "active";
  saving.value = false;
  models.value = [];
  tools.value = [];
  restrictions.value = [];
  graphs.value = [];
  error.value = "";
  notice.value = "";
  loading.value = true;
  const project = activeProjectId.value;
  try {
    if (!project) throw new Error("请先选择项目");
    const [graphList, modelList, toolList, agent, restrictionsData] = await Promise.all([
      listGraphsPage(project, { limit: 500 }),
      listRuntimeModels(project),
      listRuntimeTools(project),
      agentId.value ? getAgent(project, agentId.value) : Promise.resolve(null),
      listToolRestrictions(project).catch(() => ({ items: [] })),
    ]);
    if (requestEpoch !== epoch) return;
    graphs.value = graphList.items;
    models.value = modelList.models.filter((model: RuntimeModelItem) => model.enabled);
    tools.value = toolList.tools;
    restrictions.value = restrictionsData.items || [];
    if (agent) fill(agent);
    else graphId.value = graphs.value[0]?.graph_id ?? "";
  } catch (cause) {
    if (requestEpoch === epoch)
      error.value = cause instanceof Error ? cause.message : "加载失败";
  } finally {
    if (requestEpoch === epoch) loading.value = false;
  }
}

watch(
  [activeProjectId, agentId],
  () => {
    void load();
  },
  { immediate: true },
);

watch([activeProjectId, graphId], async ([project, graph]) => {
  const requestEpoch = ++schemaEpoch;
  fields.value = [];
  schemaError.value = "";
  schemaLoading.value = !!graph;
  if (!project || !graph) return;
  try {
    const schema = await getAgentParameterSchema(project, graph);
    if (requestEpoch === schemaEpoch) fields.value = contextFields(schema);
  } catch (cause) {
    if (requestEpoch === schemaEpoch)
      schemaError.value =
        cause instanceof Error ? cause.message : "参数加载失败";
  } finally {
    if (requestEpoch === schemaEpoch) schemaLoading.value = false;
  }
});

async function save() {
  if (
    !editable.value ||
    loading.value ||
    saving.value ||
    schemaLoading.value ||
    schemaError.value
  )
    return;
  const requestEpoch = epoch;
  const project = activeProjectId.value;
  saving.value = true;
  error.value = "";
  notice.value = "";
  try {
    if (!name.value.trim() || !graphId.value)
      throw new Error("请填写名称并选择 Graph");
    const nextContext: AgentContext = parseAgentContext(
      {
        ...context.value,
      },
      fields.value,
    );
    delete (nextContext as any).tools;
    delete (nextContext as any).enable_tools;
    if (isNew.value) {
      const created = await createAgent(project, {
        graph_id: graphId.value,
        name: name.value.trim(),
        description: description.value,
        context: Object.keys(nextContext).length ? nextContext : undefined,
      });
      if (requestEpoch === epoch) {
        void router.replace(`${basePath.value}/agents/${created.id}`);
        notice.value = "创建成功";
      }
    } else {
      const agent = original.value;
      if (!agent) return;
      const changes: Parameters<typeof updateAgent>[2] = {};
      if (name.value.trim() !== agent.name) changes.name = name.value.trim();
      if (description.value !== agent.description)
        changes.description = description.value;
      if (status.value !== agent.status) changes.status = status.value;
      if (JSON.stringify(nextContext) !== JSON.stringify(agent.context))
        changes.context = nextContext;
      if (!Object.keys(changes).length) {
        notice.value = "没有需要保存的改动";
        return;
      }
      const updated = await updateAgent(project, agent.id, changes);
      if (requestEpoch === epoch) {
        fill(updated);
        notice.value = "已保存修改";
      }
    }
  } catch (cause) {
    if (requestEpoch === epoch)
      error.value = cause instanceof Error ? cause.message : "保存失败";
  } finally {
    if (requestEpoch === epoch) saving.value = false;
  }
}

function formatDate(val: string | null | undefined) {
  if (!val) return "—";
  return new Date(val).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function copyAgentId() {
  if (!original.value?.id) return;
  void navigator.clipboard.writeText(original.value.id);
  copiedId.value = true;
  setTimeout(() => {
    copiedId.value = false;
  }, 2000);
}

function applyTokenPreset(tokens: number | undefined) {
  context.value.max_tokens = tokens;
}

onScopeDispose(() => {
  ++epoch;
  ++schemaEpoch;
});
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Agents"
      :title="isNew ? '新建 Agent' : (original?.name || '智能体配置')"
      :description="isNew ? '选择底层 Graph 与执行策略，配置专属运行参数并创建智能体。' : '查看并调整该智能体的模型路由、生成参数与工具访问控制。'"
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          @click="router.push(`${basePath}/agents`)"
        >
          返回列表
        </BaseButton>
        <BaseButton
          v-if="original"
          variant="secondary"
          :disabled="original.status !== 'active'"
          @click="
            router.push({
              path: `${basePath}/chat`,
              query: { agentId: original.id },
            })
          "
        >
          <BaseIcon
            name="chat"
            size="sm"
            class="mr-1 text-primary-500"
          />
          打开聊天
        </BaseButton>
      </template>
    </PageHeader>

    <StateBanner
      v-if="error"
      variant="danger"
      title="操作未完成"
      :description="error"
    />
    <StateBanner
      v-if="notice"
      variant="success"
      title="操作成功"
      :description="notice"
    />

    <p
      v-if="loading"
      role="status"
      class="py-12 text-center text-sm text-gray-500"
    >
      正在读取智能体与配置元数据…
    </p>

    <!-- 主表单与预览双栏布局 -->
    <div
      v-else-if="isNew || original"
      class="grid gap-6 xl:grid-cols-[minmax(0,1.28fr)_minmax(320px,0.72fr)]"
    >
      <!-- 左栏：主配置区 -->
      <form
        class="space-y-6"
        @submit.prevent="save"
      >
        <fieldset
          :disabled="!editable || saving"
          class="space-y-6"
        >
          <!-- 卡片 1：基础信息 -->
          <SurfaceCard class="space-y-5">
            <div class="flex items-center justify-between border-b border-gray-100 pb-3.5 dark:border-dark-800">
              <div class="flex items-center gap-2.5">
                <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-50 text-primary-600 dark:bg-primary-950/40 dark:text-primary-300">
                  <BaseIcon
                    name="assistant"
                    size="sm"
                  />
                </div>
                <div>
                  <h2 class="text-sm font-semibold text-gray-900 dark:text-white">
                    基础信息
                  </h2>
                  <p class="text-xs text-gray-500 dark:text-dark-300">
                    定义智能体的对外标识与调度的底层 Graph
                  </p>
                </div>
              </div>
              <StatusPill
                v-if="original"
                :tone="status === 'active' ? 'success' : 'warning'"
              >
                {{ status === 'active' ? '启用中' : '已停用' }}
              </StatusPill>
            </div>

            <div class="grid gap-4 md:grid-cols-2">
              <div>
                <label class="pw-input-label">
                  智能体名称 <span class="text-red-500">*</span>
                </label>
                <input
                  v-model="name"
                  required
                  maxlength="200"
                  class="pw-input"
                  placeholder="例如：技术文档编写助手"
                >
              </div>

              <div>
                <label class="pw-input-label">
                  底层 Graph <span class="text-red-500">*</span>
                </label>
                <BaseSelect
                  :model-value="graphId"
                  :options="graphOptions"
                  :disabled="!!original"
                  placeholder="请选择绑定的 Graph"
                  @update:model-value="val => { graphId = String(val) }"
                />
              </div>
            </div>

            <div>
              <label class="pw-input-label">
                功能描述
              </label>
              <textarea
                v-model="description"
                maxlength="2000"
                class="pw-input"
                rows="3"
                placeholder="简明扼要地描述该智能体的主要能力与使用场景…"
              />
              <div class="mt-1 text-right text-xs text-gray-400">
                {{ description.length }} / 2000
              </div>
            </div>

            <div
              v-if="original"
              class="pt-1"
            >
              <label class="pw-input-label">运行状态</label>
              <div class="max-w-xs">
                <BaseSelect
                  :model-value="status"
                  :options="statusOptions"
                  @update:model-value="val => { status = (val as Agent['status']) || 'active' }"
                />
              </div>
            </div>
          </SurfaceCard>

          <!-- 卡片 2：模型与运行参数 -->
          <SurfaceCard class="space-y-5">
            <div class="flex items-center justify-between border-b border-gray-100 pb-3.5 dark:border-dark-800">
              <div class="flex items-center gap-2.5">
                <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-sky-50 text-sky-600 dark:bg-sky-950/40 dark:text-sky-300">
                  <BaseIcon
                    name="sparkle"
                    size="sm"
                  />
                </div>
                <div>
                  <h2 class="text-sm font-semibold text-gray-900 dark:text-white">
                    模型与推理参数
                  </h2>
                  <p class="text-xs text-gray-500 dark:text-dark-300">
                    微调上下文策略、采样发散度与最大 Token 预算
                  </p>
                </div>
              </div>
            </div>

            <p
              v-if="schemaLoading"
              class="py-4 text-center text-xs text-gray-500"
            >
              正在拉取该 Graph 的参数定义…
            </p>
            <p
              v-if="schemaError"
              role="alert"
              class="text-xs text-red-600"
            >
              {{ schemaError }}
            </p>

            <div
              v-if="!schemaLoading && !schemaError"
              class="space-y-5"
            >
              <!-- 第一行：模型选择 与 执行模式 下拉 -->
              <div class="grid gap-4 md:grid-cols-2">
                <div>
                  <label class="pw-input-label">指定模型</label>
                  <BaseSelect
                    :model-value="(context.model_id as string) || ''"
                    :options="modelOptions"
                    placeholder="使用项目默认模型"
                    @update:model-value="val => { context.model_id = val ? String(val) : undefined }"
                  />
                  <p class="mt-1.5 text-xs text-gray-400 dark:text-dark-400">
                    可覆盖项目的统一默认模型
                  </p>
                </div>

                <div>
                  <label class="pw-input-label">执行模式 (Execution Mode)</label>
                  <BaseSelect
                    :model-value="(context.execution_mode as string) || ''"
                    :options="executionModeOptions"
                    placeholder="使用默认模式"
                    @update:model-value="val => { context.execution_mode = val ? String(val) : undefined }"
                  />
                  <p class="mt-1.5 text-xs text-gray-400 dark:text-dark-400">
                    控制运行时推理深度与资源消耗策略
                  </p>
                </div>
              </div>

              <!-- 参数调节滑块区 -->
              <div class="grid gap-5 border-t border-gray-100 pt-4 dark:border-dark-800 md:grid-cols-2">
                <!-- Temperature -->
                <div class="space-y-2 rounded-xl bg-gray-50/70 p-3.5 dark:bg-dark-900/60">
                  <div class="flex items-center justify-between">
                    <span class="text-xs font-semibold text-gray-700 dark:text-gray-300">Temperature (采样温度)</span>
                    <span class="rounded-md bg-white px-2 py-0.5 font-mono text-xs font-bold text-primary-600 shadow-sm dark:bg-dark-800 dark:text-primary-300">
                      {{ context.temperature ?? '默认 (0.7)' }}
                    </span>
                  </div>
                  <div class="flex items-center gap-3">
                    <input
                      type="range"
                      min="0"
                      max="2"
                      step="0.05"
                      :value="context.temperature ?? 0.7"
                      class="h-1.5 flex-1 cursor-pointer accent-primary-600"
                      @input="context.temperature = Number(($event.target as HTMLInputElement).value)"
                    >
                    <input
                      v-model.number="context.temperature"
                      type="number"
                      min="0"
                      max="2"
                      step="0.05"
                      class="pw-input h-8 w-20 text-center font-mono text-xs"
                      placeholder="默认"
                    >
                  </div>
                  <div class="flex justify-between text-[10px] text-gray-400">
                    <span>0.0 严谨</span>
                    <span>0.7 平衡</span>
                    <span>1.5+ 创意</span>
                  </div>
                </div>

                <!-- Top P -->
                <div class="space-y-2 rounded-xl bg-gray-50/70 p-3.5 dark:bg-dark-900/60">
                  <div class="flex items-center justify-between">
                    <span class="text-xs font-semibold text-gray-700 dark:text-gray-300">Top P (核采样率)</span>
                    <span class="rounded-md bg-white px-2 py-0.5 font-mono text-xs font-bold text-sky-600 shadow-sm dark:bg-dark-800 dark:text-sky-300">
                      {{ context.top_p ?? '默认 (1.0)' }}
                    </span>
                  </div>
                  <div class="flex items-center gap-3">
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.05"
                      :value="context.top_p ?? 1"
                      class="h-1.5 flex-1 cursor-pointer accent-sky-600"
                      @input="context.top_p = Number(($event.target as HTMLInputElement).value)"
                    >
                    <input
                      v-model.number="context.top_p"
                      type="number"
                      min="0"
                      max="1"
                      step="0.05"
                      class="pw-input h-8 w-20 text-center font-mono text-xs"
                      placeholder="默认"
                    >
                  </div>
                  <div class="flex justify-between text-[10px] text-gray-400">
                    <span>0.1 聚焦</span>
                    <span>0.5 适中</span>
                    <span>1.0 全量</span>
                  </div>
                </div>
              </div>

              <!-- Max Tokens -->
              <div class="rounded-xl border border-gray-100 p-4 dark:border-dark-800">
                <div class="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <label class="text-xs font-semibold text-gray-700 dark:text-gray-300">Max Tokens (最大单次输出)</label>
                    <p class="mt-0.5 text-xs text-gray-400">限制回复的最大 Token 长度，超出将被截断</p>
                  </div>
                  <div class="flex items-center gap-1.5">
                    <button
                      v-for="preset in [2048, 4096, 8192, 16384]"
                      :key="preset"
                      type="button"
                      class="rounded-lg border border-gray-200 px-2 py-1 text-[11px] font-medium text-gray-600 transition-colors hover:border-primary-500 hover:text-primary-600 dark:border-dark-700 dark:text-dark-200"
                      :class="context.max_tokens === preset ? 'border-primary-500 bg-primary-50 text-primary-700 dark:bg-primary-950/40 dark:text-primary-300' : ''"
                      @click="applyTokenPreset(preset)"
                    >
                      {{ preset >= 1024 ? `${preset / 1024}k` : preset }}
                    </button>
                    <button
                      v-if="context.max_tokens"
                      type="button"
                      class="px-1.5 text-[11px] text-gray-400 hover:text-red-500"
                      title="清除预设"
                      @click="applyTokenPreset(undefined)"
                    >
                      清除
                    </button>
                  </div>
                </div>
                <div class="mt-2.5 max-w-xs">
                  <input
                    v-model.number="context.max_tokens"
                    type="number"
                    min="1"
                    step="1"
                    class="pw-input font-mono text-xs"
                    placeholder="留空则遵循 Graph 内部默认值"
                  >
                </div>
              </div>
            </div>
          </SurfaceCard>

          <!-- 卡片 3：工具调用范围 -->
          <SurfaceCard class="space-y-4">
            <div class="flex items-center justify-between border-b border-gray-100 pb-3.5 dark:border-dark-800">
              <div class="flex items-center gap-2.5">
                <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-300">
                  <BaseIcon
                    name="settings-2"
                    size="sm"
                  />
                </div>
                <div>
                  <h2 class="text-sm font-semibold text-gray-900 dark:text-white">
                    已声明工具能力
                  </h2>
                  <p class="text-xs text-gray-500 dark:text-dark-300">
                    该智能体归属 Graph 声明的工具列表（由运行时统一治理并受项目禁用规则管控）
                  </p>
                </div>
              </div>
              <span class="text-xs text-gray-400">
                共 {{ declaredToolsForGraph.length }} 项工具
                <template v-if="declaredToolsForGraph.length">
                  （<span class="text-emerald-600 dark:text-emerald-400">{{ toolsStats.available }} 可用</span>
                  <template v-if="toolsStats.restricted > 0">
                    · <span class="text-rose-600 dark:text-rose-400">{{ toolsStats.restricted }} 已禁用</span>
                  </template>）
                </template>
              </span>
            </div>

            <!-- 工具卡片网格（只读展示） -->
            <div class="space-y-3 pt-2">
              <div
                v-if="declaredToolsForGraph.length"
                class="grid gap-2.5 sm:grid-cols-2"
              >
                <div
                  v-for="tool in declaredToolsForGraph"
                  :key="tool.tool_key"
                  class="relative flex items-start gap-3 rounded-xl border p-3 transition-all"
                  :class="
                    getToolRestriction(tool.tool_key)
                      ? 'border-rose-200/80 bg-rose-50/30 dark:border-rose-900/40 dark:bg-rose-950/20'
                      : 'border-gray-150 bg-gray-50/40 dark:border-dark-800 dark:bg-dark-900/40'
                  "
                >
                  <!-- 可用状态：对勾（绿色）；禁用状态：叉号（红色） -->
                  <div
                    class="mt-0.5 flex h-4.5 w-4.5 shrink-0 items-center justify-center rounded-full"
                    :class="
                      getToolRestriction(tool.tool_key)
                        ? 'bg-rose-100 text-rose-600 dark:bg-rose-950/60 dark:text-rose-400'
                        : 'bg-emerald-100 text-emerald-600 dark:bg-emerald-950/60 dark:text-emerald-400'
                    "
                  >
                    <BaseIcon
                      :name="getToolRestriction(tool.tool_key) ? 'x' : 'check'"
                      size="xs"
                    />
                  </div>

                  <div class="min-w-0 flex-1">
                    <div class="flex items-center justify-between gap-1">
                      <span
                        class="truncate text-xs font-semibold"
                        :class="
                          getToolRestriction(tool.tool_key)
                            ? 'text-gray-700 line-through dark:text-dark-300'
                            : 'text-gray-900 dark:text-white'
                        "
                      >
                        {{ tool.name || tool.tool_key }}
                      </span>
                      <div class="flex items-center gap-1 shrink-0">
                        <span
                          v-if="getToolRestriction(tool.tool_key)"
                          class="rounded-full bg-rose-100 px-1.5 py-0.2 text-[10px] font-medium text-rose-700 dark:bg-rose-950/60 dark:text-rose-300"
                        >
                          {{ getToolRestriction(tool.tool_key)?.subject_type === 'project' ? '项目禁用' : '成员禁用' }}
                        </span>
                        <span
                          v-if="tool.source"
                          class="rounded bg-gray-100 px-1 py-0.2 text-[10px] text-gray-500 dark:bg-dark-800"
                        >
                          {{ tool.source }}
                        </span>
                      </div>
                    </div>
                    <p class="mt-0.5 font-mono text-[11px] text-gray-400">
                      {{ tool.tool_key }}
                    </p>
                    <p
                      v-if="tool.description"
                      class="mt-1 line-clamp-2 text-[11px] text-gray-500 dark:text-dark-300"
                    >
                      {{ tool.description }}
                    </p>
                    <!-- 禁用原因清晰展示 -->
                    <div
                      v-if="getToolRestriction(tool.tool_key)"
                      class="mt-2 rounded-lg bg-rose-50/80 px-2 py-1 text-[11px] text-rose-700 dark:bg-rose-950/40 dark:text-rose-300"
                    >
                      <span class="font-medium">原因：</span>{{ getToolRestriction(tool.tool_key)?.reason }}
                    </div>
                  </div>
                </div>
              </div>

              <p
                v-else
                class="py-6 text-center text-xs text-gray-400"
              >
                {{ graphId ? '所选 Graph 当前未声明任何工具' : '请先选择 Graph 以查看声明工具' }}
              </p>
            </div>
          </SurfaceCard>

          <!-- 底部操作按钮 -->
          <div class="flex items-center justify-end gap-3 pt-2">
            <BaseButton
              variant="secondary"
              type="button"
              :disabled="saving"
              @click="router.push(`${basePath}/agents`)"
            >
              取消
            </BaseButton>
            <BaseButton
              type="submit"
              :disabled="schemaLoading || !!schemaError || !graphId || saving"
            >
              <BaseIcon
                v-if="!saving"
                :name="isNew ? 'plus' : 'check'"
                size="sm"
                class="mr-1"
              />
              {{ saving ? "正在提交…" : (isNew ? "立即创建 Agent" : "保存所有配置") }}
            </BaseButton>
          </div>
        </fieldset>
      </form>

      <!-- 右栏：实时预览看板与元数据信息 -->
      <aside class="space-y-5">
        <!-- 实时卡片预览 -->
        <SurfaceCard class="space-y-4">
          <div class="flex items-center justify-between border-b border-gray-100 pb-3 dark:border-dark-800">
            <span class="text-xs font-semibold uppercase tracking-wider text-gray-400">
              配置看板 · 实时预览
            </span>
            <span class="flex h-2 w-2 rounded-full bg-emerald-500 ring-4 ring-emerald-100 dark:ring-emerald-950/50" />
          </div>

          <!-- 模拟渲染的 Agent Profile -->
          <div class="rounded-2xl border border-gray-100 bg-gradient-to-b from-gray-50/80 to-white p-4.5 dark:border-dark-800 dark:from-dark-900/60 dark:to-dark-950">
            <div class="flex items-start gap-3.5">
              <div class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-primary-500 to-primary-700 font-bold text-white shadow-md shadow-primary-500/20">
                {{ (name.trim().charAt(0) || 'A').toUpperCase() }}
              </div>
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2">
                  <h3 class="truncate text-base font-bold text-gray-900 dark:text-white">
                    {{ name.trim() || '未命名智能体' }}
                  </h3>
                  <StatusPill :tone="status === 'active' ? 'success' : 'warning'">
                    {{ status === 'active' ? '启用' : '停用' }}
                  </StatusPill>
                </div>
                <p class="mt-1 line-clamp-2 text-xs text-gray-500 dark:text-dark-300">
                  {{ description.trim() || '尚未填写描述信息…' }}
                </p>
              </div>
            </div>

            <!-- 参数指标速览 -->
            <div class="mt-4 grid grid-cols-2 gap-2 border-t border-gray-150/60 pt-3 text-xs dark:border-dark-800">
              <div class="rounded-lg bg-white p-2 dark:bg-dark-900">
                <span class="text-[10px] text-gray-400">执行模型</span>
                <p class="truncate font-semibold text-gray-800 dark:text-gray-200">
                  {{ currentModelItem?.display_name || '项目默认模型' }}
                </p>
              </div>
              <div class="rounded-lg bg-white p-2 dark:bg-dark-900">
                <span class="text-[10px] text-gray-400">推理模式</span>
                <p class="font-semibold capitalize text-gray-800 dark:text-gray-200">
                  {{ context.execution_mode || 'standard (默认)' }}
                </p>
              </div>
              <div class="rounded-lg bg-white p-2 dark:bg-dark-900">
                <span class="text-[10px] text-gray-400">Temperature</span>
                <p class="font-mono font-semibold text-gray-800 dark:text-gray-200">
                  {{ context.temperature ?? '0.7 (默认)' }}
                </p>
              </div>
              <div class="rounded-lg bg-white p-2 dark:bg-dark-900">
                <span class="text-[10px] text-gray-400">已声明工具</span>
                <p class="font-semibold text-gray-800 dark:text-gray-200">
                  {{ declaredToolsForGraph.length ? `${declaredToolsForGraph.length} 项` : '无' }}
                </p>
              </div>
            </div>
          </div>

          <!-- 当前 Graph 详情 -->
          <div
            v-if="currentGraphItem"
            class="space-y-2 rounded-xl bg-gray-50/60 p-3 text-xs dark:bg-dark-900/40"
          >
            <div class="flex items-center gap-1.5 font-medium text-gray-700 dark:text-dark-200">
              <BaseIcon
                name="graph"
                size="sm"
                class="text-primary-500"
              />
              <span>绑定拓扑：{{ currentGraphItem.display_name || currentGraphItem.graph_id }}</span>
            </div>
            <p
              v-if="currentGraphItem.description"
              class="text-gray-500 dark:text-dark-300"
            >
              {{ currentGraphItem.description }}
            </p>
            <div class="flex items-center gap-2 text-[11px] text-gray-400">
              <span>架构源：{{ currentGraphItem.source_type }}</span>
              <span>·</span>
              <span>同步状态：{{ currentGraphItem.sync_status }}</span>
            </div>
          </div>
        </SurfaceCard>

        <!-- 编辑态下的系统元数据 -->
        <SurfaceCard
          v-if="original"
          class="space-y-3.5"
        >
          <div class="flex items-center gap-2 text-xs font-semibold text-gray-900 dark:text-white">
            <BaseIcon
              name="info"
              size="sm"
              class="text-primary-500"
            />
            元数据与审计记录
          </div>

          <dl class="space-y-2.5 text-xs">
            <div class="flex items-center justify-between gap-2 border-b border-gray-100 pb-2 dark:border-dark-800">
              <dt class="text-gray-500 dark:text-dark-400">Agent ID</dt>
              <dd class="flex items-center gap-1 font-mono text-gray-800 dark:text-dark-200">
                <span class="max-w-[140px] truncate" :title="original.id">{{ original.id }}</span>
                <button
                  type="button"
                  class="text-gray-400 hover:text-primary-600"
                  :title="copiedId ? '已复制' : '复制完整 ID'"
                  @click="copyAgentId"
                >
                  <BaseIcon
                    :name="copiedId ? 'check' : 'copy'"
                    size="xs"
                    :class="copiedId ? 'text-emerald-500' : ''"
                  />
                </button>
              </dd>
            </div>

            <div class="flex items-center justify-between gap-2 border-b border-gray-100 pb-2 dark:border-dark-800">
              <dt class="text-gray-500 dark:text-dark-400">创建人</dt>
              <dd class="text-gray-800 dark:text-dark-200">{{ original.created_by || '系统默认' }}</dd>
            </div>

            <div class="flex items-center justify-between gap-2 border-b border-gray-100 pb-2 dark:border-dark-800">
              <dt class="text-gray-500 dark:text-dark-400">创建时间</dt>
              <dd class="text-gray-800 dark:text-dark-200">{{ formatDate(original.created_at) }}</dd>
            </div>

            <div class="flex items-center justify-between gap-2">
              <dt class="text-gray-500 dark:text-dark-400">最后更新</dt>
              <dd class="text-gray-800 dark:text-dark-200">{{ formatDate(original.updated_at) }}</dd>
            </div>
          </dl>
        </SurfaceCard>
      </aside>
    </div>
  </section>
</template>

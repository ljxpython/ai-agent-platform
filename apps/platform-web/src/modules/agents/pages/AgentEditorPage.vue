<script setup lang="ts">
import { computed, onScopeDispose, ref, shallowRef, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import BaseButton from "@/components/base/BaseButton.vue";
import SurfaceCard from "@/components/base/SurfaceCard.vue";
import PageHeader from "@/components/layout/PageHeader.vue";
import StateBanner from "@/components/platform/StateBanner.vue";
import { useAuthorization } from "@/composables/useAuthorization";
import { useWorkspaceProjectContext } from "@/composables/useWorkspaceProjectContext";
import {
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
import type {
  ManagementGraph,
  RuntimeModelItem,
  RuntimeToolItem,
} from "@/types/management";

const route = useRoute();
const router = useRouter();
const { activeProjectId } = useWorkspaceProjectContext();
const { can } = useAuthorization();
const agentId = computed(() =>
  typeof route.params.agentId === "string" ? route.params.agentId : "",
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
const toolMode = ref<"inherit" | "select">("inherit");
const selectedTools = ref<string[]>([]);
const graphs = ref<ManagementGraph[]>([]);
const models = ref<RuntimeModelItem[]>([]);
const tools = ref<RuntimeToolItem[]>([]);
const fields = ref<ContextField[]>([]);
const loading = ref(true);
const saving = ref(false);
const schemaLoading = ref(false);
const schemaError = ref("");
const error = ref("");
const notice = ref("");
let epoch = 0;
let schemaEpoch = 0;

function fill(agent: Agent) {
  original.value = agent;
  graphId.value = agent.graph_id;
  name.value = agent.name;
  description.value = agent.description;
  status.value = agent.status;
  context.value = { ...agent.context };
  toolMode.value = agent.context.tools === undefined ? "inherit" : "select";
  selectedTools.value = [...(agent.context.tools ?? [])];
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
  selectedTools.value = [];
  toolMode.value = "inherit";
  status.value = "active";
  saving.value = false;
  models.value = [];
  tools.value = [];
  graphs.value = [];
  error.value = "";
  notice.value = "";
  loading.value = true;
  const project = activeProjectId.value;
  try {
    if (!project) throw new Error("请先选择项目");
    const [graphList, modelList, toolList, agent] = await Promise.all([
      listGraphsPage(project, { limit: 500 }),
      listRuntimeModels(project),
      listRuntimeTools(project),
      agentId.value ? getAgent(project, agentId.value) : Promise.resolve(null),
    ]);
    if (requestEpoch !== epoch) return;
    graphs.value = graphList.items;
    models.value = modelList.models.filter((model) => model.enabled);
    tools.value = toolList.tools;
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
        tools: toolMode.value === "select" ? selectedTools.value : undefined,
      },
      fields.value,
    );
    const agent = original.value;
    if (agent) {
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
        notice.value = "已保存";
      }
    }
  } catch (cause) {
    if (requestEpoch === epoch)
      error.value = cause instanceof Error ? cause.message : "保存失败";
  } finally {
    if (requestEpoch === epoch) saving.value = false;
  }
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
      :title="original?.name || '智能体配置'"
      description="查看已授权智能体，并设置当前项目的默认运行参数。"
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
      title="保存结果"
      :description="notice"
    />
    <p
      v-if="loading"
      role="status"
    >
      加载中…
    </p>
    <SurfaceCard
      v-else-if="original"
      class="max-w-4xl"
    >
      <form
        class="space-y-5"
        @submit.prevent="save"
      >
        <fieldset
          :disabled="!editable || saving"
          class="space-y-5"
        >
          <div class="grid gap-4 md:grid-cols-2">
            <label>名称<input
              v-model="name"
              required
              maxlength="200"
              class="pw-input mt-1"
            ></label>
            <label>Graph<select
              v-model="graphId"
              aria-label="Graph"
              :disabled="!!original"
              required
              class="pw-input mt-1"
            >
              <option
                v-if="
                  original &&
                    !graphs.some((graph) => graph.graph_id === graphId)
                "
                :value="graphId"
              >
                {{ graphId }}（当前不可用）
              </option>
              <option
                v-for="graph in graphs"
                :key="graph.graph_id"
                :value="graph.graph_id"
              >
                {{ graph.display_name || graph.graph_id }}
              </option>
            </select></label>
          </div>
          <label class="block">描述<textarea
            v-model="description"
            maxlength="2000"
            class="pw-input mt-1"
            rows="3"
          />
          </label>
          <label
            v-if="original"
            class="block"
          >状态<select
            v-model="status"
            class="pw-input mt-1"
          >
            <option value="active">启用</option>
            <option value="disabled">停用</option>
          </select></label>
          <h2 class="font-medium">
            默认运行参数
          </h2>
          <p
            v-if="schemaLoading"
            class="text-sm text-gray-500"
          >
            读取参数定义…
          </p>
          <p
            v-if="schemaError"
            role="alert"
            class="text-red-600"
          >
            {{ schemaError }}
          </p>
          <div class="grid gap-4 md:grid-cols-2">
            <label
              v-for="field in fields"
              :key="field.key"
            >{{ field.label }}
              <select
                v-if="field.key === 'model_id'"
                v-model="context.model_id"
                :aria-label="field.label"
                class="pw-input mt-1"
              >
                <option :value="undefined">使用项目默认模型</option>
                <option
                  v-for="model in models"
                  :key="model.id"
                  :value="model.id"
                >
                  {{ model.display_name }}
                </option>
              </select>
              <input
                v-else
                v-model="context[field.key]"
                type="number"
                :min="field.minimum"
                :max="field.maximum"
                :step="field.type === 'integer' ? 1 : 'any'"
                class="pw-input mt-1"
                placeholder="使用默认值"
              >
            </label>
          </div>
          <label class="block">工具范围<select
            v-model="toolMode"
            class="pw-input mt-1"
          >
            <option value="inherit">使用已授权的默认工具</option>
            <option value="select">明确选择工具（可以不选）</option>
          </select></label>
          <div
            v-if="toolMode === 'select'"
            class="grid gap-2 md:grid-cols-2"
          >
            <label
              v-for="tool in tools"
              :key="tool.tool_key"
              class="flex items-center gap-2"
            ><input
              v-model="selectedTools"
              type="checkbox"
              :value="tool.tool_key"
            >{{ tool.name || tool.tool_key }}</label>
            <p
              v-if="!tools.length"
              class="text-sm text-gray-500"
            >
              当前没有可选工具
            </p>
          </div>
          <BaseButton
            type="submit"
            :disabled="schemaLoading || !!schemaError || !graphId"
          >
            {{ saving ? "保存中…" : "保存" }}
          </BaseButton>
        </fieldset>
      </form>
    </SurfaceCard>
  </section>
</template>

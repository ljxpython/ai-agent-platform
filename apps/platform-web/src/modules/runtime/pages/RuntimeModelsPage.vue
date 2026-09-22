<script setup lang="ts">
import { computed, onScopeDispose, ref, watch } from "vue";
import { useRoute } from "vue-router";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseDialog from "@/components/base/BaseDialog.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import PageHeader from "@/components/layout/PageHeader.vue";
import PaginationBar from "@/components/platform/PaginationBar.vue";
import SearchInput from "@/components/platform/SearchInput.vue";
import StateBanner from "@/components/platform/StateBanner.vue";
import StatusPill from "@/components/platform/StatusPill.vue";
import { useAuthorization } from "@/composables/useAuthorization";
import { useWorkspaceProjectContext } from "@/composables/useWorkspaceProjectContext";
import { useAuthStore } from "@/stores/auth";
import type { ActionMenuItem } from "@/components/platform/data-table";
import {
  createRuntimeModel,
  deleteRuntimeModel,
  listRuntimeModels,
  listPlatformModels,
  listRuntimeTools,
  refreshRuntimeTools,
  updateRuntimeModel,
  type RuntimeModelInput,
} from "@/services/runtime/runtime.service";
import {
  listRuntimeModelPolicies,
  updateRuntimeModelPolicy,
} from "@/services/runtime-policies/runtime-policies.service";
import type {
  RuntimeModelItem,
  RuntimeModelPolicyValue,
  RuntimeToolItem,
} from "@/types/management";
import RuntimeModelEditor, {
  type ModelEditorMode,
  type ModelEditorSubmitPayload,
} from "../components/RuntimeModelEditor.vue";
import RuntimeModelDetailDialog from "../components/RuntimeModelDetailDialog.vue";
import ProviderStationCard, {
  type ProviderStation,
} from "../components/ProviderStationCard.vue";
import ToolRestrictionsPanel from "../components/ToolRestrictionsPanel.vue";

const { activeProjectId } = useWorkspaceProjectContext();
const auth = useAuthStore();
const { can } = useAuthorization();
const route = useRoute();
const platformMode = computed(() => route.name === "workspace-platform-models");
const canManagePlatform = computed(() => platformMode.value && can("platform.model.write"));
const canManagePrivate = computed(() => !platformMode.value && can("project.runtime.write"));
const canManage = computed(() =>
  platformMode.value ? canManagePlatform.value : canManagePrivate.value,
);
const canManagePolicy = computed(() => !platformMode.value && can("project.runtime.write"));
const canRefresh = computed(() => !platformMode.value && can("platform.catalog.refresh"));
const items = ref<RuntimeModelItem[]>([]);
const policies = ref<Record<string, RuntimeModelPolicyValue>>({});
const tools = ref<RuntimeToolItem[]>([]);
const toolRestrictionsOpen = ref(false);
const tab = ref<"models" | "tools">("models");
const query = ref("");
const page = ref(1);
const pageSize = ref(24);
const pageSizeOptions = computed(() =>
  tab.value === "tools" ? [12, 24, 48, 96] : [10, 20, 50, 100],
);
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const notice = ref("");
const editorOpen = ref(false);
const editingModel = ref<RuntimeModelItem | null>(null);
const targetStation = ref<ProviderStation | null>(null);
const detailModel = ref<RuntimeModelItem | null>(null);
let epoch = 0;
const defaultIds = computed(() =>
  Object.keys(policies.value).filter(
    (id) => policies.value[id].is_default_for_project,
  ),
);
const authorizedIds = computed(() =>
  Object.keys(policies.value).filter((id) => policies.value[id].is_enabled),
);
const filteredModels = computed(() =>
  items.value.filter((item) =>
    [item.model, item.display_name, item.provider, item.base_url].some(
      (value) => value.toLowerCase().includes(query.value.trim().toLowerCase()),
    ),
  ),
);
const filteredTools = computed(() =>
  tools.value.filter((item) =>
    [item.name, item.tool_key, item.description].some((value) =>
      value.toLowerCase().includes(query.value.trim().toLowerCase()),
    ),
  ),
);
const total = computed(() =>
  tab.value === "models"
    ? filteredModels.value.length
    : filteredTools.value.length,
);
const visibleTools = computed(() =>
  filteredTools.value.slice(
    (page.value - 1) * pageSize.value,
    page.value * pageSize.value,
  ),
);
const privateModels = computed(() =>
  filteredModels.value.filter((item) => item.scope_type === "project"),
);
const platformModels = computed(() =>
  filteredModels.value.filter((item) => item.scope_type !== "project"),
);

function groupModelsToStations(
  modelList: RuntimeModelItem[],
  defaultScope?: "platform" | "project",
): ProviderStation[] {
  const groups = new Map<string, RuntimeModelItem[]>();
  for (const model of modelList) {
    const key = JSON.stringify([
      model.provider,
      model.base_url,
      model.protocol,
      model.scope_type || defaultScope || "platform",
    ]);
    const group = groups.get(key) ?? [];
    group.push(model);
    groups.set(key, group);
  }
  return [...groups].map(([id, models]) => ({
    id,
    name: models[0].provider,
    provider: models[0].provider,
    baseUrl: models[0].base_url,
    protocol: models[0].protocol,
    credentialConfigured: models.every((model) => model.credential_configured),
    modelCount: models.length,
    enabledCount: models.filter((model) => model.enabled).length,
    models,
    isDefaultStation: models.some((model) =>
      defaultIds.value.includes(model.id),
    ),
    scopeType: models[0].scope_type || defaultScope || "platform",
  }));
}

const privateStations = computed(() =>
  groupModelsToStations(privateModels.value, "project"),
);
const platformStations = computed(() =>
  groupModelsToStations(platformModels.value, "platform"),
);
const stations = computed<ProviderStation[]>(() => {
  if (platformMode.value) {
    return groupModelsToStations(
      filteredModels.value.slice(
        (page.value - 1) * pageSize.value,
        page.value * pageSize.value,
      ),
      "platform",
    );
  }
  return groupModelsToStations(filteredModels.value);
});

async function load() {
  const requestEpoch = ++epoch;
  const project = activeProjectId.value;
  loading.value = true;
  error.value = "";
  items.value = [];
  policies.value = {};
  tools.value = [];
  try {
    if (platformMode.value) {
      const models = await listPlatformModels();
      if (requestEpoch === epoch) items.value = models.models;
      return;
    }
    if (!project) throw new Error("请先选择项目");
    const [models, modelPolicies, toolData] = await Promise.all([
      listRuntimeModels(project),
      listRuntimeModelPolicies(project),
      listRuntimeTools(project),
    ]);
    if (requestEpoch !== epoch) return;
    items.value = models.models;
    policies.value = Object.fromEntries(
      modelPolicies.items.map((item) => [item.catalog_id, item.policy]),
    );
    tools.value = toolData.tools;
  } catch (cause) {
    if (requestEpoch === epoch)
      error.value = cause instanceof Error ? cause.message : "目录读取失败";
  } finally {
    if (requestEpoch === epoch) loading.value = false;
  }
}
watch(
  [activeProjectId, platformMode, () => auth.sessionEpoch],
  () => {
    editorOpen.value = false;
    editingModel.value = null;
    targetStation.value = null;
    detailModel.value = null;
    toolRestrictionsOpen.value = false;
    tab.value = "models";
    saving.value = false;
    notice.value = "";
    page.value = 1;
    query.value = "";
    void load();
  },
  { immediate: true },
);
watch(tab, (newTab) => {
  page.value = 1;
  pageSize.value = newTab === "tools" ? 24 : 20;
});
watch([query, pageSize], () => {
  page.value = 1;
});
onScopeDispose(() => {
  ++epoch;
});

const editorMode = ref<ModelEditorMode>("standard");

function openAddStandard(station: ProviderStation | null = null) {
  if (!canManage.value || saving.value) return;
  detailModel.value = null;
  editingModel.value = null;
  targetStation.value = station;
  editorMode.value = "standard";
  editorOpen.value = true;
}

function openAddCustom(station: ProviderStation | null = null) {
  if (!canManage.value || saving.value) return;
  detailModel.value = null;
  editingModel.value = null;
  targetStation.value = station;
  editorMode.value = "custom";
  editorOpen.value = true;
}

function edit(
  model: RuntimeModelItem | null = null,
  station: ProviderStation | null = null,
) {
  if (!canManage.value || saving.value) return;
  detailModel.value = null;
  editingModel.value = model;
  targetStation.value = station;
  editorMode.value = model ? "edit" : "standard";
  editorOpen.value = true;
}

const deleteDialogState = ref<{
  open: boolean;
  model: RuntimeModelItem | null;
  busy: boolean;
}>({
  open: false,
  model: null,
  busy: false,
});

function confirmDelete(model: RuntimeModelItem) {
  deleteDialogState.value = {
    open: true,
    model,
    busy: false,
  };
}

async function handleDeleteModel() {
  const model = deleteDialogState.value.model;
  if (!model) return;
  deleteDialogState.value.busy = true;
  try {
    await deleteRuntimeModel(activeProjectId.value, model.id);
    notice.value = `已成功删除模型「${model.display_name || model.model}」`;
    deleteDialogState.value.open = false;
    deleteDialogState.value.model = null;
    await load();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "删除失败";
  } finally {
    deleteDialogState.value.busy = false;
  }
}

async function save(payload: ModelEditorSubmitPayload) {
  if (!canManage.value || saving.value) return;
  const isPlatform = platformMode.value;
  const project = activeProjectId.value;
  const requestEpoch = epoch;
  saving.value = true;
  error.value = "";
  notice.value = "";
  const common: Omit<RuntimeModelInput, "model" | "display_name"> = {
    provider: payload.provider,
    base_url: payload.base_url,
    protocol: payload.protocol,
    enabled: payload.enabled,
    ...(payload.api_key ? { api_key: payload.api_key } : {}),
  };
  try {
    if (payload.isEdit && payload.editingId) {
      await updateRuntimeModel(project, payload.editingId, {
        ...common,
        model: payload.models[0].id,
        display_name: payload.display_name,
      });
      if (requestEpoch !== epoch) return;
      notice.value = "模型配置已保存";
    } else {
      const scope_type = isPlatform ? "platform" : "project";
      const project_id = isPlatform ? undefined : project;
      const results = await Promise.allSettled(
        payload.models.map((model) =>
          createRuntimeModel(project, {
            ...common,
            model: model.id,
            display_name: model.name || model.id,
            scope_type,
            project_id,
          }),
        ),
      );
      if (requestEpoch !== epoch) return;
      const failed = results.flatMap((result, index) =>
        result.status === "rejected" ? [payload.models[index].id] : [],
      );
      if (failed.length === results.length) {
        const firstErr = results.find((r) => r.status === "rejected") as PromiseRejectedResult | undefined;
        const errDetail =
          (firstErr?.reason as any)?.response?.data?.detail ||
          (firstErr?.reason instanceof Error ? firstErr.reason.message : "模型创建失败，请检查配置后重试");
        throw new Error(errDetail);
      }
      notice.value = failed.length
        ? `已创建 ${results.length - failed.length} 个模型；未创建：${failed.join("、")}。请仅重新添加失败项。`
        : isPlatform
          ? `已创建 ${results.length} 个全局模型；项目管理员可在项目中设置选用策略。`
          : `已成功接入 ${results.length} 个项目私有模型 (BYOK)！`;
    }
    editorOpen.value = false;
    editingModel.value = null;
    targetStation.value = null;
    saving.value = false;
    await load();
  } catch (cause) {
    if (requestEpoch === epoch)
      error.value = cause instanceof Error ? cause.message : "保存失败";
  } finally {
    if (requestEpoch === epoch) saving.value = false;
  }
}

async function mutate(action: (project: string) => Promise<unknown>) {
  if ((!canManage.value && !canManagePolicy.value) || saving.value || loading.value) return;
  const requestEpoch = epoch;
  saving.value = true;
  error.value = "";
  notice.value = "";
  try {
    await action(activeProjectId.value);
    if (requestEpoch !== epoch) return;
    saving.value = false;
    await load();
  } catch (cause) {
    if (requestEpoch === epoch)
      error.value = cause instanceof Error ? cause.message : "更新失败";
  } finally {
    if (requestEpoch === epoch) saving.value = false;
  }
}

async function doRefreshTools() {
  if (!canRefresh.value || saving.value || loading.value) return;
  const requestEpoch = epoch;
  saving.value = true;
  error.value = "";
  notice.value = "";
  try {
    const result = await refreshRuntimeTools(activeProjectId.value);
    if (requestEpoch !== epoch) return;
    notice.value = `工具同步完成，共 ${result.count} 个工具`;
    saving.value = false;
    await load();
  } catch (cause) {
    if (requestEpoch === epoch)
      error.value = cause instanceof Error ? cause.message : "工具同步失败";
  } finally {
    if (requestEpoch === epoch) saving.value = false;
  }
}

function modelActions(model: RuntimeModelItem): ActionMenuItem[] {
  const actions: ActionMenuItem[] = [
    {
      key: "detail",
      label: "查看详情",
      icon: "eye",
      onSelect: () => {
        detailModel.value = model;
      },
    },
  ];
  if (saving.value || loading.value) return actions;

  const isPrivate = model.scope_type === "project";
  const policy = policies.value[model.id];

  // 1. 全局平台管理模式
  if (platformMode.value && canManagePlatform.value) {
    actions.push({
      key: "edit",
      label: "编辑模型配置",
      icon: "edit",
      onSelect: () => edit(model),
    });
    actions.push({
      key: "toggle",
      label: model.enabled ? "全局停用模型" : "全局启用模型",
      icon: "settings-2",
      onSelect: () =>
        mutate((project) =>
          updateRuntimeModel(project, model.id, { enabled: !model.enabled }),
        ),
    });
    actions.push({
      key: "delete",
      label: "删除模型",
      icon: "trash",
      danger: true,
      onSelect: () => confirmDelete(model),
    });
    return actions;
  }

  // 2. 项目模式下的私有模型 (BYOK)
  if (!platformMode.value && isPrivate) {
    if (canManagePrivate.value) {
      actions.push({
        key: "edit",
        label: "编辑私有模型",
        icon: "edit",
        onSelect: () => edit(model),
      });
    }
    if (canManagePolicy.value && policy) {
      actions.push({
        key: "default",
        label: policy.is_default_for_project ? "取消项目默认" : "设为项目默认",
        icon: "check",
        onSelect: () =>
          mutate((project) =>
            updateRuntimeModelPolicy(project, model.id, {
              is_enabled: true,
              is_default_for_project: !policy.is_default_for_project,
            }),
          ),
      });
    }
    if (canManagePrivate.value) {
      actions.push({
        key: "delete",
        label: "删除私有模型",
        icon: "trash",
        danger: true,
        onSelect: () => confirmDelete(model),
      });
    }
    return actions;
  }

  // 3. 项目视图下的平台公共模型
  if (!platformMode.value && !isPrivate && canManagePolicy.value && policy) {
    actions.push({
      key: "grant",
      label: policy.is_enabled ? "撤销项目授权" : "授权给当前项目",
      icon: "shield",
      onSelect: () =>
        mutate((project) =>
          updateRuntimeModelPolicy(project, model.id, {
            is_enabled: !policy.is_enabled,
            is_default_for_project: false,
          }),
        ),
    });
    if (policy.is_enabled && model.enabled) {
      actions.push({
        key: "default",
        label: policy.is_default_for_project ? "取消项目默认" : "设为项目默认",
        icon: "check",
        onSelect: () =>
          mutate((project) =>
            updateRuntimeModelPolicy(project, model.id, {
              is_enabled: true,
              is_default_for_project: !policy.is_default_for_project,
            }),
          ),
      });
    }
  }

  return actions;
}
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Models & Tools"
      :title="platformMode ? '全局模型连接' : '项目模型与工具'"
      :description="
        platformMode
          ? '维护全平台共用的模型连接、端点、凭据与启停。'
          : '管理项目可用模型与工具。支持接入团队私有模型 (BYOK) 与选用平台公共模型。'
      "
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          :disabled="loading || saving"
          @click="load"
        >
          刷新
        </BaseButton>
        <BaseButton
          v-if="canRefresh && tab === 'tools'"
          variant="secondary"
          :disabled="saving || loading"
          @click="doRefreshTools"
        >
          同步工具
        </BaseButton>
        <BaseButton
          v-if="canManagePolicy && tab === 'tools'"
          variant="primary"
          :disabled="saving || loading"
          @click="toolRestrictionsOpen = true"
        >
          管理禁用规则
        </BaseButton>
        <BaseButton
          v-if="platformMode && canManagePlatform && tab === 'models'"
          :disabled="saving"
          @click="openAddStandard()"
        >
          <BaseIcon
            name="plus"
            size="xs"
          />
          <span>新增平台模型</span>
        </BaseButton>
        <BaseButton
          v-if="!platformMode && canManagePrivate && tab === 'models'"
          variant="primary"
          :disabled="saving"
          @click="openAddStandard()"
        >
          <BaseIcon
            name="plus"
            size="xs"
          />
          <span>添加私有模型 (BYOK)</span>
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
      variant="info"
      title="保存结果"
      :description="notice"
    />
    <RuntimeModelEditor
      v-if="editorOpen"
      :editing-model="editingModel"
      :initial-station="targetStation"
      :initial-mode="editorMode"
      :scope-type="platformMode ? 'platform' : 'project'"
      :busy="saving"
      @close="editorOpen = false"
      @submit="save"
    />
    <div class="flex flex-wrap items-center gap-3">
      <BaseButton
        :variant="tab === 'models' ? 'primary' : 'secondary'"
        @click="tab = 'models'"
      >
        <span>模型</span>
        <span
          v-if="filteredModels.length"
          class="ml-1.5 rounded-full px-1.5 py-0.5 text-xs font-mono"
          :class="tab === 'models' ? 'bg-primary-700/80 text-white dark:bg-primary-300 dark:text-gray-900' : 'bg-gray-200 text-gray-700 dark:bg-dark-700 dark:text-gray-300'"
        >
          {{ filteredModels.length }}
        </span>
      </BaseButton>
      <BaseButton
        v-if="!platformMode"
        :variant="tab === 'tools' ? 'primary' : 'secondary'"
        @click="tab = 'tools'"
      >
        <span>工具目录</span>
        <span
          v-if="filteredTools.length"
          class="ml-1.5 rounded-full px-1.5 py-0.5 text-xs font-mono"
          :class="tab === 'tools' ? 'bg-primary-700/80 text-white dark:bg-primary-300 dark:text-gray-900' : 'bg-gray-200 text-gray-700 dark:bg-dark-700 dark:text-gray-300'"
        >
          {{ filteredTools.length }}
        </span>
      </BaseButton>
      <SearchInput
        v-model="query"
        :placeholder="tab === 'models' ? '搜索名称、提供商或端点' : '搜索工具名称或 tool_key'"
        class="ml-auto max-w-sm"
      />
    </div>
    <p
      v-if="loading"
      role="status"
    >
      正在读取目录与项目授权…
    </p>
    <template v-else-if="!error || items.length || tools.length">
      <p
        v-if="!total"
        class="py-12 text-center text-gray-500"
      >
        没有符合条件的记录
      </p>
      <template v-else-if="tab === 'models'">
        <!-- 全局平台模型管理模式 -->
        <template v-if="platformMode">
          <div class="space-y-4">
            <ProviderStationCard
              v-for="station in stations"
              :key="station.id"
              :station="station"
              :show-policy="false"
              :show-credentials="true"
              :default-model-ids="defaultIds"
              :authorized-model-ids="authorizedIds"
              :can-manage="canManagePlatform && !saving"
              :get-model-actions="modelActions"
              @add-model="edit(null, $event)"
            />
          </div>
        </template>

        <!-- 项目模型管理模式：清晰分为 私有 BYOK 和 平台公共 两大板块 -->
        <div
          v-else
          class="space-y-8"
        >
          <!-- 板块 1: 项目私有模型 (BYOK) -->
          <section class="space-y-4">
            <div
              class="flex flex-wrap items-center justify-between gap-3 border-b border-gray-100 pb-3 dark:border-dark-800"
            >
              <div>
                <div class="flex items-center gap-2">
                  <h2 class="text-base font-semibold text-gray-900 dark:text-white">
                    项目私有模型 (BYOK)
                  </h2>
                  <span
                    class="rounded-full bg-purple-50 px-2.5 py-0.5 text-xs font-semibold text-purple-700 dark:bg-purple-950/50 dark:text-purple-300"
                  >
                    {{ privateModels.length }}
                  </span>
                </div>
                <p class="mt-0.5 text-xs text-gray-500 dark:text-dark-400">
                  本项目自备的模型接入与 API Key，仅当前项目成员可见与调用。由项目自主维护凭据与额度。
                </p>
              </div>
            </div>

            <!-- 私有模型卡片列表 -->
            <div
              v-if="privateStations.length > 0"
              class="space-y-4"
            >
              <ProviderStationCard
                v-for="station in privateStations"
                :key="station.id"
                :station="station"
                :show-policy="true"
                :show-credentials="true"
                :default-model-ids="defaultIds"
                :authorized-model-ids="authorizedIds"
                :can-manage="canManagePrivate && !saving"
                :get-model-actions="modelActions"
                @add-model="edit(null, $event)"
              />

              <!-- 私有模型列表下方的并排新增按钮 -->
              <div
                v-if="canManagePrivate && !editorOpen"
                class="grid grid-cols-1 gap-3 pt-2 sm:grid-cols-2"
              >
                <button
                  type="button"
                  class="flex h-11 items-center justify-center gap-2 rounded-xl border border-dashed border-gray-300 bg-white/50 text-xs font-medium text-gray-700 transition hover:border-purple-400 hover:bg-purple-50/40 hover:text-purple-700 dark:border-dark-700 dark:bg-dark-900/30 dark:text-dark-200 dark:hover:border-purple-500 dark:hover:bg-purple-950/20 dark:hover:text-purple-300"
                  :disabled="saving"
                  @click="openAddStandard()"
                >
                  <BaseIcon
                    name="plus"
                    size="xs"
                  />
                  <span>添加提供方</span>
                </button>
                <button
                  type="button"
                  class="flex h-11 items-center justify-center gap-2 rounded-xl border border-dashed border-gray-300 bg-white/50 text-xs font-medium text-gray-700 transition hover:border-purple-400 hover:bg-purple-50/40 hover:text-purple-700 dark:border-dark-700 dark:bg-dark-900/30 dark:text-dark-200 dark:hover:border-purple-500 dark:hover:bg-purple-950/20 dark:hover:text-purple-300"
                  :disabled="saving"
                  @click="openAddCustom()"
                >
                  <BaseIcon
                    name="plus"
                    size="xs"
                  />
                  <span>添加自定义提供方</span>
                </button>
              </div>
            </div>

            <!-- 无私有模型时的引导卡片 -->
            <div
              v-else
              class="rounded-xl border border-dashed border-gray-200 bg-gray-50/50 p-6 text-center dark:border-dark-700 dark:bg-dark-900/30"
            >
              <div
                class="mx-auto flex h-10 w-10 items-center justify-center rounded-xl bg-purple-50 text-purple-600 dark:bg-purple-950/40 dark:text-purple-300"
              >
                <BaseIcon
                  name="sparkle"
                  size="md"
                />
              </div>
              <h3 class="mt-2.5 text-sm font-semibold text-gray-900 dark:text-white">
                尚未接入项目私有模型
              </h3>
              <p class="mx-auto mt-1 max-w-md text-xs text-gray-500 dark:text-dark-400">
                如果团队有自备的 API Key（如 DeepSeek、OpenAI、Claude 或本地局域网 Ollama/vLLM），可直接添加为私有模型，由项目独立调用与承担费用。
              </p>
              <div
                v-if="canManagePrivate && !editorOpen"
                class="mt-4 flex flex-wrap justify-center gap-3"
              >
                <button
                  type="button"
                  class="flex h-10 items-center justify-center gap-1.5 rounded-xl border border-dashed border-purple-300 bg-purple-50/50 px-4 text-xs font-medium text-purple-700 transition hover:border-purple-400 hover:bg-purple-100/60 dark:border-purple-800 dark:bg-purple-950/40 dark:text-purple-300 dark:hover:bg-purple-900/40"
                  :disabled="saving"
                  @click="openAddStandard()"
                >
                  <BaseIcon
                    name="plus"
                    size="xs"
                  />
                  <span>添加提供方</span>
                </button>
                <button
                  type="button"
                  class="flex h-10 items-center justify-center gap-1.5 rounded-xl border border-dashed border-gray-300 bg-white px-4 text-xs font-medium text-gray-700 transition hover:border-gray-400 hover:bg-gray-50 dark:border-dark-700 dark:bg-dark-800 dark:text-dark-200 dark:hover:bg-dark-700"
                  :disabled="saving"
                  @click="openAddCustom()"
                >
                  <BaseIcon
                    name="plus"
                    size="xs"
                  />
                  <span>添加自定义提供方</span>
                </button>
              </div>
            </div>
          </section>

          <!-- 板块 2: 平台公共模型 -->
          <section class="space-y-4">
            <div
              class="flex flex-wrap items-center justify-between gap-3 border-b border-gray-100 pb-3 dark:border-dark-800"
            >
              <div>
                <div class="flex items-center gap-2">
                  <h2 class="text-base font-semibold text-gray-900 dark:text-white">
                    平台公共模型
                  </h2>
                  <span
                    class="rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-semibold text-blue-700 dark:bg-blue-950/50 dark:text-blue-300"
                  >
                    {{ platformModels.length }}
                  </span>
                </div>
                <p class="mt-0.5 text-xs text-gray-500 dark:text-dark-400">
                  由平台运维统一托管供给的标准化模型基座。项目管理员可按需授权给本项目选用或设为项目默认。
                </p>
              </div>
            </div>

            <!-- 平台模型卡片列表 -->
            <div
              v-if="platformStations.length > 0"
              class="space-y-4"
            >
              <ProviderStationCard
                v-for="station in platformStations"
                :key="station.id"
                :station="station"
                :show-policy="true"
                :show-credentials="true"
                :default-model-ids="defaultIds"
                :authorized-model-ids="authorizedIds"
                :can-manage="false"
                :get-model-actions="modelActions"
              />
            </div>
            <div
              v-else
              class="rounded-xl border border-gray-100 bg-gray-50/50 p-6 text-center text-xs text-gray-400 dark:border-dark-800 dark:bg-dark-900/30 dark:text-dark-500"
            >
              暂无可用的平台公共模型
            </div>
          </section>
        </div>
      </template>
      <!-- 工具卡片列表（只读目录） -->
      <div
        v-else
        class="grid gap-3 md:grid-cols-2 xl:grid-cols-3"
      >
        <article
          v-for="tool in visibleTools"
          :key="tool.id || tool.tool_key"
          class="rounded-xl border border-gray-100 bg-white p-4 shadow-sm dark:border-dark-800 dark:bg-dark-950"
        >
          <!-- 顶部：名称 + 标识 -->
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0 flex-1">
              <h3 class="truncate font-semibold text-gray-900 dark:text-white">
                {{ tool.name || tool.tool_key }}
              </h3>
              <span class="mt-1 inline-block rounded-md bg-gray-100 px-1.5 py-0.5 font-mono text-xs text-gray-500 dark:bg-dark-800 dark:text-dark-300">
                {{ tool.tool_key }}
              </span>
            </div>
            <StatusPill
              :tone="
                tool.sync_status === 'ready'
                  ? 'success'
                  : tool.sync_status === 'error'
                    ? 'danger'
                    : 'warning'
              "
            >
              {{ tool.sync_status }}
            </StatusPill>
          </div>

          <!-- 归属 Graph 标签 -->
          <div
            v-if="tool.graph_ids && tool.graph_ids.length"
            class="mt-2.5 flex flex-wrap items-center gap-1.5"
          >
            <span class="text-[11px] text-gray-400 dark:text-dark-500">归属:</span>
            <span
              v-for="gid in tool.graph_ids"
              :key="gid"
              class="rounded bg-primary-50 px-1.5 py-0.5 font-mono text-[11px] text-primary-700 dark:bg-primary-950/40 dark:text-primary-300"
            >
              {{ gid }}
            </span>
          </div>

          <!-- 描述 -->
          <p class="mt-3 line-clamp-2 text-sm text-gray-500 dark:text-dark-300">
            {{ tool.description || "暂无描述" }}
          </p>

          <!-- 底部：source + 同步时间 -->
          <div class="mt-4 flex items-center justify-between border-t border-gray-100 pt-3 text-xs text-gray-400 dark:border-dark-800 dark:text-dark-400">
            <span>来源: {{ tool.source || "—" }}</span>
            <span
              v-if="tool.last_seen_at"
              class="text-[11px]"
            >
              同步于 {{ new Date(tool.last_seen_at).toLocaleDateString() }}
            </span>
          </div>
        </article>
      </div>
      <PaginationBar
        v-if="platformMode || tab === 'tools'"
        :total="total"
        :page="page"
        :page-size="pageSize"
        :page-size-options="pageSizeOptions"
        :disabled="loading || saving"
        @update:page="page = $event"
        @update:page-size="pageSize = $event"
      />
    </template>
    <RuntimeModelDetailDialog
      :show="!!detailModel"
      :model="detailModel"
      :can-manage="(platformMode && canManagePlatform) || (!platformMode && detailModel?.scope_type === 'project' && canManagePrivate)"
      :is-project-default="!!detailModel && defaultIds.includes(detailModel.id)"
      @close="detailModel = null"
      @edit="edit($event)"
    />
    <BaseDialog
      :show="deleteDialogState.open"
      title="删除模型"
      width="narrow"
      @close="deleteDialogState.open = false"
    >
      <div class="space-y-3 text-sm text-gray-600 dark:text-dark-300">
        <p>
          确定要删除模型
          <strong class="font-mono text-gray-900 dark:text-white">
            {{ deleteDialogState.model?.display_name || deleteDialogState.model?.model }}
          </strong>
          吗？
        </p>
        <p class="text-xs text-rose-600 dark:text-rose-400">
          ⚠️ 此操作将永久移除该模型配置。若有正在使用该模型的任务或 Agent，可能会导致调用失败。
        </p>
      </div>
      <template #footer>
        <div class="flex justify-end gap-3">
          <BaseButton
            variant="secondary"
            :disabled="deleteDialogState.busy"
            @click="deleteDialogState.open = false"
          >
            取消
          </BaseButton>
          <BaseButton
            variant="danger"
            :disabled="deleteDialogState.busy"
            @click="handleDeleteModel"
          >
            {{ deleteDialogState.busy ? "正在删除…" : "确认删除" }}
          </BaseButton>
        </div>
      </template>
    </BaseDialog>
    <ToolRestrictionsPanel
      :show="toolRestrictionsOpen"
      :project-id="activeProjectId"
      :tools="tools"
      :can-manage="canManagePolicy"
      @close="toolRestrictionsOpen = false"
    />
  </section>
</template>

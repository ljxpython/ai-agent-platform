<script setup lang="ts">
import { computed, onScopeDispose, ref, watch } from "vue";
import BaseButton from "@/components/base/BaseButton.vue";
import PageHeader from "@/components/layout/PageHeader.vue";
import SurfaceCard from "@/components/base/SurfaceCard.vue";
import PaginationBar from "@/components/platform/PaginationBar.vue";
import SearchInput from "@/components/platform/SearchInput.vue";
import StateBanner from "@/components/platform/StateBanner.vue";
import { useAuthorization } from "@/composables/useAuthorization";
import { useWorkspaceProjectContext } from "@/composables/useWorkspaceProjectContext";
import { useAuthStore } from "@/stores/auth";
import type { ActionMenuItem } from "@/components/platform/data-table";
import {
  createRuntimeModel,
  listRuntimeModels,
  updateRuntimeModel,
  type RuntimeModelInput,
} from "@/services/runtime/runtime.service";
import {
  listRuntimeModelPolicies,
  listRuntimeToolPolicies,
  updateRuntimeModelPolicy,
  updateRuntimeToolPolicy,
} from "@/services/runtime-policies/runtime-policies.service";
import type {
  RuntimeModelItem,
  RuntimeModelPolicyValue,
  RuntimeToolPolicyItem,
} from "@/types/management";
import RuntimeModelEditor, {
  type ModelEditorSubmitPayload,
} from "../components/RuntimeModelEditor.vue";
import RuntimeModelDetailDialog from "../components/RuntimeModelDetailDialog.vue";
import ProviderStationCard, {
  type ProviderStation,
} from "../components/ProviderStationCard.vue";

const { activeProjectId } = useWorkspaceProjectContext();
const auth = useAuthStore();
const { can } = useAuthorization();
const canManage = computed(() => can("project.runtime.write"));
const items = ref<RuntimeModelItem[]>([]);
const policies = ref<Record<string, RuntimeModelPolicyValue>>({});
const tools = ref<RuntimeToolPolicyItem[]>([]);
const tab = ref<"models" | "tools">("models");
const query = ref("");
const page = ref(1);
const pageSize = ref(20);
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
const stations = computed<ProviderStation[]>(() => {
  const groups = new Map<string, RuntimeModelItem[]>();
  for (const model of filteredModels.value.slice(
    (page.value - 1) * pageSize.value,
    page.value * pageSize.value,
  )) {
    const key = JSON.stringify([
      model.provider,
      model.base_url,
      model.protocol,
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
  }));
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
    if (!project) throw new Error("请先选择项目");
    const [models, modelPolicies, toolPolicies] = await Promise.all([
      listRuntimeModels(project),
      listRuntimeModelPolicies(project),
      listRuntimeToolPolicies(project),
    ]);
    if (requestEpoch !== epoch) return;
    items.value = models.models;
    policies.value = Object.fromEntries(
      modelPolicies.items.map((item) => [item.catalog_id, item.policy]),
    );
    tools.value = toolPolicies.items;
  } catch (cause) {
    if (requestEpoch === epoch)
      error.value = cause instanceof Error ? cause.message : "目录读取失败";
  } finally {
    if (requestEpoch === epoch) loading.value = false;
  }
}
watch(
  [activeProjectId, () => auth.sessionEpoch],
  () => {
    editorOpen.value = false;
    editingModel.value = null;
    targetStation.value = null;
    detailModel.value = null;
    saving.value = false;
    notice.value = "";
    page.value = 1;
    query.value = "";
    void load();
  },
  { immediate: true },
);
watch([tab, query, pageSize], () => {
  page.value = 1;
});
onScopeDispose(() => {
  ++epoch;
});

function edit(
  model: RuntimeModelItem | null = null,
  station: ProviderStation | null = null,
) {
  if (!canManage.value || saving.value) return;
  detailModel.value = null;
  editingModel.value = model;
  targetStation.value = station;
  editorOpen.value = true;
}
async function save(payload: ModelEditorSubmitPayload) {
  if (!canManage.value || saving.value) return;
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
      const results = await Promise.allSettled(
        payload.models.map((model) =>
          createRuntimeModel(project, {
            ...common,
            model: model.id,
            display_name: model.name || model.id,
          }),
        ),
      );
      if (requestEpoch !== epoch) return;
      const failed = results.flatMap((result, index) =>
        result.status === "rejected" ? [payload.models[index].id] : [],
      );
      if (failed.length === results.length)
        throw new Error("模型创建失败，请检查配置后重试");
      notice.value = failed.length
        ? `已创建 ${results.length - failed.length} 个模型；未创建：${failed.join("、")}。请仅重新添加失败项。`
        : `已创建 ${results.length} 个模型，请按需要授权给当前项目。`;
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
  if (!canManage.value || saving.value || loading.value) return;
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
  if (!canManage.value || saving.value || loading.value) return actions;
  const policy = policies.value[model.id];
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
  if (policy) {
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
    if (policy.is_enabled && model.enabled)
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
  return actions;
}
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Models & Tools"
      title="模型与工具"
      description="维护模型连接，并管理当前项目的模型与工具授权。"
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
          v-if="canManage && tab === 'models'"
          :disabled="saving"
          @click="edit()"
        >
          新增模型
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
      :busy="saving"
      @close="editorOpen = false"
      @submit="save"
    />
    <div class="flex flex-wrap items-center gap-3">
      <BaseButton
        :variant="tab === 'models' ? 'primary' : 'secondary'"
        @click="tab = 'models'"
      >
        模型
      </BaseButton>
      <BaseButton
        :variant="tab === 'tools' ? 'primary' : 'secondary'"
        @click="tab = 'tools'"
      >
        工具授权
      </BaseButton>
      <SearchInput
        v-model="query"
        :placeholder="tab === 'models' ? '搜索名称、提供商或端点' : '搜索工具'"
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
        <ProviderStationCard
          v-for="station in stations"
          :key="station.id"
          :station="station"
          :default-model-ids="defaultIds"
          :authorized-model-ids="authorizedIds"
          :can-manage="canManage && !saving"
          :get-model-actions="modelActions"
          @add-model="edit(null, $event)"
        />
      </template>
      <SurfaceCard v-else>
        <div
          v-for="tool in visibleTools"
          :key="tool.catalog_id"
          class="flex items-center justify-between gap-4 border-b border-gray-100 py-4 dark:border-dark-800"
        >
          <div>
            <h2 class="font-medium">
              {{ tool.name || tool.tool_key }}
            </h2>
            <p class="mt-1 text-sm text-gray-500">
              {{ tool.description }}
            </p>
            <p class="mt-1 text-xs text-gray-400">
              {{ tool.tool_key }} · {{ tool.source }}
            </p>
          </div>
          <label class="flex shrink-0 items-center gap-2 text-sm"><input
            type="checkbox"
            :checked="tool.policy.is_enabled"
            :disabled="!canManage || saving"
            @change="
              mutate((project) =>
                updateRuntimeToolPolicy(project, tool.catalog_id, {
                  is_enabled: !tool.policy.is_enabled,
                }),
              )
            "
          >项目授权</label>
        </div>
      </SurfaceCard>
      <PaginationBar
        :total="total"
        :page="page"
        :page-size="pageSize"
        :disabled="loading || saving"
        @update:page="page = $event"
        @update:page-size="pageSize = $event"
      />
    </template>
    <RuntimeModelDetailDialog
      :show="!!detailModel"
      :model="detailModel"
      :can-manage="canManage && !saving"
      :is-project-default="!!detailModel && defaultIds.includes(detailModel.id)"
      @close="detailModel = null"
      @edit="edit($event)"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import { useAuthorization } from '@/composables/useAuthorization'
import { useWorkspaceProjectContext } from '@/composables/useWorkspaceProjectContext'
import PageHeader from '@/components/layout/PageHeader.vue'
import TablePageLayout from '@/components/layout/TablePageLayout.vue'
import { usePagination } from '@/composables/usePagination'
import ActionMenu from '@/components/platform/ActionMenu.vue'
import DataTable from '@/components/platform/DataTable.vue'
import FilterToolbar from '@/components/platform/FilterToolbar.vue'
import MetricCard from '@/components/platform/MetricCard.vue'
import PaginationBar from '@/components/platform/PaginationBar.vue'
import SearchInput from '@/components/platform/SearchInput.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import StatusPill from '@/components/platform/StatusPill.vue'
import type { ActionMenuItem, DataTableColumn } from '@/components/platform/data-table'
import {
  createRuntimeModel,
  listRuntimeModels,
  updateRuntimeModel,
} from '@/services/runtime/runtime.service'
import { listRuntimeModelPolicies, updateRuntimeModelPolicy } from '@/services/runtime-policies/runtime-policies.service'
import { useUiStore } from '@/stores/ui'
import type { RuntimeModelItem, RuntimeModelPolicyValue } from '@/types/management'
import { copyText } from '@/utils/clipboard'
import { formatDateTime, shortId } from '@/utils/format'
import RuntimeModelEditor, { type ModelEditorSubmitPayload } from '../components/RuntimeModelEditor.vue'
import RuntimeModelDetailDialog from '../components/RuntimeModelDetailDialog.vue'
import ProviderStationCard, { type ProviderStation } from '../components/ProviderStationCard.vue'

function getSyncTone(status: string): 'neutral' | 'success' | 'warning' | 'danger' {
  if (status === 'synced' || status === 'ready') {
    return 'success'
  }
  if (status === 'failed' || status === 'error') {
    return 'danger'
  }
  if (status === 'pending') {
    return 'warning'
  }
  return 'neutral'
}

const items = ref<RuntimeModelItem[]>([])
const policies = ref<Record<string, RuntimeModelPolicyValue>>({})
const queryInput = ref('')
const query = ref('')
const loading = ref(false)
const error = ref('')
const notice = ref('')
const editorOpen = ref(false)
const editingModel = ref<RuntimeModelItem | null>(null)
const saving = ref(false)
const detailDialogOpen = ref(false)
const detailTargetModel = ref<RuntimeModelItem | null>(null)
const targetStation = ref<ProviderStation | null>(null)
const viewMode = ref<'stations' | 'table'>('stations')
const lastSyncedAt = ref<string | null>(null)
const { activeProjectId } = useWorkspaceProjectContext()
const uiStore = useUiStore()
const authorization = useAuthorization()
const pagination = usePagination({
  initialPageSize: 20,
  storageKey: 'pw:runtime-models:page-size'
})
const canManageModels = computed(() => authorization.currentProjectCan('project.runtime.write'))
const modelRows = computed(() => filteredItems.value as unknown as Record<string, unknown>[])
const columns = computed<DataTableColumn[]>(() => [
  {
    key: 'model_id',
    label: 'Model ID',
    sortable: true,
    alwaysVisible: true,
    sortValue: (row) => row.model_id || ''
  },
  {
    key: 'display_name',
    label: 'Display Name',
    sortable: true,
    sortValue: (row) => row.display_name || row.model_id || ''
  },
  {
    key: 'is_default',
    label: '默认项',
    sortable: true,
    sortValue: (row) => (row.is_default ? 1 : 0)
  },
  {
    key: 'runtime_id',
    label: 'Runtime',
    sortable: true,
    defaultHidden: true,
    sortValue: (row) => row.runtime_id || ''
  },
  {
    key: 'sync_status',
    label: '同步状态',
    sortable: true,
      sortValue: (row) => row.sync_status || ''
  },
  {
    key: 'enabled',
    label: '状态',
    sortable: true,
    sortValue: (row) => (row.enabled === false ? 0 : 1)
  },
  {
    key: 'credential_configured',
    label: '凭据',
    sortable: true,
    sortValue: (row) => (row.credential_configured ? 1 : 0)
  }
])

const filteredItems = computed(() => {
  const normalized = query.value.trim().toLowerCase()
  if (!normalized) {
    return items.value
  }

  return items.value.filter((item) => {
    const modelId = item.model_id?.toLowerCase() || ''
    const displayName = item.display_name?.toLowerCase() || ''
    return modelId.includes(normalized) || displayName.includes(normalized)
  })
})

function formatStationName(provider: string): string {
  const lower = provider.toLowerCase()
  if (lower.includes('deepseek-proxy')) return 'DeepSeek 中转站'
  if (lower.includes('gpt-proxy')) return 'GPT 中转站'
  if (lower.includes('deepseek')) return 'DeepSeek 官方站'
  if (lower.includes('openai')) return 'OpenAI 官方站'
  if (lower.includes('ollama')) return 'Ollama 本地服务站'
  if (lower.includes('qwen')) return '通义千问 (DashScope) 站'
  if (lower.includes('glm')) return '智谱清言 (GLM) 站'
  if (lower.includes('anthropic')) return 'Anthropic Claude 服务站'
  return `${provider.toUpperCase()} 服务站`
}

const providerStations = computed<ProviderStation[]>(() => {
  const map = new Map<string, RuntimeModelItem[]>()
  for (const item of filteredItems.value) {
    const key = item.provider || 'default'
    if (!map.has(key)) {
      map.set(key, [])
    }
    map.get(key)!.push(item)
  }

  return Array.from(map.entries()).map(([provider, modelList]) => {
    const first = modelList[0]
    const hasCredential = modelList.some((m) => m.credential_configured)
    const hasDefault = modelList.some((m) => m.is_default)
    const enabledCount = modelList.filter((m) => m.enabled !== false).length

    return {
      id: provider,
      name: formatStationName(provider),
      provider,
      baseUrl: first?.base_url || '',
      protocol: first?.protocol || 'openai-compatible',
      credentialConfigured: hasCredential,
      modelCount: modelList.length,
      enabledCount,
      models: modelList,
      isDefaultStation: hasDefault
    }
  })
})

const defaultCount = computed(() => items.value.filter((item) => item.is_default).length)
const stats = computed(() => [
  {
    label: '中转站总量',
    value: providerStations.value.length,
    hint: '已接入的服务端点与渠道数量',
    icon: 'globe',
    tone: 'primary'
  },
  {
    label: '模型总量',
    value: items.value.length,
    hint: 'Runtime 当前暴露的模型目录',
    icon: 'runtime',
    tone: 'primary'
  },
  {
    label: '默认模型',
    value: defaultCount.value,
    hint: '`is_default=true` 的模型数量',
    icon: 'shield',
    tone: 'success'
  },
  {
    label: '当前结果',
    value: filteredItems.value.length,
    hint: query.value ? `按关键词“${query.value}”筛选` : '当前全部模型结果',
    icon: 'overview',
    tone: 'warning'
  }
])

function modelFromRow(row: Record<string, unknown>) {
  return row as RuntimeModelItem
}

async function loadModels() {
  const projectId = activeProjectId.value
  loading.value = true
  error.value = ''

  try {
    const [payload, policyPayload] = await Promise.all([
      listRuntimeModels(projectId),
      listRuntimeModelPolicies(projectId).catch(() => ({ items: [], total: 0 }))
    ])
    policies.value = Object.fromEntries(
      (policyPayload.items || []).map((item) => [item.catalog_id, item.policy])
    )
    items.value = (Array.isArray(payload.models) ? payload.models : []).map((item) => ({
      ...item,
      is_default: policies.value[item.id]?.is_default_for_project ?? item.is_default
    }))
    lastSyncedAt.value = payload.last_synced_at
  } catch (loadError) {
    items.value = []
    lastSyncedAt.value = null
    error.value = loadError instanceof Error ? loadError.message : 'Runtime 模型目录加载失败'
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  query.value = queryInput.value.trim()
  if (pagination.page.value === 1) {
    return
  }

  pagination.resetPage()
}

function resetFilters() {
  queryInput.value = ''
  query.value = ''
  if (pagination.page.value === 1) {
    return
  }

  pagination.resetPage()
}

async function handleCopyValue(label: string, value: string) {
  const copied = await copyText(value)
  uiStore.pushToast({
    type: copied ? 'success' : 'warning',
    title: copied ? `已复制${label}` : '复制失败',
    message: copied ? value : '当前环境不支持自动复制，请手动复制。'
  })
}



function openCreateModel() {
  targetStation.value = null
  editingModel.value = null
  editorOpen.value = true
}

function openEditModel(model: RuntimeModelItem) {
  targetStation.value = null
  editingModel.value = model
  editorOpen.value = true
}

function handleAddFromStation(station: ProviderStation) {
  targetStation.value = station
  editingModel.value = null
  editorOpen.value = true
}

async function handleSaveModel(payload: ModelEditorSubmitPayload) {
  if (!canManageModels.value || saving.value) return
  saving.value = true
  error.value = ''
  notice.value = ''

  try {
    if (payload.isEdit && payload.editingId) {
      const updateData: Record<string, unknown> = {
        provider: payload.provider,
        display_name: payload.display_name,
        base_url: payload.base_url,
        protocol: payload.protocol,
        model: payload.models[0]?.id || payload.display_name,
        enabled: payload.enabled
      }
      if (payload.api_key) {
        updateData.api_key = payload.api_key
      }
      await updateRuntimeModel(activeProjectId.value, payload.editingId, updateData as never)
      notice.value = `模型“${payload.display_name}”配置已成功更新`
    } else {
      // 批量创建模型
      const createTasks = payload.models.map((m) =>
        createRuntimeModel(activeProjectId.value, {
          provider: payload.provider,
          display_name: m.name || m.id,
          base_url: payload.base_url,
          protocol: payload.protocol,
          model: m.id,
          api_key: payload.api_key,
          enabled: payload.enabled
        })
      )
      const results = await Promise.allSettled(createTasks)
      const succeeded = results.filter((r) => r.status === 'fulfilled').length
      const failed = results.filter((r) => r.status === 'rejected')

      if (failed.length === 0) {
        notice.value = `已成功添加 ${succeeded} 个模型并完成配置`
      } else if (succeeded > 0) {
        notice.value = `成功添加 ${succeeded} 个模型，其中 ${failed.length} 个模型添加失败`
      } else {
        const firstError = (failed[0] as PromiseRejectedResult)?.reason
        throw new Error(firstError instanceof Error ? firstError.message : '批量添加模型失败，请检查网络或配置')
      }
    }

    editorOpen.value = false
    await loadModels()
  } catch (saveError) {
    error.value = saveError instanceof Error ? saveError.message : '模型配置保存失败'
  } finally {
    saving.value = false
  }
}

function openModelDetail(model: RuntimeModelItem) {
  detailTargetModel.value = model
  detailDialogOpen.value = true
}

function handleEditFromDetail(model: RuntimeModelItem) {
  detailDialogOpen.value = false
  openEditModel(model)
}

function modelActions(model: RuntimeModelItem): ActionMenuItem[] {
  const policy = policies.value[model.id]
  const actions: ActionMenuItem[] = [
    {
      key: 'copy-model-id',
      label: '复制 Model ID',
      icon: 'copy',
      onSelect: () => handleCopyValue('Model ID', model.model_id)
    },
    {
      key: 'copy-runtime-id',
      label: '复制 Runtime ID',
      icon: 'copy',
      onSelect: () => handleCopyValue('Runtime ID', model.runtime_id)
    },
    {
      key: 'detail',
      label: '查看详情',
      icon: 'eye',
      onSelect: () => openModelDetail(model)
    }
  ]
  if (canManageModels.value) {
    actions.unshift({ key: 'edit', label: '编辑模型', icon: 'edit', onSelect: () => openEditModel(model) })
    actions.push({
      key: 'default',
      label: policy?.is_default_for_project ? '取消项目默认' : '设为项目默认',
      icon: policy?.is_default_for_project ? 'close' : 'check',
      onSelect: async () => {
        try {
          await updateRuntimeModelPolicy(activeProjectId.value, model.id, {
            is_enabled: policy?.is_enabled !== false,
            is_default_for_project: !policy?.is_default_for_project
          })
          await loadModels()
        } catch (policyError) {
          error.value = policyError instanceof Error ? policyError.message : '项目默认模型更新失败'
        }
      }
    })
    actions.push({
      key: 'toggle',
      label: model.enabled === false ? '启用模型' : '停用模型',
      icon: model.enabled === false ? 'check' : 'pause',
      onSelect: async () => {
        await updateRuntimeModel(activeProjectId.value, model.id, { enabled: model.enabled === false }).then(loadModels).catch((toggleError) => {
          error.value = toggleError instanceof Error ? toggleError.message : '模型状态更新失败'
        })
      }
    })
  }
  return actions
}

onMounted(() => {
  void loadModels()
})

watch(
  () => filteredItems.value.length,
  (count) => {
    pagination.setTotal(count)
  },
  { immediate: true }
)

watch(
  () => activeProjectId.value,
  () => {
    void loadModels()
  }
)
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Runtime"
      title="Runtime Models"
      description="模型目录页负责把 model_id、display_name、默认项和同步状态都拉到新工作台，不再依赖旧页面排查配置。"
    >
      <template #actions>
        <BaseButton
          v-if="canManageModels"
          @click="openCreateModel"
        >
          新增模型
        </BaseButton>
      </template>
    </PageHeader>

    <RuntimeModelEditor
      v-if="editorOpen"
      :editing-model="editingModel"
      :initial-station="targetStation"
      :busy="saving"
      @close="editorOpen = false"
      @submit="handleSaveModel"
    />

    <StateBanner
      v-if="error"
      title="Runtime 模型目录加载失败"
      :description="error"
      variant="danger"
    />

    <StateBanner
      v-if="notice"
      title="目录刷新成功"
      :description="notice"
      variant="success"
    />

    <div class="grid gap-4 xl:grid-cols-4">
      <MetricCard
        v-for="item in stats"
        :key="item.label"
        :label="item.label"
        :value="item.value"
        :hint="item.hint"
        :icon="item.icon"
        :tone="item.tone"
      />
    </div>

    <TablePageLayout>
      <template #filters>
        <FilterToolbar>
          <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div class="grid flex-1 gap-3 sm:grid-cols-[minmax(0,1fr)_auto_auto]">
              <SearchInput
                v-model="queryInput"
                placeholder="按 model_id 或 display_name 搜索"
              />
              <BaseButton
                variant="secondary"
                @click="resetFilters"
              >
                清空
              </BaseButton>
              <BaseButton @click="applyFilters">
                应用筛选
              </BaseButton>
            </div>

            <!-- 视图模式切换：中转站聚合视图 vs 全量表格视图 -->
            <div class="inline-flex items-center gap-1 rounded-xl border border-gray-200/80 bg-gray-50/80 p-1 dark:border-dark-700 dark:bg-dark-900/60 shrink-0">
              <button
                type="button"
                class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition"
                :class="viewMode === 'stations' ? 'bg-white text-gray-900 shadow-sm dark:bg-dark-800 dark:text-white font-semibold' : 'text-gray-500 hover:text-gray-900 dark:text-dark-400 dark:hover:text-dark-200'"
                @click="viewMode = 'stations'"
              >
                <BaseIcon
                  name="globe"
                  size="xs"
                />
                <span>中转站视图 ({{ providerStations.length }})</span>
              </button>
              <button
                type="button"
                class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition"
                :class="viewMode === 'table' ? 'bg-white text-gray-900 shadow-sm dark:bg-dark-800 dark:text-white font-semibold' : 'text-gray-500 hover:text-gray-900 dark:text-dark-400 dark:hover:text-dark-200'"
                @click="viewMode = 'table'"
              >
                <BaseIcon
                  name="table"
                  size="xs"
                />
                <span>扁平表格 ({{ filteredItems.length }})</span>
              </button>
            </div>
          </div>
        </FilterToolbar>
      </template>

      <template #table>
        <!-- 中转站卡片聚合视图 -->
        <div
          v-if="viewMode === 'stations'"
          class="space-y-4"
        >
          <div
            v-if="providerStations.length === 0"
            class="pw-panel flex flex-col items-center justify-center py-16 text-center"
          >
            <div class="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-gray-100 text-gray-400 dark:bg-dark-800 dark:text-dark-500">
              <BaseIcon
                name="globe"
                size="lg"
              />
            </div>
            <h3 class="text-sm font-semibold text-gray-900 dark:text-white">
              没有找到中转站或模型配置
            </h3>
            <p class="mt-1 text-xs text-gray-500 dark:text-dark-400">
              {{ items.length ? '没有模型命中当前搜索条件。' : '当前 runtime 没有返回任何模型目录。' }}
            </p>
          </div>

          <ProviderStationCard
            v-for="station in providerStations"
            :key="station.id"
            :station="station"
            :get-model-actions="modelActions"
            @add-model="handleAddFromStation"
            @view-detail="openModelDetail"
          />
        </div>

        <!-- 全量扁平 DataTable 视图 -->
        <DataTable
          v-else
          :columns="columns"
          :rows="modelRows"
          :loading="loading"
          :page="pagination.page.value"
          :page-size="pagination.pageSize.value"
          row-key="id"
          sort-storage-key="pw:runtime-models:sort"
          column-storage-key="pw:runtime-models:columns"
          empty-title="没有找到模型目录"
          :empty-description="
            items.length
              ? '没有模型命中当前搜索条件。'
              : '当前 runtime 没有返回任何模型目录。'
          "
          empty-icon="runtime"
        >
          <template #cell-model_id="{ row }">
            <span class="font-mono text-xs text-gray-500 dark:text-dark-300">
              {{ modelFromRow(row).model_id }}
            </span>
          </template>

          <template #cell-display_name="{ row }">
            <div class="font-semibold text-gray-900 dark:text-white">
              {{ modelFromRow(row).display_name || modelFromRow(row).model_id }}
            </div>
          </template>

          <template #cell-is_default="{ row }">
            <StatusPill :tone="modelFromRow(row).is_default ? 'success' : 'neutral'">
              {{ modelFromRow(row).is_default ? 'default' : 'no' }}
            </StatusPill>
          </template>

          <template #cell-runtime_id="{ row }">
            <span class="text-gray-500 dark:text-dark-300">
              {{ shortId(modelFromRow(row).runtime_id) }}
            </span>
          </template>

          <template #cell-sync_status="{ row }">
            <div class="space-y-2">
              <StatusPill :tone="getSyncTone(modelFromRow(row).sync_status)">
                {{ modelFromRow(row).sync_status || 'unknown' }}
              </StatusPill>
              <div class="text-xs text-gray-400 dark:text-dark-400">
                {{ formatDateTime(modelFromRow(row).last_synced_at) }}
              </div>
            </div>
          </template>

          <template #cell-enabled="{ row }">
            <StatusPill :tone="modelFromRow(row).enabled === false ? 'danger' : 'success'">
              {{ modelFromRow(row).enabled === false ? 'disabled' : 'enabled' }}
            </StatusPill>
          </template>

          <template #cell-credential_configured="{ row }">
            <StatusPill :tone="modelFromRow(row).credential_configured ? 'success' : 'warning'">
              {{ modelFromRow(row).credential_configured ? 'configured' : 'missing' }}
            </StatusPill>
          </template>

          <template #cell-actions="{ row }">
            <ActionMenu :items="modelActions(modelFromRow(row))" />
          </template>
        </DataTable>
      </template>

      <template
        v-if="viewMode === 'table' && pagination.total.value > 0"
        #footer
      >
        <PaginationBar
          :total="pagination.total.value"
          :page="pagination.page.value"
          :page-size="pagination.pageSize.value"
          :disabled="loading"
          @update:page="pagination.setPage"
          @update:page-size="pagination.setPageSize"
        />
      </template>
    </TablePageLayout>

    <RuntimeModelDetailDialog
      :show="detailDialogOpen"
      :model="detailTargetModel"
      @close="detailDialogOpen = false"
      @edit="handleEditFromDetail"
    />
  </section>
</template>

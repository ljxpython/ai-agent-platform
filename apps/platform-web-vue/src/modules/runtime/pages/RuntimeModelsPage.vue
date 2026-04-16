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
  listRuntimeModels,
  submitRuntimeRefreshOperation,
  waitForRuntimeRefreshOperation
} from '@/services/runtime/runtime.service'
import { useUiStore } from '@/stores/ui'
import type { RuntimeModelItem } from '@/types/management'
import { copyText } from '@/utils/clipboard'
import { formatDateTime, shortId } from '@/utils/format'

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
const queryInput = ref('')
const query = ref('')
const loading = ref(false)
const refreshing = ref(false)
const error = ref('')
const notice = ref('')
const lastSyncedAt = ref<string | null>(null)
const { activeProjectId } = useWorkspaceProjectContext()
const uiStore = useUiStore()
const authorization = useAuthorization()
const pagination = usePagination({
  initialPageSize: 20,
  storageKey: 'pw:runtime-models:page-size'
})
const canRefreshCatalog = computed(() =>
  authorization.can('platform.catalog.refresh') || authorization.currentProjectCan('project.runtime.write')
)
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

const defaultCount = computed(() => items.value.filter((item) => item.is_default).length)
const stats = computed(() => [
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
  },
  {
    label: '最近同步',
    value: lastSyncedAt.value ? formatDateTime(lastSyncedAt.value) : '--',
    hint: '模型目录最近一次同步时间',
    icon: 'activity',
    tone: 'danger'
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
    const payload = await listRuntimeModels(projectId)
    items.value = Array.isArray(payload.models) ? payload.models : []
    lastSyncedAt.value = payload.last_synced_at
  } catch (loadError) {
    items.value = []
    lastSyncedAt.value = null
    error.value = loadError instanceof Error ? loadError.message : 'Runtime 模型目录加载失败'
  } finally {
    loading.value = false
  }
}

async function handleRefreshCatalog() {
  const projectId = activeProjectId.value
  if (!canRefreshCatalog.value) {
    error.value = '当前账号没有刷新 Runtime 目录的权限'
    return
  }
  refreshing.value = true
  error.value = ''
  notice.value = ''

  try {
    const operation = await submitRuntimeRefreshOperation('models', projectId)
    notice.value = `模型目录刷新任务已提交，任务号 ${shortId(operation.id)}`
    const finalOperation = await waitForRuntimeRefreshOperation(operation.id, {
      timeoutMs: 90000
    })
    if (finalOperation.status !== 'succeeded') {
      throw new Error(
        (finalOperation.error_payload?.message as string | undefined) || 'Runtime 模型目录刷新未成功完成'
      )
    }
    const count = Number(finalOperation.result_payload?.count || 0)
    notice.value = `Runtime 模型目录已刷新，当前同步 ${count} 条记录`
    await loadModels()
  } catch (refreshError) {
    error.value = refreshError instanceof Error ? refreshError.message : 'Runtime 模型目录刷新失败'
  } finally {
    refreshing.value = false
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

function handlePendingAction(message: string) {
  uiStore.pushToast({
    type: 'info',
    title: '详情暂未开放',
    message
  })
}

function modelActions(model: RuntimeModelItem): ActionMenuItem[] {
  return [
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
      label: '查看详情（暂未开放）',
      icon: 'eye',
      onSelect: () => handlePendingAction(`模型 ${model.display_name || model.model_id} 的详情页暂未开放，请先查看当前目录信息。`)
    }
  ]
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
        <router-link
          class="pw-btn pw-btn-secondary"
          to="/workspace/runtime"
        >
          返回 Runtime
        </router-link>
        <router-link
          class="pw-btn pw-btn-secondary"
          to="/workspace/runtime/tools"
        >
          工具目录
        </router-link>
        <BaseButton
          variant="secondary"
          :disabled="refreshing || !canRefreshCatalog"
          @click="handleRefreshCatalog"
        >
          <BaseIcon
            name="refresh"
            size="sm"
          />
          {{ canRefreshCatalog ? (refreshing ? '刷新中...' : '刷新目录') : '当前账号只读' }}
        </BaseButton>
      </template>
    </PageHeader>

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
          <div class="grid gap-4 xl:grid-cols-[minmax(0,1fr)_auto_auto]">
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
        </FilterToolbar>
      </template>

      <template #table>
        <DataTable
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

          <template #cell-actions="{ row }">
            <ActionMenu :items="modelActions(modelFromRow(row))" />
          </template>
        </DataTable>
      </template>

      <template
        v-if="pagination.total.value > 0"
        #footer
      >
        <PaginationBar
          :total="pagination.total.value"
          :page="pagination.page.value"
          :page-size="pagination.pageSize.value"
          :disabled="loading || refreshing"
          @update:page="pagination.setPage"
          @update:page-size="pagination.setPageSize"
        />
      </template>
    </TablePageLayout>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
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
import { resolvePlatformClientScope } from '@/services/platform/control-plane'
import {
  listRuntimeTools,
  refreshRuntimeTools,
  submitRuntimeRefreshOperation,
  waitForRuntimeRefreshOperation
} from '@/services/runtime/runtime.service'
import { useWorkspaceStore } from '@/stores/workspace'
import { useUiStore } from '@/stores/ui'
import type { RuntimeToolItem } from '@/types/management'
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

const items = ref<RuntimeToolItem[]>([])
const queryInput = ref('')
const query = ref('')
const loading = ref(false)
const refreshing = ref(false)
const error = ref('')
const notice = ref('')
const lastSyncedAt = ref<string | null>(null)
const workspaceStore = useWorkspaceStore()
const uiStore = useUiStore()
const pagination = usePagination({
  initialPageSize: 20,
  storageKey: 'pw:runtime-tools:page-size'
})
const toolRows = computed(() => filteredItems.value as unknown as Record<string, unknown>[])
const columns = computed<DataTableColumn[]>(() => [
  {
    key: 'name',
    label: 'Tool',
    sortable: true,
    alwaysVisible: true,
    sortValue: (row) => row.name || row.tool_key || ''
  },
  {
    key: 'source',
    label: 'Source',
    sortable: true,
    sortValue: (row) => row.source || ''
  },
  {
    key: 'description',
    label: 'Description',
    sortable: true,
    sortValue: (row) => row.description || '',
    cellClass: 'max-w-[420px]'
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
    const name = item.name?.toLowerCase() || ''
    const source = item.source?.toLowerCase() || ''
    const description = item.description?.toLowerCase() || ''
    return (
      name.includes(normalized) || source.includes(normalized) || description.includes(normalized)
    )
  })
})

const sourceCount = computed(() => new Set(items.value.map((item) => item.source).filter(Boolean)).size)
const stats = computed(() => [
  {
    label: '工具总量',
    value: items.value.length,
    hint: 'Runtime 当前暴露的工具目录',
    icon: 'activity',
    tone: 'primary'
  },
  {
    label: '来源数',
    value: sourceCount.value,
    hint: '当前工具目录覆盖的 source 数量',
    icon: 'overview',
    tone: 'success'
  },
  {
    label: '当前结果',
    value: filteredItems.value.length,
    hint: query.value ? `按关键词“${query.value}”筛选` : '当前全部工具结果',
    icon: 'search',
    tone: 'warning'
  },
  {
    label: '最近同步',
    value: lastSyncedAt.value ? formatDateTime(lastSyncedAt.value) : '--',
    hint: '工具目录最近一次同步时间',
    icon: 'shield',
    tone: 'danger'
  }
])

function toolFromRow(row: Record<string, unknown>) {
  return row as RuntimeToolItem
}

async function loadTools() {
  const projectId = workspaceStore.runtimeScopedProjectId
  loading.value = true
  error.value = ''

  try {
    const payload = await listRuntimeTools(projectId)
    items.value = Array.isArray(payload.tools) ? payload.tools : []
    lastSyncedAt.value = payload.last_synced_at
  } catch (loadError) {
    items.value = []
    lastSyncedAt.value = null
    error.value = loadError instanceof Error ? loadError.message : 'Runtime 工具目录加载失败'
  } finally {
    loading.value = false
  }
}

async function handleRefreshCatalog() {
  const projectId = workspaceStore.runtimeScopedProjectId
  refreshing.value = true
  error.value = ''
  notice.value = ''

  try {
    if (
      resolvePlatformClientScope('runtime_catalog') === 'v2' &&
      resolvePlatformClientScope('operations') === 'v2'
    ) {
      const operation = await submitRuntimeRefreshOperation('tools', projectId)
      notice.value = `工具目录刷新任务已提交，任务号 ${shortId(operation.id)}`
      const finalOperation = await waitForRuntimeRefreshOperation(operation.id, {
        timeoutMs: 90000
      })
      if (finalOperation.status !== 'succeeded') {
        throw new Error(
          (finalOperation.error_payload?.message as string | undefined) || 'Runtime 工具目录刷新未成功完成'
        )
      }
      const count = Number(finalOperation.result_payload?.count || 0)
      notice.value = `Runtime 工具目录已刷新，当前同步 ${count} 条记录`
    } else {
      const payload = await refreshRuntimeTools(projectId)
      notice.value = `Runtime 工具目录已刷新，当前同步 ${payload.count} 条记录`
    }
    await loadTools()
  } catch (refreshError) {
    error.value = refreshError instanceof Error ? refreshError.message : 'Runtime 工具目录刷新失败'
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
    title: '能力待迁移',
    message
  })
}

function toolActions(tool: RuntimeToolItem): ActionMenuItem[] {
  return [
    {
      key: 'copy-tool-key',
      label: '复制 Tool Key',
      icon: 'copy',
      onSelect: () => handleCopyValue('Tool Key', tool.tool_key)
    },
    {
      key: 'copy-runtime-id',
      label: '复制 Runtime ID',
      icon: 'copy',
      onSelect: () => handleCopyValue('Runtime ID', tool.runtime_id)
    },
    {
      key: 'detail',
      label: '工具详情待迁移',
      icon: 'eye',
      onSelect: () => handlePendingAction(`工具 ${tool.name || tool.tool_key} 的详情页仍在迁移队列中。`)
    }
  ]
}

onMounted(() => {
  void loadTools()
})

watch(
  () => filteredItems.value.length,
  (count) => {
    pagination.setTotal(count)
  },
  { immediate: true }
)

watch(
  () => workspaceStore.runtimeScopedProjectId,
  () => {
    void loadTools()
  }
)
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Runtime"
      title="Runtime Tools"
      description="工具目录页把 tool key、source、description 和同步状态统一拉回新工作台，后续助手挂工具不再需要回旧系统排查。"
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
          to="/workspace/runtime/models"
        >
          模型目录
        </router-link>
        <BaseButton
          variant="secondary"
          :disabled="refreshing"
          @click="handleRefreshCatalog"
        >
          <BaseIcon
            name="refresh"
            size="sm"
          />
          {{ refreshing ? '刷新中...' : '刷新目录' }}
        </BaseButton>
      </template>
    </PageHeader>

    <StateBanner
      v-if="error"
      title="Runtime 工具目录加载失败"
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
              placeholder="按 name、source 或 description 搜索"
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
          :rows="toolRows"
          :loading="loading"
          :page="pagination.page.value"
          :page-size="pagination.pageSize.value"
          row-key="id"
          sort-storage-key="pw:runtime-tools:sort"
          column-storage-key="pw:runtime-tools:columns"
          empty-title="没有找到工具目录"
          :empty-description="
            items.length
              ? '没有工具命中当前搜索条件。'
              : '当前 runtime 没有返回任何工具目录。'
          "
          empty-icon="activity"
        >
          <template #cell-name="{ row }">
            <div>
              <div class="font-semibold text-gray-900 dark:text-white">
                {{ toolFromRow(row).name || toolFromRow(row).tool_key }}
              </div>
              <div class="mt-1 font-mono text-xs text-gray-400 dark:text-dark-400">
                {{ toolFromRow(row).tool_key }}
              </div>
            </div>
          </template>

          <template #cell-source="{ row }">
            <span class="text-gray-500 dark:text-dark-300">
              {{ toolFromRow(row).source || '--' }}
            </span>
          </template>

          <template #cell-description="{ row }">
            <span class="text-gray-500 dark:text-dark-300">
              {{ toolFromRow(row).description?.trim() || '暂无描述' }}
            </span>
          </template>

          <template #cell-runtime_id="{ row }">
            <span class="text-gray-500 dark:text-dark-300">
              {{ shortId(toolFromRow(row).runtime_id) }}
            </span>
          </template>

          <template #cell-sync_status="{ row }">
            <div class="space-y-2">
              <StatusPill :tone="getSyncTone(toolFromRow(row).sync_status)">
                {{ toolFromRow(row).sync_status || 'unknown' }}
              </StatusPill>
              <div class="text-xs text-gray-400 dark:text-dark-400">
                {{ formatDateTime(toolFromRow(row).last_synced_at) }}
              </div>
            </div>
          </template>

          <template #cell-actions="{ row }">
            <ActionMenu :items="toolActions(toolFromRow(row))" />
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

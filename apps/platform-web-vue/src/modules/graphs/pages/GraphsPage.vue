<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import TablePageLayout from '@/components/layout/TablePageLayout.vue'
import { usePagination } from '@/composables/usePagination'
import ActionMenu from '@/components/platform/ActionMenu.vue'
import DataTable from '@/components/platform/DataTable.vue'
import EmptyState from '@/components/platform/EmptyState.vue'
import FilterToolbar from '@/components/platform/FilterToolbar.vue'
import MetricCard from '@/components/platform/MetricCard.vue'
import PaginationBar from '@/components/platform/PaginationBar.vue'
import SearchInput from '@/components/platform/SearchInput.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import StatusPill from '@/components/platform/StatusPill.vue'
import type { ActionMenuItem, DataTableColumn } from '@/components/platform/data-table'
import { listGraphsPage, refreshGraphsCatalog } from '@/services/graphs/graphs.service'
import { useUiStore } from '@/stores/ui'
import { useWorkspaceStore } from '@/stores/workspace'
import type { ManagementGraph } from '@/types/management'
import { copyText } from '@/utils/clipboard'
import { writeRecentChatTarget } from '@/utils/chatTarget'
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

const workspaceStore = useWorkspaceStore()
const uiStore = useUiStore()
const router = useRouter()

const items = ref<ManagementGraph[]>([])
const queryInput = ref('')
const query = ref('')
const loading = ref(false)
const refreshing = ref(false)
const error = ref('')
const notice = ref('')
const lastSyncedAt = ref<string | null>(null)
const graphRows = computed(() => items.value as unknown as Record<string, unknown>[])
const pagination = usePagination({
  initialPageSize: 20,
  storageKey: 'pw:graphs:page-size'
})
const columns = computed<DataTableColumn[]>(() => [
  {
    key: 'graph_id',
    label: 'Graph',
    sortable: true,
    alwaysVisible: true,
    sortValue: (row) => row.graph_id || ''
  },
  {
    key: 'display_name',
    label: 'Display Name',
    sortable: true,
    sortValue: (row) => row.display_name || row.graph_id || ''
  },
  {
    key: 'description',
    label: 'Description',
    sortable: true,
    cellClass: 'max-w-[360px]',
    sortValue: (row) => row.description || ''
  },
  {
    key: 'source_type',
    label: 'Source',
    sortable: true,
    sortValue: (row) => row.source_type || ''
  },
  {
    key: 'sync_status',
    label: '同步状态',
    sortable: true,
    sortValue: (row) => row.sync_status || ''
  }
])

const currentProject = computed(() => workspaceStore.currentProject)
const syncedCount = computed(() =>
  items.value.filter((item) => item.sync_status === 'synced' || item.sync_status === 'ready').length
)
const stats = computed(() => [
  {
    label: '当前项目',
    value: currentProject.value?.name || '未选择',
    hint: '图谱目录严格跟随当前项目上下文',
    icon: 'project',
    tone: 'primary'
  },
  {
    label: '当前结果',
    value: items.value.length,
    hint: `当前结果集总数 ${pagination.total.value}`,
    icon: 'graph',
    tone: 'success'
  },
  {
    label: '已同步',
    value: syncedCount.value,
    hint: 'sync_status 为 synced 或 ready 的图谱',
    icon: 'shield',
    tone: 'warning'
  },
  {
    label: '最近同步',
    value: lastSyncedAt.value ? formatDateTime(lastSyncedAt.value) : '--',
    hint: '图谱目录最近一次同步时间',
    icon: 'activity',
    tone: 'danger'
  }
])

function graphFromRow(row: Record<string, unknown>) {
  return row as ManagementGraph
}

async function loadGraphs() {
  const projectId = workspaceStore.currentProjectId
  if (!projectId) {
    items.value = []
    pagination.setTotal(0)
    lastSyncedAt.value = null
    error.value = ''
    loading.value = false
    return
  }

  loading.value = true
  error.value = ''

  try {
    const payload = await listGraphsPage(projectId, {
      limit: pagination.pageSize.value,
      offset: pagination.offset.value,
      query: query.value
    }, { mode: 'runtime' })

    items.value = payload.items
    pagination.setTotal(payload.total)
    lastSyncedAt.value = payload.last_synced_at ?? null
  } catch (loadError) {
    items.value = []
    pagination.setTotal(0)
    lastSyncedAt.value = null
    error.value = loadError instanceof Error ? loadError.message : '图谱目录加载失败'
  } finally {
    loading.value = false
  }
}

async function handleRefreshCatalog() {
  const projectId = workspaceStore.currentProjectId
  if (!projectId) {
    return
  }

  refreshing.value = true
  error.value = ''
  notice.value = ''

  try {
    const payload = await refreshGraphsCatalog(projectId, { mode: 'runtime' })
    notice.value = `图谱目录已刷新，当前同步 ${payload.count} 条记录`
    await loadGraphs()
  } catch (refreshError) {
    error.value = refreshError instanceof Error ? refreshError.message : '图谱目录刷新失败'
  } finally {
    refreshing.value = false
  }
}

function applyFilters() {
  query.value = queryInput.value.trim()
  if (pagination.page.value === 1) {
    void loadGraphs()
    return
  }

  pagination.resetPage()
}

function resetFilters() {
  queryInput.value = ''
  query.value = ''
  if (pagination.page.value === 1) {
    void loadGraphs()
    return
  }

  pagination.resetPage()
}

function setAsRecentChatTarget(graph: ManagementGraph) {
  const projectId = workspaceStore.currentProjectId
  if (!projectId) {
    return
  }

  writeRecentChatTarget(projectId, {
    targetType: 'graph',
    graphId: graph.graph_id,
    graphName: graph.display_name || graph.graph_id
  })
  uiStore.pushToast({
    type: 'success',
    title: '已设为聊天目标',
    message: graph.display_name || graph.graph_id
  })
}

function openGraphChat(graph: ManagementGraph) {
  const projectId = workspaceStore.currentProjectId

  if (projectId) {
    writeRecentChatTarget(projectId, {
      targetType: 'graph',
      graphId: graph.graph_id,
      graphName: graph.display_name || graph.graph_id
    })
  }

  void router.push({
    path: '/workspace/chat',
    query: {
      targetType: 'graph',
      graphId: graph.graph_id,
      graphName: graph.display_name || graph.graph_id
    }
  })
}

async function handleCopyGraphId(graph: ManagementGraph) {
  const copied = await copyText(graph.graph_id)
  uiStore.pushToast({
    type: copied ? 'success' : 'warning',
    title: copied ? '已复制 Graph ID' : '复制失败',
    message: copied ? graph.graph_id : '当前环境不支持自动复制，请手动复制。'
  })
}

function handlePendingAction(message: string) {
  uiStore.pushToast({
    type: 'info',
    title: '能力待迁移',
    message
  })
}

function graphActions(graph: ManagementGraph): ActionMenuItem[] {
  return [
    {
      key: 'open-chat',
      label: '打开聊天',
      icon: 'chat',
      onSelect: () => openGraphChat(graph)
    },
    {
      key: 'focus-chat-target',
      label: '设为聊天目标',
      icon: 'chat',
      onSelect: () => setAsRecentChatTarget(graph)
    },
    {
      key: 'copy-graph-id',
      label: '复制 Graph ID',
      icon: 'copy',
      onSelect: () => handleCopyGraphId(graph)
    },
    {
      key: 'detail',
      label: '图谱详情待迁移',
      icon: 'eye',
      onSelect: () => handlePendingAction(`图谱 ${graph.display_name || graph.graph_id} 的详情页仍在迁移队列中。`)
    }
  ]
}

watch(
  () => workspaceStore.currentProjectId,
  () => {
    if (pagination.page.value !== 1) {
      pagination.resetPage()
      return
    }

    void loadGraphs()
  },
  { immediate: true }
)

watch([() => pagination.page.value, () => pagination.pageSize.value], () => {
  void loadGraphs()
})
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Graphs"
      title="Graphs"
      description="图谱目录页先承接 catalog 可见性、搜索和聊天目标预设。助手、Threads 和 Chat 后续都会继续消费这套目录数据。"
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          :disabled="!currentProject || refreshing"
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
      title="图谱目录加载失败"
      :description="error"
      variant="danger"
    />

    <StateBanner
      v-if="notice"
      title="操作成功"
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

    <EmptyState
      v-if="!currentProject"
      icon="project"
      title="请先选择项目"
      description="图谱目录是项目级能力。不带 project 上下文去看 catalog，会把后续 Chat 和 Threads 的目标绑定全搞乱。"
    />

    <TablePageLayout v-else>
      <template #filters>
        <FilterToolbar>
          <div class="grid gap-4 xl:grid-cols-[minmax(0,1fr)_auto_auto]">
            <SearchInput
              v-model="queryInput"
              :placeholder="`在 ${currentProject.name} 下搜索图谱`"
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
          :rows="graphRows"
          :loading="loading"
          row-key="id"
          sort-storage-key="pw:graphs:sort"
          column-storage-key="pw:graphs:columns"
          empty-title="没有找到图谱目录"
          empty-description="当前项目下没有图谱数据，或者没有结果命中筛选条件。可以先刷新 catalog，再确认 runtime 同步链路。"
          empty-icon="graph"
        >
          <template #cell-graph_id="{ row }">
            <div class="font-semibold text-gray-900 dark:text-white">
              {{ graphFromRow(row).graph_id }}
            </div>
            <div class="mt-1 text-xs text-gray-400 dark:text-dark-400">
              {{ shortId(graphFromRow(row).id) }}
            </div>
          </template>

          <template #cell-display_name="{ row }">
            <span class="text-gray-900 dark:text-white">
              {{ graphFromRow(row).display_name || graphFromRow(row).graph_id }}
            </span>
          </template>

          <template #cell-description="{ row }">
            <span class="text-gray-500 dark:text-dark-300">
              {{ graphFromRow(row).description?.trim() || '暂无描述' }}
            </span>
          </template>

          <template #cell-source_type="{ row }">
            <span class="text-gray-500 dark:text-dark-300">
              {{ graphFromRow(row).source_type || '--' }}
            </span>
          </template>

          <template #cell-sync_status="{ row }">
            <div class="space-y-2">
              <StatusPill :tone="getSyncTone(graphFromRow(row).sync_status)">
                {{ graphFromRow(row).sync_status || 'unknown' }}
              </StatusPill>
              <div class="text-xs text-gray-400 dark:text-dark-400">
                {{ formatDateTime(graphFromRow(row).last_synced_at) }}
              </div>
            </div>
          </template>

          <template #cell-actions="{ row }">
            <ActionMenu :items="graphActions(graphFromRow(row))" />
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

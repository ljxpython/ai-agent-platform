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
import { listAssistantsPage } from '@/services/assistants/assistants.service'
import { useUiStore } from '@/stores/ui'
import { useWorkspaceStore } from '@/stores/workspace'
import type { ManagementAssistant } from '@/types/management'
import { copyText } from '@/utils/clipboard'
import { writeRecentChatTarget } from '@/utils/chatTarget'
import { formatDateTime, shortId } from '@/utils/format'

const router = useRouter()
const workspaceStore = useWorkspaceStore()
const uiStore = useUiStore()

const queryInput = ref('')
const query = ref('')
const loading = ref(false)
const error = ref('')
const items = ref<ManagementAssistant[]>([])
const assistantRows = computed(() => items.value as unknown as Record<string, unknown>[])
const pagination = usePagination({
  initialPageSize: 20,
  storageKey: 'pw:assistants:page-size'
})
const columns = computed<DataTableColumn[]>(() => [
  {
    key: 'name',
    label: '助手',
    sortable: true,
    alwaysVisible: true,
    sortValue: (row) => row.name
  },
  {
    key: 'graph_id',
    label: 'Graph',
    sortable: true,
    sortValue: (row) => row.graph_id || ''
  },
  {
    key: 'sync_status',
    label: '同步状态',
    sortable: true,
    sortValue: (row) => row.sync_status || ''
  },
  {
    key: 'status',
    label: '运行状态',
    sortable: true,
    sortValue: (row) => row.status || ''
  },
  {
    key: 'last_synced_at',
    label: '最近同步',
    sortable: true,
    sortValue: (row) => row.last_synced_at || row.updated_at || ''
  },
  {
    key: 'id',
    label: 'ID',
    sortable: true,
    defaultHidden: true,
    sortValue: (row) => row.id
  }
])

const currentProject = computed(() => workspaceStore.currentProject)
const activeCount = computed(() => items.value.filter((item) => item.status === 'active').length)
const syncIssueCount = computed(() => items.value.filter((item) => item.sync_status !== 'synced').length)
const stats = computed(() => [
  {
    label: '当前项目',
    value: currentProject.value?.name || '未选择',
    hint: '助手列表严格跟随当前 project 上下文',
    icon: 'project',
    tone: 'primary'
  },
  {
    label: '助手数量',
    value: pagination.total.value,
    hint: '当前项目下返回的助手总量',
    icon: 'assistant',
    tone: 'success'
  },
  {
    label: '同步异常',
    value: syncIssueCount.value,
    hint: 'sync_status 不为 synced 的助手',
    icon: 'activity',
    tone: 'warning'
  },
  {
    label: '已启用',
    value: activeCount.value,
    hint: '状态为 active 的助手',
    icon: 'sparkle',
    tone: 'danger'
  }
])

function assistantFromRow(row: Record<string, unknown>) {
  return row as ManagementAssistant
}

async function loadAssistants() {
  const projectId = workspaceStore.currentProjectId
  if (!projectId) {
    items.value = []
    pagination.setTotal(0)
    error.value = ''
    loading.value = false
    return
  }

  loading.value = true
  error.value = ''

  try {
    const payload = await listAssistantsPage(projectId, {
      limit: pagination.pageSize.value,
      offset: pagination.offset.value,
      query: query.value
    })

    items.value = payload.items
    pagination.setTotal(payload.total)
  } catch (loadError) {
    items.value = []
    pagination.setTotal(0)
    error.value = loadError instanceof Error ? loadError.message : '助手列表加载失败'
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  query.value = queryInput.value.trim()
  if (pagination.page.value === 1) {
    void loadAssistants()
    return
  }

  pagination.resetPage()
}

function resetFilters() {
  queryInput.value = ''
  query.value = ''
  if (pagination.page.value === 1) {
    void loadAssistants()
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

function resolveAssistantTargetId(assistant: ManagementAssistant) {
  return assistant.langgraph_assistant_id?.trim() || assistant.id
}

function openAssistantChat(assistant: ManagementAssistant) {
  const assistantId = resolveAssistantTargetId(assistant)
  const projectId = workspaceStore.currentProjectId

  if (projectId) {
    writeRecentChatTarget(projectId, {
      targetType: 'assistant',
      assistantId
    })
  }

  void router.push({
    path: '/workspace/chat',
    query: {
      targetType: 'assistant',
      assistantId
    }
  })
}

function setAssistantAsRecentTarget(assistant: ManagementAssistant) {
  const projectId = workspaceStore.currentProjectId
  const assistantId = resolveAssistantTargetId(assistant)
  if (!projectId) {
    return
  }

  writeRecentChatTarget(projectId, {
    targetType: 'assistant',
    assistantId
  })

  uiStore.pushToast({
    type: 'success',
    title: '已设为聊天目标',
    message: assistant.name || assistantId
  })
}

function assistantActions(assistant: ManagementAssistant): ActionMenuItem[] {
  return [
    {
      key: 'open-chat',
      label: '打开聊天',
      icon: 'chat',
      onSelect: () => openAssistantChat(assistant)
    },
    {
      key: 'focus-chat-target',
      label: '设为聊天目标',
      icon: 'check',
      onSelect: () => setAssistantAsRecentTarget(assistant)
    },
    {
      key: 'copy-id',
      label: '复制助手 ID',
      icon: 'copy',
      onSelect: () => handleCopyValue('助手 ID', assistant.id)
    },
    {
      key: 'copy-graph-id',
      label: assistant.graph_id ? '复制 Graph ID' : '未绑定 Graph',
      icon: 'copy',
      disabled: !assistant.graph_id,
      onSelect: () => handleCopyValue('Graph ID', assistant.graph_id || '')
    },
    {
      key: 'copy-langgraph-assistant-id',
      label: assistant.langgraph_assistant_id ? '复制 LangGraph ID' : '未绑定 LangGraph ID',
      icon: 'copy',
      disabled: !assistant.langgraph_assistant_id,
      onSelect: () => handleCopyValue('LangGraph Assistant ID', assistant.langgraph_assistant_id || '')
    },
    {
      key: 'detail',
      label: '助手详情',
      icon: 'eye',
      onSelect: () => void router.push(`/workspace/assistants/${assistant.id}`)
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

    void loadAssistants()
  },
  { immediate: true }
)

watch([() => pagination.page.value, () => pagination.pageSize.value], () => {
  void loadAssistants()
})
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Assistants"
      title="助手管理"
      description="Agent 是汇报里的重点，所以这页先把项目上下文、助手列表和同步状态做成像样的后台页。"
    >
      <template #actions>
        <BaseButton
          :disabled="!currentProject"
          @click="void router.push('/workspace/assistants/new')"
        >
          <BaseIcon
            name="assistant"
            size="sm"
          />
          新建助手
        </BaseButton>
        <BaseButton
          variant="secondary"
          :disabled="!currentProject"
          @click="loadAssistants"
        >
          <BaseIcon
            name="refresh"
            size="sm"
          />
          刷新
        </BaseButton>
      </template>
    </PageHeader>

    <StateBanner
      v-if="error"
      title="助手列表加载失败"
      :description="error"
      variant="danger"
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
      description="助手是项目级资源，不带 project 上下文去查只会把接口边界搞乱。先通过顶部项目切换器选中项目，再进入这里。"
    />

    <TablePageLayout v-else>
      <template #filters>
        <FilterToolbar>
          <div class="grid gap-4 xl:grid-cols-[minmax(0,1fr)_auto_auto]">
            <SearchInput
              v-model="queryInput"
              :placeholder="`在 ${currentProject.name} 下搜索助手`"
            />
            <BaseButton
              variant="secondary"
              @click="resetFilters"
            >
              重置
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
          :rows="assistantRows"
          :loading="loading"
          row-key="id"
          sort-storage-key="pw:assistants:sort"
          column-storage-key="pw:assistants:columns"
          empty-title="当前项目还没有助手"
          empty-description="接口已经接通了，只是这个项目下暂时没有可展示的数据。后续新建助手和详情页可以直接挂在这张列表母版上继续做。"
          empty-icon="assistant"
        >
          <template #cell-name="{ row }">
            <div class="flex items-start gap-3">
              <div class="mt-0.5 flex h-9 w-9 items-center justify-center rounded-xl bg-primary-50 text-primary-600 dark:bg-primary-950/40 dark:text-primary-300">
                <BaseIcon
                  name="assistant"
                  size="sm"
                />
              </div>
              <div>
                <div class="font-semibold text-gray-900 dark:text-white">
                  {{ assistantFromRow(row).name }}
                </div>
                <div class="mt-1 text-sm leading-6 text-gray-500 dark:text-dark-300">
                  {{ assistantFromRow(row).description || '暂无描述' }}
                </div>
              </div>
            </div>
          </template>

          <template #cell-graph_id="{ row }">
            <span class="text-gray-500 dark:text-dark-300">
              {{ assistantFromRow(row).graph_id || '未绑定' }}
            </span>
          </template>

          <template #cell-sync_status="{ row }">
            <StatusPill :tone="assistantFromRow(row).sync_status === 'synced' ? 'success' : 'warning'">
              {{ assistantFromRow(row).sync_status }}
            </StatusPill>
          </template>

          <template #cell-status="{ row }">
            <StatusPill :tone="assistantFromRow(row).status === 'active' ? 'success' : 'warning'">
              {{ assistantFromRow(row).status }}
            </StatusPill>
          </template>

          <template #cell-last_synced_at="{ row }">
            <span class="text-gray-500 dark:text-dark-300">
              {{ formatDateTime(assistantFromRow(row).last_synced_at || assistantFromRow(row).updated_at) }}
            </span>
          </template>

          <template #cell-id="{ row }">
            <span class="text-gray-400 dark:text-dark-400">
              {{ shortId(assistantFromRow(row).id) }}
            </span>
          </template>

          <template #cell-actions="{ row }">
            <ActionMenu :items="assistantActions(assistantFromRow(row))" />
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
          :disabled="loading"
          @update:page="pagination.setPage"
          @update:page-size="pagination.setPageSize"
        />
      </template>
    </TablePageLayout>
  </section>
</template>

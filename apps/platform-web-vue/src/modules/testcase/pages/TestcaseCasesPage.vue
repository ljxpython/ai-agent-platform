<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseSelect from '@/components/base/BaseSelect.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import TablePageLayout from '@/components/layout/TablePageLayout.vue'
import { usePagination } from '@/composables/usePagination'
import { useVisibleFilterSettings } from '@/composables/useVisibleFilterSettings'
import ActionMenu from '@/components/platform/ActionMenu.vue'
import DataTable from '@/components/platform/DataTable.vue'
import EmptyState from '@/components/platform/EmptyState.vue'
import FilterSettingsMenu from '@/components/platform/FilterSettingsMenu.vue'
import FilterToolbar from '@/components/platform/FilterToolbar.vue'
import PaginationBar from '@/components/platform/PaginationBar.vue'
import SearchInput from '@/components/platform/SearchInput.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import StatusPill from '@/components/platform/StatusPill.vue'
import TestcaseOverviewStrip from '@/components/platform/TestcaseOverviewStrip.vue'
import TestcaseWorkspaceNav from '@/components/platform/TestcaseWorkspaceNav.vue'
import type { ActionMenuItem, DataTableColumn } from '@/components/platform/data-table'
import type { FilterSettingItem } from '@/components/platform/filter-settings'
import { getTestcaseOverview, getTestcaseRole, listTestcaseBatches, listTestcaseCases } from '@/services/testcase/testcase.service'
import { useUiStore } from '@/stores/ui'
import { useWorkspaceStore } from '@/stores/workspace'
import type { TestcaseBatchSummary, TestcaseCase, TestcaseOverview, TestcaseRole } from '@/types/management'
import { copyText } from '@/utils/clipboard'
import { formatDateTime, shortId } from '@/utils/format'

function getStatusTone(status: string): 'neutral' | 'success' | 'warning' | 'danger' {
  if (status === 'active') {
    return 'success'
  }
  if (status === 'draft') {
    return 'warning'
  }
  if (status === 'disabled' || status === 'archived') {
    return 'neutral'
  }
  return 'danger'
}

function getPriorityTone(priority: string): 'neutral' | 'success' | 'warning' | 'danger' {
  const normalized = priority.trim().toLowerCase()
  if (normalized === 'p0' || normalized === 'high' || normalized === 'critical') {
    return 'danger'
  }
  if (normalized === 'p1' || normalized === 'medium') {
    return 'warning'
  }
  if (normalized === 'p2' || normalized === 'low') {
    return 'success'
  }
  return 'neutral'
}

const workspaceStore = useWorkspaceStore()
const uiStore = useUiStore()

const overview = ref<TestcaseOverview | null>(null)
const batches = ref<TestcaseBatchSummary[]>([])
const role = ref<TestcaseRole | null>(null)
const items = ref<TestcaseCase[]>([])
const loading = ref(false)
const error = ref('')
const searchInput = ref('')
const batchInput = ref('')
const statusInput = ref('')
const query = ref('')
const batchFilter = ref('')
const statusFilter = ref('')
const caseRows = computed(() => items.value as unknown as Record<string, unknown>[])
const pagination = usePagination({
  initialPageSize: 20,
  storageKey: 'pw:testcase-cases:page-size'
})
const filterItems: FilterSettingItem[] = [
  { key: 'batch', label: '批次' },
  { key: 'status', label: '状态' }
]
const { visibleFilterKeys, visibleFilterSet, setVisibleFilterKeys } = useVisibleFilterSettings(
  filterItems,
  'pw:testcase-cases:filters'
)
const columns = computed<DataTableColumn[]>(() => [
  {
    key: 'title',
    label: '标题',
    sortable: true,
    alwaysVisible: true,
    sortValue: (row) => row.title || ''
  },
  {
    key: 'module_name',
    label: '模块',
    sortable: true,
    sortValue: (row) => row.module_name || ''
  },
  {
    key: 'priority',
    label: '优先级',
    sortable: true,
    sortValue: (row) => row.priority || ''
  },
  {
    key: 'status',
    label: '状态',
    sortable: true,
    sortValue: (row) => row.status || ''
  },
  {
    key: 'batch_id',
    label: '批次',
    sortable: true,
    defaultHidden: true,
    sortValue: (row) => row.batch_id || ''
  },
  {
    key: 'updated_at',
    label: '更新时间',
    sortable: true,
    sortValue: (row) => row.updated_at || ''
  }
])

function testcaseCaseFromRow(row: Record<string, unknown>) {
  return row as TestcaseCase
}

async function loadMeta(projectId: string) {
  const [overviewPayload, batchPayload, rolePayload] = await Promise.all([
    getTestcaseOverview(projectId),
    listTestcaseBatches(projectId, { limit: 100, offset: 0 }),
    getTestcaseRole(projectId)
  ])
  overview.value = overviewPayload
  batches.value = batchPayload.items
  role.value = rolePayload
}

async function loadCases() {
  const projectId = workspaceStore.currentProjectId
  if (!projectId) {
    overview.value = null
    batches.value = []
    role.value = null
    items.value = []
    pagination.setTotal(0)
    error.value = ''
    return
  }

  loading.value = true
  error.value = ''

  try {
    await loadMeta(projectId)
    const payload = await listTestcaseCases(projectId, {
      batch_id: batchFilter.value || undefined,
      status: statusFilter.value || undefined,
      query: query.value || undefined,
      limit: pagination.pageSize.value,
      offset: pagination.offset.value
    })
    items.value = payload.items
    pagination.setTotal(payload.total)
  } catch (loadError) {
    items.value = []
    pagination.setTotal(0)
    error.value = loadError instanceof Error ? loadError.message : '测试用例列表加载失败'
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  query.value = searchInput.value.trim()
  batchFilter.value = batchInput.value
  statusFilter.value = statusInput.value
  if (pagination.page.value === 1) {
    void loadCases()
    return
  }

  pagination.resetPage()
}

function resetFilters() {
  searchInput.value = ''
  batchInput.value = ''
  statusInput.value = ''
  query.value = ''
  batchFilter.value = ''
  statusFilter.value = ''
  if (pagination.page.value === 1) {
    void loadCases()
    return
  }

  pagination.resetPage()
}

function updateVisibleFilters(nextKeys: string[]) {
  const previous = new Set(visibleFilterKeys.value)
  setVisibleFilterKeys(nextKeys)

  let shouldReload = false

  if (previous.has('batch') && !visibleFilterSet.value.has('batch')) {
    batchInput.value = ''
    batchFilter.value = ''
    shouldReload = true
  }

  if (previous.has('status') && !visibleFilterSet.value.has('status')) {
    statusInput.value = ''
    statusFilter.value = ''
    shouldReload = true
  }

  if (shouldReload) {
    if (pagination.page.value === 1) {
      void loadCases()
    } else {
      pagination.resetPage()
    }
  }
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

function caseActions(item: TestcaseCase): ActionMenuItem[] {
  return [
    {
      key: 'copy-case-id',
      label: item.case_id ? '复制 Case ID' : '缺少 Case ID',
      icon: 'copy',
      disabled: !item.case_id,
      onSelect: () => handleCopyValue('Case ID', item.case_id || '')
    },
    {
      key: 'copy-batch-id',
      label: item.batch_id ? '复制批次 ID' : '未归属批次',
      icon: 'copy',
      disabled: !item.batch_id,
      onSelect: () => handleCopyValue('批次 ID', item.batch_id || '')
    },
    {
      key: 'detail',
      label: '用例详情待迁移',
      icon: 'eye',
      onSelect: () => handlePendingAction(`用例 ${item.title} 的详情页仍在迁移队列中。`)
    }
  ]
}

watch([() => pagination.page.value, () => pagination.pageSize.value], () => {
  void loadCases()
})

watch(
  () => workspaceStore.currentProjectId,
  () => {
    if (pagination.page.value !== 1) {
      pagination.resetPage()
      return
    }

    void loadCases()
  },
  { immediate: true }
)
</script>

<template>
  <section class="pw-page-shell">
    <TestcaseWorkspaceNav />

    <PageHeader
      eyebrow="Testcase"
      title="用例列表"
      description="查看 `test_case_service` 正式保存的测试用例，先把批次、状态、搜索和详情查看迁过来。"
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          @click="loadCases"
        >
          刷新
        </BaseButton>
      </template>
    </PageHeader>

    <TestcaseOverviewStrip :overview="overview" />

    <StateBanner
      v-if="error"
      title="测试用例列表加载失败"
      :description="error"
      variant="danger"
    />

    <EmptyState
      v-if="!workspaceStore.currentProject"
      icon="project"
      title="请先选择项目"
      description="没有项目上下文，没法读取 testcase 数据。"
    />

    <TablePageLayout v-else>
      <template #filters>
        <FilterToolbar>
          <div class="flex flex-wrap items-center gap-3">
            <div class="min-w-0 flex-1 basis-full sm:min-w-[260px]">
              <SearchInput
                v-model="searchInput"
                placeholder="按标题、模块、描述、case_id 搜索"
              />
            </div>

            <div
              v-if="visibleFilterSet.has('batch')"
              class="w-full sm:w-[240px]"
            >
              <BaseSelect v-model="batchInput">
                <option value="">
                  全部批次
                </option>
                <option
                  v-for="item in batches"
                  :key="item.batch_id"
                  :value="item.batch_id"
                >
                  {{ item.batch_id }}
                </option>
              </BaseSelect>
            </div>

            <div
              v-if="visibleFilterSet.has('status')"
              class="w-full sm:w-[180px]"
            >
              <BaseSelect v-model="statusInput">
                <option value="">
                  全部状态
                </option>
                <option value="active">
                  active
                </option>
                <option value="draft">
                  draft
                </option>
                <option value="disabled">
                  disabled
                </option>
                <option value="archived">
                  archived
                </option>
              </BaseSelect>
            </div>

            <div class="flex w-full flex-wrap items-center justify-end gap-2 xl:ml-auto xl:w-auto xl:flex-nowrap">
              <FilterSettingsMenu
                :items="filterItems"
                :model-value="visibleFilterKeys"
                @update:model-value="updateVisibleFilters"
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
          </div>
        </FilterToolbar>
      </template>

      <template #table>
        <DataTable
          :columns="columns"
          :rows="caseRows"
          :loading="loading"
          row-key="id"
          sort-storage-key="pw:testcase-cases:sort"
          column-storage-key="pw:testcase-cases:columns"
          empty-title="当前没有正式测试用例"
          :empty-description="
            role?.can_write_testcase
              ? '当前项目下还没有保存的测试用例，后面会继续补创建、编辑和详情能力。'
              : '当前项目下没有保存的测试用例，且你当前是只读角色。'
          "
          empty-icon="testcase"
        >
          <template #cell-title="{ row }">
            <div class="font-semibold text-gray-900 dark:text-white">
              {{ testcaseCaseFromRow(row).title }}
            </div>
            <div class="mt-1 text-xs text-gray-400 dark:text-dark-400">
              {{ testcaseCaseFromRow(row).case_id || shortId(testcaseCaseFromRow(row).id) }} · 来源文档 {{ testcaseCaseFromRow(row).source_document_ids.length }}
            </div>
          </template>

          <template #cell-module_name="{ row }">
            <span class="text-gray-500 dark:text-dark-300">
              {{ testcaseCaseFromRow(row).module_name || '--' }}
            </span>
          </template>

          <template #cell-priority="{ row }">
            <StatusPill :tone="getPriorityTone(testcaseCaseFromRow(row).priority || '')">
              {{ testcaseCaseFromRow(row).priority || '--' }}
            </StatusPill>
          </template>

          <template #cell-status="{ row }">
            <StatusPill :tone="getStatusTone(testcaseCaseFromRow(row).status)">
              {{ testcaseCaseFromRow(row).status }}
            </StatusPill>
          </template>

          <template #cell-batch_id="{ row }">
            <span class="text-gray-500 dark:text-dark-300">
              {{ testcaseCaseFromRow(row).batch_id || '--' }}
            </span>
          </template>

          <template #cell-updated_at="{ row }">
            <span class="text-gray-500 dark:text-dark-300">
              {{ formatDateTime(testcaseCaseFromRow(row).updated_at) }}
            </span>
          </template>

          <template #cell-actions="{ row }">
            <ActionMenu :items="caseActions(testcaseCaseFromRow(row))" />
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

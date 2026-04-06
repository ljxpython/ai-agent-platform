<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseDialog from '@/components/base/BaseDialog.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseSelect from '@/components/base/BaseSelect.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import TablePageLayout from '@/components/layout/TablePageLayout.vue'
import { usePagination } from '@/composables/usePagination'
import ActionMenu from '@/components/platform/ActionMenu.vue'
import DataTable from '@/components/platform/DataTable.vue'
import FilterToolbar from '@/components/platform/FilterToolbar.vue'
import MetricCard from '@/components/platform/MetricCard.vue'
import PaginationBar from '@/components/platform/PaginationBar.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import StatusPill from '@/components/platform/StatusPill.vue'
import type { ActionMenuItem, DataTableColumn } from '@/components/platform/data-table'
import {
  cancelOperation,
  downloadOperationArtifact,
  getOperationDetail,
  listOperations
} from '@/services/operations/operations.service'
import { resolvePlatformClientScope } from '@/services/platform/control-plane'
import { useUiStore } from '@/stores/ui'
import { useWorkspaceStore } from '@/stores/workspace'
import type { ManagementOperation, OperationStatus } from '@/types/management'
import { downloadBlob } from '@/utils/browser-download'
import { formatDateTime, shortId } from '@/utils/format'

const router = useRouter()
const workspaceStore = useWorkspaceStore()
const uiStore = useUiStore()
const pagination = usePagination({
  initialPageSize: 20,
  storageKey: 'pw:operations:page-size'
})

const scope = ref<'project' | 'global'>('project')
const kindInput = ref('')
const statusInput = ref<'' | OperationStatus>('')
const requestedByInput = ref('')

const kind = ref('')
const status = ref<OperationStatus | undefined>(undefined)
const requestedBy = ref('')

const loading = ref(false)
const cancellingId = ref('')
const error = ref('')
const notice = ref('')
const items = ref<ManagementOperation[]>([])

const detailDialogOpen = ref(false)
const detailLoading = ref(false)
const selectedOperation = ref<ManagementOperation | null>(null)

const operationsUseRuntimeApi = computed(() => resolvePlatformClientScope('operations') === 'v2')
const activeProjectId = computed(() =>
  operationsUseRuntimeApi.value ? workspaceStore.runtimeProjectId : workspaceStore.currentProjectId
)
const currentProject = computed(() =>
  operationsUseRuntimeApi.value ? workspaceStore.runtimeProject : workspaceStore.currentProject
)

const runningCount = computed(() =>
  items.value.filter((item) => item.status === 'submitted' || item.status === 'running').length
)
const failedCount = computed(() => items.value.filter((item) => item.status === 'failed').length)
const succeededCount = computed(() => items.value.filter((item) => item.status === 'succeeded').length)

const stats = computed(() => [
  {
    label: '当前范围',
    value: scope.value === 'project' ? currentProject.value?.name || '当前项目' : 'Global',
    hint: scope.value === 'project' ? '只看当前项目相关操作' : '跨项目统一操作视图',
    icon: 'project',
    tone: 'primary'
  },
  {
    label: '活跃任务',
    value: runningCount.value,
    hint: 'submitted / running 状态的操作',
    icon: 'activity',
    tone: runningCount.value > 0 ? 'warning' : 'success'
  },
  {
    label: '失败任务',
    value: failedCount.value,
    hint: '当前页可见的 failed 操作数量',
    icon: 'alert',
    tone: failedCount.value > 0 ? 'danger' : 'success'
  },
  {
    label: '已完成',
    value: succeededCount.value,
    hint: `当前结果集总数 ${pagination.total.value}`,
    icon: 'check',
    tone: 'success'
  }
])

const rows = computed(() => items.value as unknown as Record<string, unknown>[])

const columns = computed<DataTableColumn[]>(() => [
  {
    key: 'created_at',
    label: '提交时间',
    sortable: true,
    alwaysVisible: true,
    sortValue: (row) => row.created_at || ''
  },
  {
    key: 'kind',
    label: 'Kind',
    sortable: true,
    sortValue: (row) => row.kind || ''
  },
  {
    key: 'status',
    label: '状态',
    sortable: true,
    sortValue: (row) => row.status || ''
  },
  {
    key: 'project_id',
    label: '项目 / 操作人',
    sortable: true,
    sortValue: (row) => `${row.project_id || ''}:${row.requested_by || ''}`
  },
  {
    key: 'updated_at',
    label: '更新时间',
    sortable: true,
    sortValue: (row) => row.updated_at || ''
  }
])

function isTerminal(statusValue: OperationStatus) {
  return statusValue === 'succeeded' || statusValue === 'failed' || statusValue === 'cancelled'
}

function statusTone(statusValue: OperationStatus): 'neutral' | 'success' | 'warning' | 'danger' {
  if (statusValue === 'succeeded') {
    return 'success'
  }
  if (statusValue === 'failed' || statusValue === 'cancelled') {
    return 'danger'
  }
  if (statusValue === 'running' || statusValue === 'submitted') {
    return 'warning'
  }
  return 'neutral'
}

function operationFromRow(row: Record<string, unknown>) {
  return row as ManagementOperation
}

function formatJson(value: Record<string, unknown> | null | undefined) {
  if (!value || Object.keys(value).length === 0) {
    return ''
  }

  return JSON.stringify(value, null, 2)
}

function inferResourceRoute(operation: ManagementOperation) {
  if (operation.kind === 'runtime.models.refresh') {
    return '/workspace/runtime/models'
  }
  if (operation.kind === 'runtime.tools.refresh') {
    return '/workspace/runtime/tools'
  }
  if (operation.kind === 'runtime.graphs.refresh') {
    return '/workspace/graphs'
  }
  if (operation.kind === 'assistant.resync') {
    const assistantId = String(operation.result_payload.id || operation.input_payload.assistant_id || '').trim()
    return assistantId ? `/workspace/assistants/${encodeURIComponent(assistantId)}` : '/workspace/assistants'
  }
  if (operation.kind === 'testcase.documents.export') {
    return '/workspace/testcase/documents'
  }
  if (operation.kind === 'testcase.cases.export') {
    return '/workspace/testcase/cases'
  }
  return ''
}

function hasArtifact(operation: ManagementOperation | null) {
  if (!operation) {
    return false
  }
  const artifact = operation.result_payload?._artifact
  return Boolean(artifact && typeof artifact === 'object')
}

async function loadOperations(options?: { silent?: boolean }) {
  if (!options?.silent) {
    loading.value = true
  }
  error.value = ''

  try {
    const payload = await listOperations({
      projectId: scope.value === 'project' ? activeProjectId.value || undefined : undefined,
      kind: kind.value || undefined,
      status: status.value,
      requestedBy: requestedBy.value || undefined,
      limit: pagination.pageSize.value,
      offset: pagination.offset.value
    })
    items.value = payload.items
    pagination.setTotal(payload.total)

    if (selectedOperation.value) {
      const current = payload.items.find((item) => item.id === selectedOperation.value?.id)
      if (current) {
        selectedOperation.value = current
      }
    }
  } catch (loadError) {
    items.value = []
    pagination.setTotal(0)
    error.value = loadError instanceof Error ? loadError.message : '操作中心加载失败'
  } finally {
    if (!options?.silent) {
      loading.value = false
    }
  }
}

function applyFilters() {
  kind.value = kindInput.value.trim()
  status.value = statusInput.value || undefined
  requestedBy.value = requestedByInput.value.trim()
  if (pagination.page.value === 1) {
    void loadOperations()
    return
  }
  pagination.resetPage()
}

function resetFilters() {
  kindInput.value = ''
  statusInput.value = ''
  requestedByInput.value = ''
  kind.value = ''
  status.value = undefined
  requestedBy.value = ''
  if (pagination.page.value === 1) {
    void loadOperations()
    return
  }
  pagination.resetPage()
}

async function openOperationDetail(operationId: string) {
  detailDialogOpen.value = true
  detailLoading.value = true
  try {
    selectedOperation.value = await getOperationDetail(operationId)
  } catch (detailError) {
    selectedOperation.value = null
    error.value = detailError instanceof Error ? detailError.message : '操作详情加载失败'
  } finally {
    detailLoading.value = false
  }
}

function closeOperationDetail() {
  detailDialogOpen.value = false
  selectedOperation.value = null
}

async function handleCancel(operation: ManagementOperation) {
  cancellingId.value = operation.id
  error.value = ''
  notice.value = ''

  try {
    const updated = await cancelOperation(operation.id)
    notice.value = `操作 ${shortId(updated.id)} 已取消`
    uiStore.pushToast({
      type: 'success',
      title: '操作已取消',
      message: notice.value
    })
    if (selectedOperation.value?.id === updated.id) {
      selectedOperation.value = updated
    }
    await loadOperations()
  } catch (cancelError) {
    error.value = cancelError instanceof Error ? cancelError.message : '取消操作失败'
  } finally {
    cancellingId.value = ''
  }
}

async function handleDownloadArtifact(operation: ManagementOperation) {
  try {
    const download = await downloadOperationArtifact(operation.id)
    downloadBlob(
      download.blob,
      download.filename ||
        `operation-${operation.kind}-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}`
    )
    uiStore.pushToast({
      type: 'success',
      title: '结果已下载',
      message: download.filename || shortId(operation.id)
    })
  } catch (downloadError) {
    error.value = downloadError instanceof Error ? downloadError.message : '下载操作产物失败'
  }
}

function jumpToAudit(operation: ManagementOperation) {
  void router.push({
    path: '/workspace/audit',
    query: {
      targetType: 'operation',
      targetId: operation.id
    }
  })
}

function operationActions(operation: ManagementOperation): ActionMenuItem[] {
  const actions: ActionMenuItem[] = [
    {
      key: 'detail',
      label: '查看详情',
      icon: 'eye',
      onSelect: () => void openOperationDetail(operation.id)
    },
    {
      key: 'audit',
      label: '查看审计',
      icon: 'audit',
      onSelect: () => jumpToAudit(operation)
    }
  ]

  if (hasArtifact(operation)) {
    actions.splice(1, 0, {
      key: 'download-artifact',
      label: '下载结果',
      icon: 'download',
      onSelect: () => void handleDownloadArtifact(operation)
    })
  }

  if (!isTerminal(operation.status)) {
    actions.push({
      key: 'cancel',
      label: cancellingId.value === operation.id ? '取消中...' : '取消操作',
      icon: 'x',
      disabled: cancellingId.value === operation.id,
      onSelect: () => void handleCancel(operation)
    })
  }

  return actions
}

let refreshTimer: number | null = null

function startRefreshTimer() {
  if (typeof window === 'undefined' || refreshTimer !== null) {
    return
  }

  refreshTimer = window.setInterval(() => {
    const shouldRefreshList = items.value.some((item) => !isTerminal(item.status))
    const shouldRefreshDetail =
      detailDialogOpen.value && selectedOperation.value && !isTerminal(selectedOperation.value.status)
    if (shouldRefreshList || shouldRefreshDetail) {
      void loadOperations({ silent: true })
      if (shouldRefreshDetail && selectedOperation.value) {
        void openOperationDetail(selectedOperation.value.id)
      }
    }
  }, 3000)
}

function stopRefreshTimer() {
  if (refreshTimer !== null && typeof window !== 'undefined') {
    window.clearInterval(refreshTimer)
    refreshTimer = null
  }
}

watch([() => pagination.page.value, () => pagination.pageSize.value], () => {
  void loadOperations()
})

watch(activeProjectId, (projectId) => {
  if (!projectId && scope.value === 'project') {
    scope.value = 'global'
    return
  }

  if (scope.value === 'project') {
    void loadOperations()
  }
})

watch(scope, (nextScope, previousScope) => {
  if (nextScope === previousScope) {
    return
  }

  if (pagination.page.value === 1) {
    void loadOperations()
    return
  }
  pagination.resetPage()
})

onMounted(() => {
  if (!activeProjectId.value) {
    scope.value = 'global'
  }
  void loadOperations()
  startRefreshTimer()
})

onBeforeUnmount(() => {
  stopRefreshTimer()
})
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Governance"
      title="Operations Center"
      description="所有异步或长耗时动作最终都应该回流到这里。现在 runtime refresh、assistant resync 和 testcase export 都已经统一接到同一条治理链路里。"
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          :disabled="loading"
          @click="loadOperations"
        >
          <BaseIcon
            name="refresh"
            size="sm"
          />
          刷新列表
        </BaseButton>
      </template>
    </PageHeader>

    <StateBanner
      v-if="error"
      title="操作中心加载失败"
      :description="error"
      variant="danger"
    />
    <StateBanner
      v-else-if="notice"
      title="操作状态已更新"
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
          <div class="grid gap-4 xl:grid-cols-[180px_minmax(0,1fr)_180px_180px_auto_auto]">
            <BaseSelect v-model="scope">
              <option
                v-if="activeProjectId"
                value="project"
              >
                当前项目
              </option>
              <option value="global">
                全局
              </option>
            </BaseSelect>
            <BaseInput
              v-model="kindInput"
              placeholder="按 kind 筛选"
            />
            <BaseSelect v-model="statusInput">
              <option value="">
                全部状态
              </option>
              <option value="submitted">
                submitted
              </option>
              <option value="running">
                running
              </option>
              <option value="succeeded">
                succeeded
              </option>
              <option value="failed">
                failed
              </option>
              <option value="cancelled">
                cancelled
              </option>
            </BaseSelect>
            <BaseInput
              v-model="requestedByInput"
              placeholder="按提交人筛选"
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
          :rows="rows"
          :loading="loading"
          row-key="id"
          sort-storage-key="pw:operations:sort"
          column-storage-key="pw:operations:columns"
          empty-title="没有操作记录"
          empty-description="当前筛选范围下还没有操作记录。可以先去 Runtime、Assistants 或 Testcase 触发一次真实异步动作。"
          empty-icon="activity"
        >
          <template #cell-created_at="{ row }">
            <span class="text-sm text-gray-500 dark:text-dark-300">
              {{ formatDateTime(operationFromRow(row).created_at) }}
            </span>
          </template>

          <template #cell-kind="{ row }">
            <div class="min-w-0">
              <div class="truncate font-semibold text-gray-900 dark:text-white">
                {{ operationFromRow(row).kind }}
              </div>
              <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                {{ shortId(operationFromRow(row).id) }}
              </div>
            </div>
          </template>

          <template #cell-status="{ row }">
            <StatusPill :tone="statusTone(operationFromRow(row).status)">
              {{ operationFromRow(row).status }}
            </StatusPill>
          </template>

          <template #cell-project_id="{ row }">
            <div class="min-w-0">
              <div class="text-sm font-medium text-gray-900 dark:text-white">
                {{ shortId(operationFromRow(row).project_id) }}
              </div>
              <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                by {{ operationFromRow(row).requested_by || '--' }}
              </div>
            </div>
          </template>

          <template #cell-updated_at="{ row }">
            <span class="text-sm text-gray-500 dark:text-dark-300">
              {{ formatDateTime(operationFromRow(row).updated_at) }}
            </span>
          </template>

          <template #cell-actions="{ row }">
            <ActionMenu :items="operationActions(operationFromRow(row))" />
          </template>
        </DataTable>
      </template>

      <template
        v-if="pagination.total.value > 0"
        #footer
      >
        <PaginationBar
          :page="pagination.page.value"
          :page-size="pagination.pageSize.value"
          :total="pagination.total.value"
          :disabled="loading"
          @update:page="pagination.setPage"
          @update:page-size="pagination.setPageSize"
        />
      </template>
    </TablePageLayout>

    <BaseDialog
      :show="detailDialogOpen"
      :title="selectedOperation ? `操作详情 · ${shortId(selectedOperation.id)}` : '操作详情'"
      width="full"
      @close="closeOperationDetail"
    >
      <div
        v-if="detailLoading"
        class="rounded-2xl border border-dashed border-gray-200 px-6 py-12 text-center text-sm text-gray-500 dark:border-dark-700 dark:text-dark-300"
      >
        正在加载操作详情...
      </div>

      <div
        v-else-if="selectedOperation"
        class="space-y-5"
      >
        <div class="grid gap-4 lg:grid-cols-2">
          <div class="rounded-2xl border border-gray-100 bg-gray-50/80 p-4 dark:border-dark-800 dark:bg-dark-900/80">
            <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
              基础信息
            </div>
            <div class="mt-3 space-y-2 text-sm text-gray-600 dark:text-dark-300">
              <div><span class="font-semibold text-gray-900 dark:text-white">Kind:</span> {{ selectedOperation.kind }}</div>
              <div><span class="font-semibold text-gray-900 dark:text-white">Status:</span> {{ selectedOperation.status }}</div>
              <div><span class="font-semibold text-gray-900 dark:text-white">Requested By:</span> {{ selectedOperation.requested_by }}</div>
              <div><span class="font-semibold text-gray-900 dark:text-white">Project:</span> {{ shortId(selectedOperation.project_id) }}</div>
              <div><span class="font-semibold text-gray-900 dark:text-white">Created:</span> {{ formatDateTime(selectedOperation.created_at) }}</div>
              <div><span class="font-semibold text-gray-900 dark:text-white">Updated:</span> {{ formatDateTime(selectedOperation.updated_at) }}</div>
              <div><span class="font-semibold text-gray-900 dark:text-white">Started:</span> {{ formatDateTime(selectedOperation.started_at) }}</div>
              <div><span class="font-semibold text-gray-900 dark:text-white">Finished:</span> {{ formatDateTime(selectedOperation.finished_at) }}</div>
            </div>
          </div>

          <div class="rounded-2xl border border-gray-100 bg-gray-50/80 p-4 dark:border-dark-800 dark:bg-dark-900/80">
            <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
              快捷动作
            </div>
            <div class="mt-4 flex flex-wrap gap-3">
              <BaseButton
                variant="secondary"
                @click="jumpToAudit(selectedOperation)"
              >
                <BaseIcon
                  name="audit"
                  size="sm"
                />
                查看审计
              </BaseButton>
              <BaseButton
                v-if="hasArtifact(selectedOperation)"
                variant="secondary"
                @click="handleDownloadArtifact(selectedOperation)"
              >
                <BaseIcon
                  name="download"
                  size="sm"
                />
                下载结果
              </BaseButton>
              <router-link
                v-if="inferResourceRoute(selectedOperation)"
                class="pw-btn pw-btn-ghost"
                :to="inferResourceRoute(selectedOperation)"
              >
                <BaseIcon
                  name="overview"
                  size="sm"
                />
                打开相关页面
              </router-link>
              <BaseButton
                v-if="!isTerminal(selectedOperation.status)"
                variant="danger"
                :disabled="cancellingId === selectedOperation.id"
                @click="handleCancel(selectedOperation)"
              >
                <BaseIcon
                  name="x"
                  size="sm"
                />
                {{ cancellingId === selectedOperation.id ? '取消中...' : '取消操作' }}
              </BaseButton>
            </div>
          </div>
        </div>

        <div
          v-if="formatJson(selectedOperation.input_payload)"
          class="rounded-2xl border border-gray-100 bg-white p-4 dark:border-dark-800 dark:bg-dark-950"
        >
          <div class="text-sm font-semibold text-gray-900 dark:text-white">
            输入载荷
          </div>
          <pre class="mt-3 overflow-x-auto rounded-2xl bg-gray-950 px-4 py-4 text-xs leading-6 text-gray-100">{{ formatJson(selectedOperation.input_payload) }}</pre>
        </div>

        <div
          v-if="formatJson(selectedOperation.result_payload)"
          class="rounded-2xl border border-gray-100 bg-white p-4 dark:border-dark-800 dark:bg-dark-950"
        >
          <div class="text-sm font-semibold text-gray-900 dark:text-white">
            结果载荷
          </div>
          <pre class="mt-3 overflow-x-auto rounded-2xl bg-gray-950 px-4 py-4 text-xs leading-6 text-gray-100">{{ formatJson(selectedOperation.result_payload) }}</pre>
        </div>

        <div
          v-if="formatJson(selectedOperation.error_payload)"
          class="rounded-2xl border border-rose-100 bg-rose-50/80 p-4 dark:border-rose-900/30 dark:bg-rose-950/20"
        >
          <div class="text-sm font-semibold text-rose-700 dark:text-rose-300">
            错误载荷
          </div>
          <pre class="mt-3 overflow-x-auto rounded-2xl bg-gray-950 px-4 py-4 text-xs leading-6 text-gray-100">{{ formatJson(selectedOperation.error_payload) }}</pre>
        </div>

        <div
          v-if="formatJson(selectedOperation.metadata)"
          class="rounded-2xl border border-gray-100 bg-white p-4 dark:border-dark-800 dark:bg-dark-950"
        >
          <div class="text-sm font-semibold text-gray-900 dark:text-white">
            元数据
          </div>
          <pre class="mt-3 overflow-x-auto rounded-2xl bg-gray-950 px-4 py-4 text-xs leading-6 text-gray-100">{{ formatJson(selectedOperation.metadata) }}</pre>
        </div>
      </div>
    </BaseDialog>
  </section>
</template>

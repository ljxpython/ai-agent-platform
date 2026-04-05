<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
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
import SearchInput from '@/components/platform/SearchInput.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import StatusPill from '@/components/platform/StatusPill.vue'
import type { ActionMenuItem, DataTableColumn } from '@/components/platform/data-table'
import { listAudit } from '@/services/audit/audit.service'
import { useUiStore } from '@/stores/ui'
import { useWorkspaceStore } from '@/stores/workspace'
import type { ManagementAuditRow } from '@/types/management'
import { copyText } from '@/utils/clipboard'
import { formatDateTime, shortId } from '@/utils/format'

const workspaceStore = useWorkspaceStore()
const uiStore = useUiStore()

const scope = ref<'project' | 'global'>('project')
const actionInput = ref('')
const methodInput = ref('')
const statusCodeInput = ref('')
const action = ref('')
const method = ref('')
const statusCode = ref<number | null>(null)
const loading = ref(false)
const error = ref('')
const items = ref<ManagementAuditRow[]>([])
const auditRows = computed(() => items.value as unknown as Record<string, unknown>[])
const pagination = usePagination({
  initialPageSize: 20,
  storageKey: 'pw:audit:page-size'
})
const columns = computed<DataTableColumn[]>(() => [
  {
    key: 'created_at',
    label: '时间',
    sortable: true,
    alwaysVisible: true,
    sortValue: (row) => row.created_at
  },
  {
    key: 'action',
    label: 'Action',
    sortable: true,
    sortValue: (row) => row.action || ''
  },
  {
    key: 'request',
    label: '请求',
    sortable: true,
    sortValue: (row) => `${row.method} ${row.path}`
  },
  {
    key: 'status_code',
    label: '状态',
    sortable: true,
    sortValue: (row) => row.status_code
  },
  {
    key: 'user_id',
    label: '用户',
    sortable: true,
    defaultHidden: true,
    sortValue: (row) => row.user_id || ''
  },
  {
    key: 'request_id',
    label: 'Request ID',
    sortable: true,
    sortValue: (row) => row.request_id
  }
])

function auditRowFromTable(row: Record<string, unknown>) {
  return row as ManagementAuditRow
}

const currentProject = computed(() => workspaceStore.currentProject)
const errorCount = computed(() => items.value.filter((item) => item.status_code >= 400).length)
const stats = computed(() => [
  {
    label: '查看范围',
    value: scope.value === 'project' ? 'Project' : 'Global',
    hint: scope.value === 'project' ? '当前项目范围的审计日志' : '全局范围的管理审计日志',
    icon: 'audit',
    tone: 'primary'
  },
  {
    label: '当前项目',
    value: currentProject.value?.name || '无',
    hint: 'project scope 会自动绑定当前 workspace 项目',
    icon: 'project',
    tone: 'success'
  },
  {
    label: '可见日志',
    value: items.value.length,
    hint: `当前结果集总数 ${pagination.total.value}`,
    icon: 'overview',
    tone: 'warning'
  },
  {
    label: '异常请求',
    value: errorCount.value,
    hint: 'HTTP 状态码大于等于 400 的记录',
    icon: 'activity',
    tone: 'danger'
  }
])

function getStatusTone(statusCodeValue: number): 'success' | 'warning' | 'danger' {
  if (statusCodeValue >= 500) {
    return 'danger'
  }

  if (statusCodeValue >= 400) {
    return 'warning'
  }

  return 'success'
}

async function loadAuditRows() {
  loading.value = true
  error.value = ''

  try {
    const payload = await listAudit(scope.value === 'project' ? workspaceStore.currentProjectId || null : null, {
      limit: pagination.pageSize.value,
      offset: pagination.offset.value,
      action: action.value,
      method: method.value,
      statusCode: statusCode.value
    })

    items.value = payload.items
    pagination.setTotal(payload.total)
  } catch (loadError) {
    items.value = []
    pagination.setTotal(0)
    error.value = loadError instanceof Error ? loadError.message : '审计日志加载失败'
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  action.value = actionInput.value.trim()
  method.value = methodInput.value.trim()
  statusCode.value = statusCodeInput.value.trim() ? Number(statusCodeInput.value) : null
  if (pagination.page.value === 1) {
    void loadAuditRows()
    return
  }

  pagination.resetPage()
}

async function handleCopyValue(label: string, value: string | null | undefined) {
  const content = value?.trim() || ''
  const copied = content ? await copyText(content) : false

  uiStore.pushToast({
    type: copied ? 'success' : 'warning',
    title: copied ? `已复制${label}` : '复制失败',
    message: copied ? content : `${label} 当前不可复制`
  })
}

function auditActions(row: ManagementAuditRow): ActionMenuItem[] {
  return [
    {
      key: 'copy-request-id',
      label: '复制 Request ID',
      icon: 'copy',
      onSelect: () => handleCopyValue('Request ID', row.request_id)
    },
    {
      key: 'copy-path',
      label: '复制请求路径',
      icon: 'copy',
      onSelect: () => handleCopyValue('请求路径', row.path)
    },
    {
      key: 'copy-user-id',
      label: row.user_id ? '复制用户 ID' : '无用户 ID',
      icon: 'copy',
      disabled: !row.user_id,
      onSelect: () => handleCopyValue('用户 ID', row.user_id)
    }
  ]
}

watch(
  () => workspaceStore.currentProjectId,
  (projectId) => {
    if (!projectId) {
      scope.value = 'global'
      return
    }

    if (pagination.page.value === 1) {
      void loadAuditRows()
      return
    }

    pagination.resetPage()
  }
)

watch(scope, (nextScope, previousScope) => {
  if (nextScope === previousScope) {
    return
  }

  if (pagination.page.value === 1) {
    void loadAuditRows()
    return
  }

  pagination.resetPage()
})

watch([() => pagination.page.value, () => pagination.pageSize.value], () => {
  void loadAuditRows()
})

onMounted(() => {
  if (!workspaceStore.currentProjectId) {
    scope.value = 'global'
  }

  void loadAuditRows()
})
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Audit"
      title="审计日志"
      description="审计页负责把后台关键操作轨迹铺出来，先完成 project/global 两个范围和基础筛选，后续再补更深的详情追踪。"
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          @click="loadAuditRows"
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
      title="审计日志加载失败"
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

    <TablePageLayout>
      <template #filters>
        <FilterToolbar>
          <div class="grid gap-4 xl:grid-cols-[180px_minmax(0,1fr)_180px_180px_auto]">
            <BaseSelect v-model="scope">
              <option
                v-if="currentProject"
                value="project"
              >
                当前项目
              </option>
              <option value="global">
                全局
              </option>
            </BaseSelect>
            <SearchInput
              v-model="actionInput"
              icon="filter"
              placeholder="按 action 筛选"
            />
            <BaseSelect v-model="methodInput">
              <option value="">
                全部方法
              </option>
              <option value="GET">
                GET
              </option>
              <option value="POST">
                POST
              </option>
              <option value="PATCH">
                PATCH
              </option>
              <option value="DELETE">
                DELETE
              </option>
            </BaseSelect>
            <BaseInput
              v-model="statusCodeInput"
              placeholder="状态码"
            />
            <BaseButton @click="applyFilters">
              应用筛选
            </BaseButton>
          </div>
        </FilterToolbar>
      </template>

      <template #table>
        <DataTable
          :columns="columns"
          :rows="auditRows"
          :loading="loading"
          row-key="id"
          sort-storage-key="pw:audit:sort"
          column-storage-key="pw:audit:columns"
          empty-title="没有找到审计日志"
          empty-description="当前筛选范围下没有数据。等后续模块继续接进来之后，这里会更能体现系统的真实操作轨迹。"
          empty-icon="audit"
        >
          <template #cell-created_at="{ row }">
            <span class="text-gray-500 dark:text-dark-300">
              {{ formatDateTime(auditRowFromTable(row).created_at) }}
            </span>
          </template>

          <template #cell-action="{ row }">
            <div class="font-semibold text-gray-900 dark:text-white">
              {{ auditRowFromTable(row).action || 'unknown' }}
            </div>
            <div class="mt-1 text-sm text-gray-500 dark:text-dark-300">
              {{ auditRowFromTable(row).target_type || 'n/a' }} ·
              {{ shortId(auditRowFromTable(row).target_id) }}
            </div>
          </template>

          <template #cell-request="{ row }">
            <span class="text-gray-500 dark:text-dark-300">
              {{ auditRowFromTable(row).method }} · {{ auditRowFromTable(row).path }}
            </span>
          </template>

          <template #cell-status_code="{ row }">
            <StatusPill :tone="getStatusTone(auditRowFromTable(row).status_code)">
              {{ auditRowFromTable(row).status_code }}
            </StatusPill>
          </template>

          <template #cell-user_id="{ row }">
            <span class="text-gray-500 dark:text-dark-300">
              {{ shortId(auditRowFromTable(row).user_id) }}
            </span>
          </template>

          <template #cell-request_id="{ row }">
            <span class="text-gray-400 dark:text-dark-400">
              {{ shortId(auditRowFromTable(row).request_id) }}
            </span>
          </template>

          <template #cell-actions="{ row }">
            <ActionMenu :items="auditActions(auditRowFromTable(row))" />
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

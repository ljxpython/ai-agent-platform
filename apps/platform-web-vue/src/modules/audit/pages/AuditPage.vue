<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseSelect from '@/components/base/BaseSelect.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import TablePageLayout from '@/components/layout/TablePageLayout.vue'
import EmptyState from '@/components/platform/EmptyState.vue'
import FilterToolbar from '@/components/platform/FilterToolbar.vue'
import MetricCard from '@/components/platform/MetricCard.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import StatusPill from '@/components/platform/StatusPill.vue'
import { listAudit } from '@/services/audit/audit.service'
import { useWorkspaceStore } from '@/stores/workspace'
import type { ManagementAuditRow } from '@/types/management'
import { formatDateTime, shortId } from '@/utils/format'

const workspaceStore = useWorkspaceStore()

const scope = ref<'project' | 'global'>('project')
const actionInput = ref('')
const methodInput = ref('')
const statusCodeInput = ref('')
const action = ref('')
const method = ref('')
const statusCode = ref<number | null>(null)
const loading = ref(false)
const error = ref('')
const total = ref(0)
const items = ref<ManagementAuditRow[]>([])

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
    hint: `当前结果集总数 ${total.value}`,
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
      limit: 50,
      offset: 0,
      action: action.value,
      method: method.value,
      statusCode: statusCode.value
    })

    items.value = payload.items
    total.value = payload.total
  } catch (loadError) {
    items.value = []
    total.value = 0
    error.value = loadError instanceof Error ? loadError.message : '审计日志加载失败'
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  action.value = actionInput.value.trim()
  method.value = methodInput.value.trim()
  statusCode.value = statusCodeInput.value.trim() ? Number(statusCodeInput.value) : null
  void loadAuditRows()
}

watch(
  () => workspaceStore.currentProjectId,
  (projectId) => {
    if (!projectId) {
      scope.value = 'global'
    }
    void loadAuditRows()
  },
  { immediate: true }
)
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
            <div class="relative">
              <div class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400 dark:text-dark-400">
                <BaseIcon
                  name="filter"
                  size="sm"
                />
              </div>
              <BaseInput
                v-model="actionInput"
                class="pl-10"
                placeholder="按 action 筛选"
              />
            </div>
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
        <div
          v-if="loading"
          class="p-6 text-sm text-slate-500 dark:text-dark-300"
        >
          正在加载审计日志...
        </div>

        <div
          v-else-if="items.length"
          class="pw-table-wrapper"
        >
          <table class="pw-table">
            <thead>
              <tr>
                <th>时间</th>
                <th>Action</th>
                <th>请求</th>
                <th>状态</th>
                <th>用户</th>
                <th>Request ID</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in items"
                :key="row.id"
              >
                <td class="text-slate-500 dark:text-dark-300">
                  {{ formatDateTime(row.created_at) }}
                </td>
                <td>
                  <div class="font-semibold text-slate-900 dark:text-white">
                    {{ row.action || 'unknown' }}
                  </div>
                  <div class="mt-1 text-sm text-slate-500 dark:text-dark-300">
                    {{ row.target_type || 'n/a' }} · {{ shortId(row.target_id) }}
                  </div>
                </td>
                <td class="text-slate-500 dark:text-dark-300">
                  {{ row.method }} · {{ row.path }}
                </td>
                <td>
                  <StatusPill :tone="getStatusTone(row.status_code)">
                    {{ row.status_code }}
                  </StatusPill>
                </td>
                <td class="text-slate-500 dark:text-dark-300">
                  {{ shortId(row.user_id) }}
                </td>
                <td class="text-slate-400 dark:text-dark-400">
                  {{ shortId(row.request_id) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <EmptyState
          v-else
          icon="audit"
          title="没有找到审计日志"
          description="当前筛选范围下没有数据。等后续模块继续接进来之后，这里会更能体现系统的真实操作轨迹。"
        />
      </template>
    </TablePageLayout>
  </section>
</template>

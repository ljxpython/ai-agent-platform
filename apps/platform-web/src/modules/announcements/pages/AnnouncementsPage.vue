<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseDialog from '@/components/base/BaseDialog.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import BaseSelect from '@/components/base/BaseSelect.vue'
import ConfirmDialog from '@/components/base/ConfirmDialog.vue'
import { useAuthorization } from '@/composables/useAuthorization'
import { useWorkspaceProjectContext } from '@/composables/useWorkspaceProjectContext'
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
import {
  createAnnouncement,
  deleteAnnouncement,
  listAnnouncements,
  updateAnnouncement
} from '@/services/announcements/announcements.service'
import { useUiStore } from '@/stores/ui'
import type { ManagementAnnouncement } from '@/types/management'
import { formatDateTime } from '@/utils/format'

type AnnouncementStatus = 'draft' | 'published' | 'archived'
type AnnouncementScopeType = 'global' | 'project'
type AnnouncementTone = 'info' | 'warning' | 'success'

const uiStore = useUiStore()
const { activeProjectId, activeProject, activeProjects } = useWorkspaceProjectContext()
const authorization = useAuthorization()

const queryInput = ref('')
const statusInput = ref('')
const scopeTypeInput = ref('')
const query = ref('')
const status = ref('')
const scopeType = ref('')
const projectFilterId = ref('')
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const items = ref<ManagementAnnouncement[]>([])
const pagination = usePagination({
  initialPageSize: 20,
  storageKey: 'pw:announcements:page-size'
})

const showEditDialog = ref(false)
const showDeleteDialog = ref(false)
const editingAnnouncement = ref<ManagementAnnouncement | null>(null)
const deletingAnnouncement = ref<ManagementAnnouncement | null>(null)

const form = reactive({
  title: '',
  summary: '',
  body: '',
  tone: 'info' as AnnouncementTone,
  scopeType: 'project' as AnnouncementScopeType,
  scopeProjectId: '',
  status: 'published' as AnnouncementStatus,
  publishAt: '',
  expireAt: ''
})

const availableProjects = activeProjects
const announcementsRows = computed(() => items.value as unknown as Record<string, unknown>[])
const globalCount = computed(() => items.value.filter((item) => item.scope_type === 'global').length)
const projectCount = computed(() => items.value.filter((item) => item.scope_type === 'project').length)
const canManageGlobalAnnouncements = computed(() => authorization.can('platform.announcement.write'))
const canManageProjectAnnouncements = computed(() =>
  authorization.can('project.announcement.write', activeProjectId.value)
)
const canCreateAnnouncement = computed(() =>
  canManageGlobalAnnouncements.value || canManageProjectAnnouncements.value
)
const managementModeLabel = computed(() =>
  canManageGlobalAnnouncements.value ? '平台治理视角' : '项目治理视角'
)
const stats = computed(() => [
  {
    label: '当前结果',
    value: items.value.length,
    hint: query.value ? `搜索：${query.value}` : '当前筛选结果',
    icon: 'bell',
    tone: 'primary'
  },
  {
    label: '全局公告',
    value: globalCount.value,
    hint: 'scope_type = global',
    icon: 'overview',
    tone: 'success'
  },
  {
    label: '项目公告',
    value: projectCount.value,
    hint: 'scope_type = project',
    icon: 'folder',
    tone: 'warning'
  },
  {
    label: '当前项目',
    value: activeProject.value?.name || '未选择',
    hint: canManageGlobalAnnouncements.value ? '平台治理可切全局与项目范围' : '项目治理按当前项目工作',
    icon: 'project',
    tone: 'danger'
  }
])

const columns = computed<DataTableColumn[]>(() => [
  {
    key: 'title',
    label: '标题',
    sortable: true,
    alwaysVisible: true,
    sortValue: (row) => row.title || ''
  },
  {
    key: 'scope',
    label: '作用域',
    sortable: true,
    sortValue: (row) => row.scope_type || ''
  },
  {
    key: 'tone',
    label: '类型',
    sortable: true,
    sortValue: (row) => row.tone || ''
  },
  {
    key: 'status',
    label: '状态',
    sortable: true,
    sortValue: (row) => row.status || ''
  },
  {
    key: 'publish_at',
    label: '发布时间',
    sortable: true,
    sortValue: (row) => row.publish_at || ''
  },
  {
    key: 'expire_at',
    label: '截止时间',
    sortable: true,
    sortValue: (row) => row.expire_at || ''
  }
])

function announcementFromRow(row: Record<string, unknown>) {
  return row as ManagementAnnouncement
}

function statusTone(value: string): 'neutral' | 'success' | 'warning' {
  if (value === 'published') {
    return 'success'
  }
  if (value === 'draft') {
    return 'neutral'
  }
  return 'warning'
}

function scopeTone(value: string): 'info' | 'success' {
  return value === 'global' ? 'info' : 'success'
}

function formatDateTimeLocalInput(value?: string | null) {
  if (!value) {
    return ''
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return ''
  }

  const pad = (item: number) => String(item).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function parseDateTimeLocalInput(value: string) {
  return value.trim() ? new Date(value).toISOString() : null
}

function normalizeFormForScope() {
  if (form.scopeType === 'global') {
    form.scopeProjectId = ''
    return
  }

  if (!form.scopeProjectId) {
    form.scopeProjectId = activeProjectId.value
  }
}

async function loadAnnouncements() {
  loading.value = true
  error.value = ''

  try {
    if (!canManageGlobalAnnouncements.value && !projectFilterId.value) {
      items.value = []
      pagination.setTotal(0)
      return
    }

    const payload = await listAnnouncements({
      limit: pagination.pageSize.value,
      offset: pagination.offset.value,
      query: query.value,
      status: status.value || undefined,
      scopeType: scopeType.value || undefined,
      projectId: projectFilterId.value || undefined
    })

    items.value = payload.items
    pagination.setTotal(payload.total)
  } catch (loadError) {
    items.value = []
    pagination.setTotal(0)
    error.value =
      loadError instanceof Error ? loadError.message : '公告列表加载失败'
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  query.value = queryInput.value.trim()
  status.value = statusInput.value
  scopeType.value = scopeTypeInput.value
  if (pagination.page.value === 1) {
    void loadAnnouncements()
    return
  }

  pagination.resetPage()
}

function resetFilters() {
  queryInput.value = ''
  statusInput.value = ''
  scopeTypeInput.value = ''
  query.value = ''
  status.value = ''
  scopeType.value = ''
  projectFilterId.value = canManageGlobalAnnouncements.value ? '' : activeProjectId.value
  if (pagination.page.value === 1) {
    void loadAnnouncements()
    return
  }

  pagination.resetPage()
}

function resetForm() {
  editingAnnouncement.value = null
  form.title = ''
  form.summary = ''
  form.body = ''
  form.tone = 'info'
  form.scopeType = canManageGlobalAnnouncements.value ? 'global' : 'project'
  form.scopeProjectId = canManageGlobalAnnouncements.value ? '' : activeProjectId.value
  form.status = 'published'
  form.publishAt = ''
  form.expireAt = ''
}

function cancelDelete() {
  showDeleteDialog.value = false
  deletingAnnouncement.value = null
}

function openCreateDialog() {
  resetForm()
  normalizeFormForScope()
  showEditDialog.value = true
}

function openEditDialog(item: ManagementAnnouncement) {
  editingAnnouncement.value = item
  form.title = item.title
  form.summary = item.summary
  form.body = item.body
  form.tone = item.tone
  form.scopeType = item.scope_type === 'project' ? 'project' : 'global'
  form.scopeProjectId = item.scope_project_id || ''
  form.status = item.status as AnnouncementStatus
  form.publishAt = formatDateTimeLocalInput(item.publish_at)
  form.expireAt = formatDateTimeLocalInput(item.expire_at)
  normalizeFormForScope()
  showEditDialog.value = true
}

async function saveAnnouncement() {
  const targetProjectId = form.scopeProjectId.trim()
  if (form.scopeType === 'global' && !canManageGlobalAnnouncements.value) {
    error.value = '当前账号没有管理全局公告的权限'
    return
  }
  if (
    form.scopeType === 'project' &&
    !authorization.can('project.announcement.write', targetProjectId || activeProjectId.value)
  ) {
    error.value = '当前账号没有管理该项目公告的权限'
    return
  }
  if (!form.title.trim()) {
    error.value = '公告标题不能为空'
    return
  }
  if (!form.body.trim()) {
    error.value = '公告正文不能为空'
    return
  }
  if (form.scopeType === 'project' && !form.scopeProjectId.trim()) {
    error.value = '项目公告必须选择项目'
    return
  }

  saving.value = true
  error.value = ''

  const payload = {
    title: form.title.trim(),
    summary: form.summary.trim(),
    body: form.body.trim(),
    tone: form.tone,
    scope_type: form.scopeType,
    scope_project_id: form.scopeType === 'project' ? form.scopeProjectId.trim() : null,
    status: form.status,
    publish_at: parseDateTimeLocalInput(form.publishAt),
    expire_at: parseDateTimeLocalInput(form.expireAt)
  }

  try {
    if (editingAnnouncement.value) {
      await updateAnnouncement(editingAnnouncement.value.id, payload)
      uiStore.pushToast({
        type: 'success',
        title: '公告已更新',
        message: form.title.trim()
      })
    } else {
      await createAnnouncement(payload)
      uiStore.pushToast({
        type: 'success',
        title: '公告已创建',
        message: form.title.trim()
      })
    }

    showEditDialog.value = false
    resetForm()
    await loadAnnouncements()
  } catch (saveError) {
    error.value =
      saveError instanceof Error ? saveError.message : '公告保存失败'
  } finally {
    saving.value = false
  }
}

async function confirmDelete() {
  if (!deletingAnnouncement.value) {
    return
  }

  try {
    await deleteAnnouncement(deletingAnnouncement.value.id)
    uiStore.pushToast({
      type: 'success',
      title: '公告已删除',
      message: deletingAnnouncement.value.title
    })
    deletingAnnouncement.value = null
    await loadAnnouncements()
  } catch (deleteError) {
    error.value =
      deleteError instanceof Error ? deleteError.message : '公告删除失败'
  }
}

function actionsForRow(item: ManagementAnnouncement): ActionMenuItem[] {
  const canManageRow =
    item.scope_type === 'global'
      ? canManageGlobalAnnouncements.value
      : authorization.can('project.announcement.write', item.scope_project_id)

  return [
    {
      key: 'edit',
      label: '编辑公告',
      icon: 'eye',
      disabled: !canManageRow,
      onSelect: () => openEditDialog(item)
    },
    {
      key: 'delete',
      label: '删除公告',
      icon: 'x',
      danger: true,
      disabled: !canManageRow,
      onSelect: () => {
        deletingAnnouncement.value = item
        showDeleteDialog.value = true
      }
    }
  ]
}

watch(
  activeProjectId,
  (projectId) => {
    if (!canManageGlobalAnnouncements.value) {
      projectFilterId.value = projectId
      form.scopeType = 'project'
      form.scopeProjectId = projectId
    }

    void loadAnnouncements()
  },
  { immediate: true }
)

watch(
  () => form.scopeType,
  (scopeTypeValue) => {
    if (scopeTypeValue === 'global') {
      form.scopeProjectId = ''
      return
    }

    if (!form.scopeProjectId) {
      form.scopeProjectId = activeProjectId.value
    }
  }
)

watch([() => pagination.page.value, () => pagination.pageSize.value], () => {
  void loadAnnouncements()
})

onMounted(() => {
  if (!canManageGlobalAnnouncements.value) {
    projectFilterId.value = activeProjectId.value
  }
  void loadAnnouncements()
})
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Announcements"
      title="公告管理"
      description="这里负责真实公告的创建、编辑和删除。当前已接通 platform-api 的公告 feed、已读回写和后台 CRUD，前端不再只是静态壳层。"
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          @click="loadAnnouncements"
        >
          <BaseIcon
            name="refresh"
            size="sm"
          />
          刷新
        </BaseButton>
        <BaseButton
          :disabled="!canCreateAnnouncement"
          @click="openCreateDialog"
        >
          <BaseIcon
            name="bell"
            size="sm"
          />
          {{ canCreateAnnouncement ? '新建公告' : '当前账号只读' }}
        </BaseButton>
      </template>
    </PageHeader>

    <EmptyState
      v-if="!canManageGlobalAnnouncements && !activeProjectId"
      icon="project"
      title="请先选择项目"
      description="项目治理角色需要先选中当前项目，才能管理该项目范围内的公告。平台治理角色可直接查看全局公告。"
    />

    <template v-else>
      <StateBanner
        v-if="error"
        title="公告管理失败"
        :description="error"
        variant="danger"
      />

      <div class="grid gap-4 xl:grid-cols-4">
        <MetricCard
          v-for="itemStat in stats"
          :key="itemStat.label"
          :label="itemStat.label"
          :value="itemStat.value"
          :hint="itemStat.hint"
          :icon="itemStat.icon"
          :tone="itemStat.tone"
        />
      </div>

      <StateBanner
        title="当前管理模式"
        :description="`${managementModeLabel}。公告中心优先读取真实后端；只有接口不可用时，顶栏公告才会回退到本地公告数据。`"
        variant="info"
      />

      <TablePageLayout>
        <template #filters>
          <FilterToolbar>
            <div class="grid gap-4 xl:grid-cols-[minmax(0,1fr)_180px_180px_220px_auto_auto]">
              <SearchInput
                v-model="queryInput"
                placeholder="搜索公告标题或摘要"
              />
              <BaseSelect v-model="statusInput">
                <option value="">
                  全部状态
                </option>
                <option value="draft">
                  draft
                </option>
                <option value="published">
                  published
                </option>
                <option value="archived">
                  archived
                </option>
              </BaseSelect>
              <BaseSelect v-model="scopeTypeInput">
                <option value="">
                  全部范围
                </option>
                <option value="global">
                  global
                </option>
                <option value="project">
                  project
                </option>
              </BaseSelect>
              <BaseSelect
                v-model="projectFilterId"
                :disabled="!canManageGlobalAnnouncements"
              >
                <option value="">
                  {{ canManageGlobalAnnouncements ? '全部项目/全局' : '当前项目' }}
                </option>
                <option
                  v-for="project in availableProjects"
                  :key="project.id"
                  :value="project.id"
                >
                  {{ project.name }}
                </option>
              </BaseSelect>
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
            :rows="announcementsRows"
            :loading="loading"
            row-key="id"
            sort-storage-key="pw:announcements:sort"
            column-storage-key="pw:announcements:columns"
            empty-title="暂无公告"
            empty-description="当前筛选条件下没有公告记录。你可以直接新建一条公告来验证真实后端链路。"
            empty-icon="bell"
          >
            <template #cell-title="{ row }">
              <div class="min-w-0">
                <div class="truncate text-sm font-semibold text-gray-900 dark:text-white">
                  {{ announcementFromRow(row).title }}
                </div>
                <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                  {{ announcementFromRow(row).summary || '暂无摘要' }}
                </div>
              </div>
            </template>

            <template #cell-scope="{ row }">
              <StatusPill :tone="scopeTone(announcementFromRow(row).scope_type)">
                {{
                  announcementFromRow(row).scope_type === 'global'
                    ? 'global'
                    : availableProjects.find((item) => item.id === announcementFromRow(row).scope_project_id)?.name || 'project'
                }}
              </StatusPill>
            </template>

            <template #cell-tone="{ row }">
              <StatusPill :tone="announcementFromRow(row).tone">
                {{ announcementFromRow(row).tone }}
              </StatusPill>
            </template>

            <template #cell-status="{ row }">
              <StatusPill :tone="statusTone(announcementFromRow(row).status)">
                {{ announcementFromRow(row).status }}
              </StatusPill>
            </template>

            <template #cell-publish_at="{ row }">
              {{ formatDateTime(announcementFromRow(row).publish_at) }}
            </template>

            <template #cell-expire_at="{ row }">
              {{ formatDateTime(announcementFromRow(row).expire_at) }}
            </template>

            <template #cell-actions="{ row }">
              <ActionMenu :items="actionsForRow(announcementFromRow(row))" />
            </template>
          </DataTable>
        </template>

        <template #pagination>
          <PaginationBar
            :page="pagination.page.value"
            :page-size="pagination.pageSize.value"
            :total="pagination.total.value"
            @update:page="pagination.setPage"
            @update:page-size="pagination.setPageSize"
          />
        </template>
      </TablePageLayout>

      <BaseDialog
        :show="showEditDialog"
        :title="editingAnnouncement ? '编辑公告' : '新建公告'"
        width="wide"
        @close="showEditDialog = false"
      >
        <div class="space-y-4">
          <label class="block">
            <span class="pw-input-label">标题</span>
            <input
              v-model="form.title"
              class="pw-input"
            >
          </label>

          <label class="block">
            <span class="pw-input-label">摘要</span>
            <textarea
              v-model="form.summary"
              rows="3"
              class="pw-input min-h-[96px] resize-y"
            />
          </label>

          <label class="block">
            <span class="pw-input-label">正文</span>
            <textarea
              v-model="form.body"
              rows="8"
              class="pw-input min-h-[180px] resize-y"
            />
          </label>

          <div class="grid gap-4 md:grid-cols-2">
            <label class="block">
              <span class="pw-input-label">类型</span>
              <BaseSelect v-model="form.tone">
                <option value="info">
                  info
                </option>
                <option value="warning">
                  warning
                </option>
                <option value="success">
                  success
                </option>
              </BaseSelect>
            </label>

            <label class="block">
              <span class="pw-input-label">状态</span>
              <BaseSelect v-model="form.status">
                <option value="draft">
                  draft
                </option>
                <option value="published">
                  published
                </option>
                <option value="archived">
                  archived
                </option>
              </BaseSelect>
            </label>
          </div>

          <div class="grid gap-4 md:grid-cols-2">
            <label class="block">
              <span class="pw-input-label">范围</span>
              <BaseSelect
                v-model="form.scopeType"
                :disabled="!canManageGlobalAnnouncements"
              >
                <option
                  v-if="canManageGlobalAnnouncements"
                  value="global"
                >
                  global
                </option>
                <option value="project">
                  project
                </option>
              </BaseSelect>
            </label>

            <label class="block">
              <span class="pw-input-label">项目</span>
              <BaseSelect
                v-model="form.scopeProjectId"
                :disabled="form.scopeType !== 'project'"
              >
                <option value="">选择项目</option>
                <option
                  v-for="project in availableProjects"
                  :key="project.id"
                  :value="project.id"
                >
                  {{ project.name }}
                </option>
              </BaseSelect>
            </label>
          </div>

          <div class="grid gap-4 md:grid-cols-2">
            <label class="block">
              <span class="pw-input-label">发布时间</span>
              <input
                v-model="form.publishAt"
                type="datetime-local"
                class="pw-input"
              >
            </label>

            <label class="block">
              <span class="pw-input-label">截止时间</span>
              <input
                v-model="form.expireAt"
                type="datetime-local"
                class="pw-input"
              >
            </label>
          </div>
        </div>

        <template #footer>
          <div class="flex flex-wrap justify-end gap-3">
            <BaseButton
              variant="secondary"
              @click="showEditDialog = false"
            >
              取消
            </BaseButton>
            <BaseButton
              :disabled="saving || !canCreateAnnouncement"
              @click="saveAnnouncement"
            >
              {{ canCreateAnnouncement ? (saving ? '保存中...' : '保存公告') : '当前账号只读' }}
            </BaseButton>
          </div>
        </template>
      </BaseDialog>

      <ConfirmDialog
        :show="showDeleteDialog"
        title="删除公告"
        :message="
          deletingAnnouncement
            ? `确认删除公告“${deletingAnnouncement.title}”吗？此操作不可恢复。`
            : ''
        "
        confirm-text="删除"
        danger
        @cancel="cancelDelete"
        @confirm="confirmDelete"
      />
    </template>
  </section>
</template>

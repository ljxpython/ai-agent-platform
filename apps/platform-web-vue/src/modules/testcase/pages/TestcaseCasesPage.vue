<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseDialog from '@/components/base/BaseDialog.vue'
import BaseSelect from '@/components/base/BaseSelect.vue'
import ConfirmDialog from '@/components/base/ConfirmDialog.vue'
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
import { getOperationFailureMessage } from '@/services/operations/operations.service'
import { resolvePlatformClientScope } from '@/services/platform/control-plane'
import {
  createTestcaseCase,
  deleteTestcaseCase,
  exportTestcaseCases,
  exportTestcaseCasesByOperation,
  getTestcaseCase,
  getTestcaseOverview,
  getTestcaseRole,
  listTestcaseBatches,
  listTestcaseCases,
  listTestcaseDocuments,
  updateTestcaseCase,
  type TestcaseServiceMode,
  type UpsertTestcaseCasePayload
} from '@/services/testcase/testcase.service'
import { useUiStore } from '@/stores/ui'
import { useWorkspaceStore } from '@/stores/workspace'
import type {
  TestcaseBatchSummary,
  TestcaseCase,
  TestcaseDocument,
  TestcaseOverview,
  TestcaseRole
} from '@/types/management'
import { copyText } from '@/utils/clipboard'
import { downloadBlob } from '@/utils/browser-download'
import { formatDateTime, shortId } from '@/utils/format'

type CaseDialogMode = 'detail' | 'create' | 'edit'

type JsonParseResult = {
  value: Record<string, unknown>
  error: string | null
}

type CaseFormState = {
  batch_id: string
  case_id: string
  title: string
  description: string
  status: string
  module_name: string
  priority: string
  source_document_ids: string[]
  preconditions_text: string
  steps_text: string
  expected_results_text: string
  test_type: string
  design_technique: string
  test_data_text: string
  remarks: string
}

const FORM_STATUS_OPTIONS = ['active', 'draft', 'disabled', 'archived']
const PRIORITY_OPTIONS = ['', 'P0', 'P1', 'P2', 'P3', 'high', 'medium', 'low']

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

function asRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {}
  }
  return value as Record<string, unknown>
}

function coerceText(value: unknown): string {
  if (value == null) {
    return ''
  }
  return String(value).trim()
}

function asStringList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return []
  }
  return value.map((item) => coerceText(item)).filter(Boolean)
}

function joinLines(value: unknown): string {
  return asStringList(value).join('\n')
}

function splitLines(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function stringifyJson(value: unknown) {
  return JSON.stringify(value ?? {}, null, 2)
}

function parseJsonObjectText(value: string): JsonParseResult {
  const normalized = value.trim()
  if (!normalized) {
    return { value: {}, error: null }
  }

  try {
    const parsed = JSON.parse(normalized) as unknown
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return {
        value: {},
        error: 'test_data 必须是 JSON object，不能是数组或纯文本。'
      }
    }
    return {
      value: parsed as Record<string, unknown>,
      error: null
    }
  } catch (error) {
    return {
      value: {},
      error: error instanceof Error ? `test_data JSON 非法：${error.message}` : 'test_data JSON 非法'
    }
  }
}

function buildDefaultForm(batchId = ''): CaseFormState {
  return {
    batch_id: batchId,
    case_id: '',
    title: '',
    description: '',
    status: 'active',
    module_name: '',
    priority: '',
    source_document_ids: [],
    preconditions_text: '',
    steps_text: '',
    expected_results_text: '',
    test_type: '',
    design_technique: '',
    test_data_text: '{}',
    remarks: ''
  }
}

function buildFormFromCase(item: TestcaseCase): CaseFormState {
  const content = asRecord(item.content_json)
  const testData = asRecord(content.test_data)
  return {
    batch_id: item.batch_id ?? '',
    case_id: item.case_id ?? coerceText(content.case_id),
    title: item.title,
    description: item.description,
    status: item.status,
    module_name: item.module_name ?? coerceText(content.module_name),
    priority: item.priority ?? coerceText(content.priority),
    source_document_ids: item.source_document_ids ?? [],
    preconditions_text: joinLines(content.preconditions),
    steps_text: joinLines(content.steps),
    expected_results_text: joinLines(content.expected_results),
    test_type: coerceText(content.test_type),
    design_technique: coerceText(content.design_technique),
    test_data_text: Object.keys(testData).length > 0 ? stringifyJson(testData) : '{}',
    remarks: coerceText(content.remarks)
  }
}

function buildContentJsonPayload(
  form: CaseFormState,
  baseContentJson?: Record<string, unknown>
): Record<string, unknown> {
  const next: Record<string, unknown> = { ...(baseContentJson ?? {}) }
  const assign = (key: string, value: unknown) => {
    if (value == null) {
      delete next[key]
      return
    }
    if (typeof value === 'string' && value.trim() === '') {
      delete next[key]
      return
    }
    if (Array.isArray(value) && value.length === 0) {
      delete next[key]
      return
    }
    if (typeof value === 'object' && !Array.isArray(value) && Object.keys(asRecord(value)).length === 0) {
      delete next[key]
      return
    }
    next[key] = value
  }

  assign('case_id', form.case_id)
  assign('title', form.title)
  assign('description', form.description)
  assign('module_name', form.module_name)
  assign('priority', form.priority)
  assign('preconditions', splitLines(form.preconditions_text))
  assign('steps', splitLines(form.steps_text))
  assign('expected_results', splitLines(form.expected_results_text))
  assign('test_type', form.test_type)
  assign('design_technique', form.design_technique)
  assign('remarks', form.remarks)

  const parsedTestData = parseJsonObjectText(form.test_data_text)
  if (parsedTestData.error) {
    throw new Error(parsedTestData.error)
  }
  assign('test_data', parsedTestData.value)

  return next
}

const workspaceStore = useWorkspaceStore()
const uiStore = useUiStore()
const testcaseUseRuntimeApi = computed(() => resolvePlatformClientScope('testcase') === 'v2')
const activeProjectId = computed(() =>
  testcaseUseRuntimeApi.value ? workspaceStore.runtimeProjectId : workspaceStore.currentProjectId
)
const activeProject = computed(() =>
  testcaseUseRuntimeApi.value ? workspaceStore.runtimeProject : workspaceStore.currentProject
)

const overview = ref<TestcaseOverview | null>(null)
const batches = ref<TestcaseBatchSummary[]>([])
const role = ref<TestcaseRole | null>(null)
const items = ref<TestcaseCase[]>([])
const sourceDocuments = ref<TestcaseDocument[]>([])
const loading = ref(false)
const metaLoading = ref(false)
const exporting = ref(false)
const saving = ref(false)
const deleting = ref(false)
const sourceDocumentsLoading = ref(false)
const detailLoading = ref(false)
const error = ref('')
const detailError = ref('')
const formError = ref('')
const searchInput = ref('')
const batchInput = ref('')
const statusInput = ref('')
const sourceDocumentQuery = ref('')
const query = ref('')
const batchFilter = ref('')
const statusFilter = ref('')
const caseDialogOpen = ref(false)
const caseDialogMode = ref<CaseDialogMode>('detail')
const showDeleteDialog = ref(false)
const selectedSummary = ref<TestcaseCase | null>(null)
const selectedCase = ref<TestcaseCase | null>(null)
const form = ref<CaseFormState>(buildDefaultForm())

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

const canWrite = computed(() => Boolean(role.value?.can_write_testcase))
const requestOptions = computed<{ mode: TestcaseServiceMode } | undefined>(() =>
  testcaseUseRuntimeApi.value ? { mode: 'runtime' } : undefined
)
const dialogTitle = computed(() => {
  if (caseDialogMode.value === 'create') {
    return '新增测试用例'
  }
  if (caseDialogMode.value === 'edit') {
    return '编辑测试用例'
  }
  return '用例详情'
})
const parsedTestData = computed(() => parseJsonObjectText(form.value.test_data_text))
const stepsCount = computed(() => splitLines(form.value.steps_text).length)
const expectedResultsCount = computed(() => splitLines(form.value.expected_results_text).length)
const filteredSourceDocuments = computed(() => {
  const normalized = sourceDocumentQuery.value.trim().toLowerCase()
  if (!normalized) {
    return sourceDocuments.value
  }
  return sourceDocuments.value.filter((document) =>
    [document.filename, document.id, document.parse_status, document.batch_id]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(normalized))
  )
})
const unresolvedSourceDocumentIds = computed(() => {
  const lookup = new Set(sourceDocuments.value.map((item) => item.id))
  return form.value.source_document_ids.filter((documentId) => !lookup.has(documentId))
})
const detailMeta = computed(() => asRecord(asRecord(selectedCase.value?.content_json).meta))

function testcaseCaseFromRow(row: Record<string, unknown>) {
  return row as TestcaseCase
}

function pushToast(type: 'success' | 'error' | 'warning' | 'info', title: string, message: string) {
  uiStore.pushToast({ type, title, message })
}

async function handleCopyValue(label: string, value: string) {
  const copied = await copyText(value)
  pushToast(
    copied ? 'success' : 'warning',
    copied ? `已复制${label}` : '复制失败',
    copied ? value : '当前环境不支持自动复制，请手动复制。'
  )
}

async function loadMeta(projectId: string) {
  metaLoading.value = true
  try {
    const [overviewPayload, batchPayload, rolePayload] = await Promise.all([
      getTestcaseOverview(projectId, requestOptions.value),
      listTestcaseBatches(projectId, { limit: 100, offset: 0 }, requestOptions.value),
      getTestcaseRole(projectId, requestOptions.value)
    ])
    overview.value = overviewPayload
    batches.value = batchPayload.items
    role.value = rolePayload
  } finally {
    metaLoading.value = false
  }
}

async function loadCaseList() {
  const projectId = activeProjectId.value
  if (!projectId) {
    items.value = []
    pagination.setTotal(0)
    error.value = ''
    return
  }

  loading.value = true
  error.value = ''

  try {
    const payload = await listTestcaseCases(
      projectId,
      {
        batch_id: batchFilter.value || undefined,
        status: statusFilter.value || undefined,
        query: query.value || undefined,
        limit: pagination.pageSize.value,
        offset: pagination.offset.value
      },
      requestOptions.value
    )
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

async function refreshPage() {
  const projectId = activeProjectId.value
  if (!projectId) {
    overview.value = null
    batches.value = []
    role.value = null
    items.value = []
    pagination.setTotal(0)
    return
  }

  try {
    await Promise.all([loadMeta(projectId), loadCaseList()])
  } catch (refreshError) {
    error.value = refreshError instanceof Error ? refreshError.message : 'Testcase 页面刷新失败'
  }
}

async function loadSourceDocuments() {
  const projectId = activeProjectId.value
  if (!projectId) {
    sourceDocuments.value = []
    return
  }

  sourceDocumentsLoading.value = true
  try {
    const payload = await listTestcaseDocuments(
      projectId,
      {
        batch_id: form.value.batch_id || undefined,
        limit: 200,
        offset: 0
      },
      requestOptions.value
    )
    sourceDocuments.value = payload.items
  } catch (loadError) {
    sourceDocuments.value = []
    formError.value = loadError instanceof Error ? loadError.message : '来源文档加载失败'
  } finally {
    sourceDocumentsLoading.value = false
  }
}

async function loadCaseDetail(caseId: string) {
  const projectId = activeProjectId.value
  if (!projectId) {
    selectedCase.value = null
    detailError.value = ''
    return
  }

  detailLoading.value = true
  detailError.value = ''
  try {
    selectedCase.value = await getTestcaseCase(projectId, caseId, requestOptions.value)
  } catch (loadError) {
    selectedCase.value = null
    detailError.value = loadError instanceof Error ? loadError.message : '用例详情加载失败'
  } finally {
    detailLoading.value = false
  }
}

async function openDetailDialog(item: TestcaseCase) {
  caseDialogMode.value = 'detail'
  caseDialogOpen.value = true
  selectedSummary.value = item
  selectedCase.value = item
  formError.value = ''
  await loadCaseDetail(item.id)
}

async function openEditDialog(item: TestcaseCase) {
  caseDialogMode.value = 'edit'
  caseDialogOpen.value = true
  selectedSummary.value = item
  selectedCase.value = item
  formError.value = ''
  sourceDocumentQuery.value = ''
  await Promise.all([loadCaseDetail(item.id), loadSourceDocuments()])
  if (selectedCase.value) {
    form.value = buildFormFromCase(selectedCase.value)
  }
}

async function openCreateDialog() {
  caseDialogMode.value = 'create'
  caseDialogOpen.value = true
  selectedSummary.value = null
  selectedCase.value = null
  detailError.value = ''
  formError.value = ''
  sourceDocumentQuery.value = ''
  form.value = buildDefaultForm(batchFilter.value)
  await loadSourceDocuments()
}

function closeCaseDialog() {
  if (saving.value || deleting.value) {
    return
  }
  caseDialogOpen.value = false
  detailError.value = ''
  formError.value = ''
  sourceDocumentQuery.value = ''
}

function toggleSourceDocument(documentId: string, checked: boolean) {
  if (checked) {
    form.value = {
      ...form.value,
      source_document_ids: Array.from(new Set([...form.value.source_document_ids, documentId]))
    }
    return
  }

  form.value = {
    ...form.value,
    source_document_ids: form.value.source_document_ids.filter((item) => item !== documentId)
  }
}

function buildMutationPayload(): UpsertTestcaseCasePayload {
  return {
    batch_id: form.value.batch_id || null,
    case_id: form.value.case_id || null,
    title: form.value.title.trim(),
    description: form.value.description,
    status: form.value.status,
    module_name: form.value.module_name || null,
    priority: form.value.priority || null,
    source_document_ids: form.value.source_document_ids,
    content_json: buildContentJsonPayload(
      form.value,
      caseDialogMode.value === 'edit' ? asRecord(selectedCase.value?.content_json) : {}
    )
  }
}

async function handleSave() {
  const projectId = activeProjectId.value
  if (!projectId) {
    return
  }

  if (!form.value.title.trim()) {
    formError.value = '标题不能为空。'
    return
  }
  if (stepsCount.value === 0) {
    formError.value = '步骤至少填写 1 条。'
    return
  }
  if (expectedResultsCount.value === 0) {
    formError.value = '预期结果至少填写 1 条。'
    return
  }
  if (parsedTestData.value.error) {
    formError.value = parsedTestData.value.error
    return
  }

  saving.value = true
  formError.value = ''

  try {
    const payload = buildMutationPayload()
    const saved =
      caseDialogMode.value === 'create'
        ? await createTestcaseCase(
            projectId,
            {
              ...payload,
              title: payload.title || form.value.title.trim()
            },
            requestOptions.value
          )
        : await updateTestcaseCase(
            projectId,
            selectedSummary.value?.id || selectedCase.value?.id || '',
            payload,
            requestOptions.value
          )

    pushToast(
      'success',
      caseDialogMode.value === 'create' ? '创建成功' : '保存成功',
      `${saved.title} 已写入 testcase 服务。`
    )
    await refreshPage()
    caseDialogMode.value = 'detail'
    selectedSummary.value = saved
    selectedCase.value = saved
    await loadCaseDetail(saved.id)
  } catch (saveError) {
    formError.value = saveError instanceof Error ? saveError.message : '测试用例保存失败'
  } finally {
    saving.value = false
  }
}

async function handleDelete() {
  const projectId = activeProjectId.value
  const targetId = selectedSummary.value?.id || selectedCase.value?.id
  if (!projectId || !targetId) {
    return
  }

  deleting.value = true
  try {
    await deleteTestcaseCase(projectId, targetId, requestOptions.value)
    pushToast(
      'success',
      '删除成功',
      `${selectedCase.value?.title || selectedSummary.value?.title || shortId(targetId)} 已移除。`
    )
    showDeleteDialog.value = false
    closeCaseDialog()
    await refreshPage()
  } catch (deleteError) {
    pushToast(
      'error',
      '删除失败',
      deleteError instanceof Error ? deleteError.message : '测试用例删除失败'
    )
  } finally {
    deleting.value = false
  }
}

async function handleExport() {
  const projectId = activeProjectId.value
  if (!projectId || exporting.value) {
    return
  }

  exporting.value = true
  try {
    const exportOptions = {
      batch_id: batchFilter.value || undefined,
      status: statusFilter.value || undefined,
      query: query.value || undefined
    }
    const download = testcaseUseRuntimeApi.value
      ? await (async () => {
          const result = await exportTestcaseCasesByOperation(projectId, exportOptions)
          if (result.operation.status !== 'succeeded') {
            throw new Error(getOperationFailureMessage(result.operation))
          }
          return result.download
        })()
      : await exportTestcaseCases(projectId, exportOptions, requestOptions.value)
    downloadBlob(
      download.blob,
      download.filename ||
        `testcase-cases-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.xlsx`
    )
    pushToast('success', '导出成功', `已导出当前筛选结果，共 ${pagination.total.value} 条测试用例。`)
  } catch (exportError) {
    pushToast('error', '导出失败', exportError instanceof Error ? exportError.message : '测试用例导出失败')
  } finally {
    exporting.value = false
  }
}

function applyFilters() {
  query.value = searchInput.value.trim()
  batchFilter.value = batchInput.value
  statusFilter.value = statusInput.value
  if (pagination.page.value === 1) {
    void loadCaseList()
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
    void loadCaseList()
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
      void loadCaseList()
    } else {
      pagination.resetPage()
    }
  }
}

function caseActions(item: TestcaseCase): ActionMenuItem[] {
  const actions: ActionMenuItem[] = [
    {
      key: 'detail',
      label: '查看详情',
      icon: 'eye',
      onSelect: () => void openDetailDialog(item)
    },
    {
      key: 'copy-case-id',
      label: item.case_id ? '复制 Case ID' : '缺少 Case ID',
      icon: 'copy',
      disabled: !item.case_id,
      onSelect: () => void handleCopyValue('Case ID', item.case_id || '')
    },
    {
      key: 'copy-batch-id',
      label: item.batch_id ? '复制批次 ID' : '未归属批次',
      icon: 'copy',
      disabled: !item.batch_id,
      onSelect: () => void handleCopyValue('批次 ID', item.batch_id || '')
    }
  ]

  if (canWrite.value) {
    actions.push({
      key: 'edit',
      label: '编辑',
      icon: 'eye',
      onSelect: () => void openEditDialog(item)
    })
    actions.push({
      key: 'delete',
      label: '删除',
      icon: 'x',
      onSelect: async () => {
        selectedSummary.value = item
        selectedCase.value = item
        await loadCaseDetail(item.id)
        showDeleteDialog.value = true
      }
    })
  }

  return actions
}

watch([() => pagination.page.value, () => pagination.pageSize.value], () => {
  void loadCaseList()
})

watch(
  () => activeProjectId.value,
  () => {
    batchInput.value = ''
    statusInput.value = ''
    searchInput.value = ''
    query.value = ''
    batchFilter.value = ''
    statusFilter.value = ''
    if (pagination.page.value !== 1) {
      pagination.resetPage()
      return
    }
    void refreshPage()
  },
  { immediate: true }
)

watch(
  () => form.value.batch_id,
  () => {
    if (caseDialogOpen.value && caseDialogMode.value !== 'detail') {
      void loadSourceDocuments()
    }
  }
)
</script>

<template>
  <section class="pw-page-shell">
    <TestcaseWorkspaceNav />

    <PageHeader
      eyebrow="Testcase"
      title="用例列表"
      description="查看正式保存的测试用例，已经补上详情、创建、编辑、删除和按当前筛选结果导出。"
    >
      <template #actions>
        <div class="flex flex-wrap items-center gap-2">
          <BaseButton
            variant="secondary"
            :disabled="!activeProjectId || loading || exporting || pagination.total.value === 0"
            @click="handleExport"
          >
            {{ exporting ? '导出中...' : '导出 Excel' }}
          </BaseButton>
          <BaseButton
            variant="secondary"
            :disabled="loading || metaLoading"
            @click="refreshPage"
          >
            刷新
          </BaseButton>
          <BaseButton
            :disabled="!activeProjectId || !canWrite"
            @click="openCreateDialog"
          >
            新增用例
          </BaseButton>
        </div>
      </template>
    </PageHeader>

    <TestcaseOverviewStrip :overview="overview" />

    <StateBanner
      v-if="error"
      title="测试用例列表加载失败"
      :description="error"
      variant="danger"
    />

    <StateBanner
      v-else-if="role"
      title="当前角色"
      :description="`${role.role} · ${role.can_write_testcase ? '可写' : '只读'}`"
      variant="info"
    />

    <EmptyState
      v-if="!activeProject"
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
            canWrite
              ? '当前项目下还没有保存的测试用例，现在已经可以直接创建、编辑和导出。'
              : '当前项目下没有保存的测试用例，且你当前是只读角色。'
          "
          empty-icon="testcase"
        >
          <template #cell-title="{ row }">
            <button
              type="button"
              class="text-left"
              @click="openDetailDialog(testcaseCaseFromRow(row))"
            >
              <div class="font-semibold text-gray-900 dark:text-white">
                {{ testcaseCaseFromRow(row).title }}
              </div>
              <div class="mt-1 text-xs text-gray-400 dark:text-dark-400">
                {{ testcaseCaseFromRow(row).case_id || shortId(testcaseCaseFromRow(row).id) }} · 来源文档 {{ testcaseCaseFromRow(row).source_document_ids.length }}
              </div>
            </button>
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

    <BaseDialog
      :show="caseDialogOpen"
      :title="dialogTitle"
      width="full"
      @close="closeCaseDialog"
    >
      <div class="space-y-5">
        <StateBanner
          v-if="detailError"
          title="用例详情加载失败"
          :description="detailError"
          variant="danger"
        />

        <StateBanner
          v-if="formError"
          title="表单校验失败"
          :description="formError"
          variant="warning"
        />

        <template v-if="caseDialogMode === 'detail'">
          <div
            v-if="detailLoading"
            class="rounded-[24px] border border-gray-100 bg-gray-50/80 px-4 py-6 text-sm text-gray-500 dark:border-dark-700 dark:bg-dark-900/50 dark:text-dark-300"
          >
            正在加载用例详情...
          </div>

          <template v-else-if="selectedCase">
            <div class="grid gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
              <div class="space-y-4">
                <div class="rounded-[28px] border border-gray-100 bg-white/90 px-5 py-5 dark:border-dark-700 dark:bg-dark-950/80">
                  <div class="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div class="text-xl font-semibold text-gray-900 dark:text-white">
                        {{ selectedCase.title }}
                      </div>
                      <div class="mt-2 text-xs text-gray-400 dark:text-dark-400">
                        {{ selectedCase.case_id || selectedCase.id }}
                      </div>
                    </div>
                    <div class="flex flex-wrap gap-2">
                      <StatusPill :tone="getStatusTone(selectedCase.status)">
                        {{ selectedCase.status }}
                      </StatusPill>
                      <StatusPill :tone="getPriorityTone(selectedCase.priority || '')">
                        {{ selectedCase.priority || '未设优先级' }}
                      </StatusPill>
                    </div>
                  </div>

                  <div class="mt-4 grid gap-4 sm:grid-cols-2">
                    <div>
                      <div class="text-xs uppercase tracking-[0.18em] text-gray-400 dark:text-dark-400">
                        模块
                      </div>
                      <div class="mt-1 text-sm text-gray-700 dark:text-dark-200">
                        {{ selectedCase.module_name || '--' }}
                      </div>
                    </div>
                    <div>
                      <div class="text-xs uppercase tracking-[0.18em] text-gray-400 dark:text-dark-400">
                        批次
                      </div>
                      <div class="mt-1 break-all text-sm text-gray-700 dark:text-dark-200">
                        {{ selectedCase.batch_id || '--' }}
                      </div>
                    </div>
                    <div>
                      <div class="text-xs uppercase tracking-[0.18em] text-gray-400 dark:text-dark-400">
                        创建时间
                      </div>
                      <div class="mt-1 text-sm text-gray-700 dark:text-dark-200">
                        {{ formatDateTime(selectedCase.created_at) }}
                      </div>
                    </div>
                    <div>
                      <div class="text-xs uppercase tracking-[0.18em] text-gray-400 dark:text-dark-400">
                        更新时间
                      </div>
                      <div class="mt-1 text-sm text-gray-700 dark:text-dark-200">
                        {{ formatDateTime(selectedCase.updated_at) }}
                      </div>
                    </div>
                  </div>
                </div>

                <div class="grid gap-4 lg:grid-cols-2">
                  <div class="rounded-[28px] border border-gray-100 bg-white/90 px-5 py-5 dark:border-dark-700 dark:bg-dark-950/80">
                    <div class="text-sm font-semibold text-gray-900 dark:text-white">
                      描述
                    </div>
                    <div class="mt-3 whitespace-pre-wrap text-sm leading-7 text-gray-600 dark:text-dark-300">
                      {{ selectedCase.description || '--' }}
                    </div>
                  </div>

                  <div class="rounded-[28px] border border-gray-100 bg-white/90 px-5 py-5 dark:border-dark-700 dark:bg-dark-950/80">
                    <div class="text-sm font-semibold text-gray-900 dark:text-white">
                      前置条件
                    </div>
                    <div class="mt-3 whitespace-pre-wrap text-sm leading-7 text-gray-600 dark:text-dark-300">
                      {{ joinLines(asRecord(selectedCase.content_json).preconditions) || '--' }}
                    </div>
                  </div>
                </div>

                <div class="grid gap-4 lg:grid-cols-2">
                  <div class="rounded-[28px] border border-gray-100 bg-white/90 px-5 py-5 dark:border-dark-700 dark:bg-dark-950/80">
                    <div class="text-sm font-semibold text-gray-900 dark:text-white">
                      步骤
                    </div>
                    <div class="mt-3 whitespace-pre-wrap text-sm leading-7 text-gray-600 dark:text-dark-300">
                      {{ joinLines(asRecord(selectedCase.content_json).steps) || '--' }}
                    </div>
                  </div>

                  <div class="rounded-[28px] border border-gray-100 bg-white/90 px-5 py-5 dark:border-dark-700 dark:bg-dark-950/80">
                    <div class="text-sm font-semibold text-gray-900 dark:text-white">
                      预期结果
                    </div>
                    <div class="mt-3 whitespace-pre-wrap text-sm leading-7 text-gray-600 dark:text-dark-300">
                      {{ joinLines(asRecord(selectedCase.content_json).expected_results) || '--' }}
                    </div>
                  </div>
                </div>

                <div class="grid gap-4 lg:grid-cols-2">
                  <div class="rounded-[28px] border border-gray-100 bg-white/90 px-5 py-5 dark:border-dark-700 dark:bg-dark-950/80">
                    <div class="text-sm font-semibold text-gray-900 dark:text-white">
                      扩展字段
                    </div>
                    <div class="mt-3 space-y-3 text-sm text-gray-600 dark:text-dark-300">
                      <div>test_type: {{ coerceText(asRecord(selectedCase.content_json).test_type) || '--' }}</div>
                      <div>design_technique: {{ coerceText(asRecord(selectedCase.content_json).design_technique) || '--' }}</div>
                      <div>remarks: {{ coerceText(asRecord(selectedCase.content_json).remarks) || '--' }}</div>
                    </div>
                  </div>

                  <div class="rounded-[28px] border border-gray-100 bg-white/90 px-5 py-5 dark:border-dark-700 dark:bg-dark-950/80">
                    <div class="text-sm font-semibold text-gray-900 dark:text-white">
                      test_data
                    </div>
                    <pre class="mt-3 overflow-auto whitespace-pre-wrap break-all rounded-2xl bg-gray-50 p-3 text-xs leading-6 text-gray-700 dark:bg-dark-900 dark:text-gray-200">{{ stringifyJson(asRecord(selectedCase.content_json).test_data) }}</pre>
                  </div>
                </div>
              </div>

              <div class="space-y-4">
                <div class="rounded-[28px] border border-gray-100 bg-white/90 px-5 py-5 dark:border-dark-700 dark:bg-dark-950/80">
                  <div class="flex items-center justify-between gap-3">
                    <div class="text-sm font-semibold text-gray-900 dark:text-white">
                      来源文档
                    </div>
                    <div class="text-xs text-gray-400 dark:text-dark-400">
                      {{ selectedCase.source_document_ids.length }} 条
                    </div>
                  </div>

                  <div class="mt-3 space-y-3">
                    <div
                      v-for="document in selectedCase.source_documents || []"
                      :key="document.id"
                      class="rounded-2xl border border-gray-100 bg-gray-50/80 px-3 py-3 dark:border-dark-700 dark:bg-dark-900/60"
                    >
                      <div class="font-medium text-gray-900 dark:text-white">
                        {{ document.filename }}
                      </div>
                      <div class="mt-1 break-all text-xs text-gray-500 dark:text-dark-300">
                        {{ document.id }} · {{ document.parse_status }} · {{ document.batch_id || '--' }}
                      </div>
                    </div>

                    <div
                      v-for="missingId in selectedCase.missing_source_document_ids || []"
                      :key="missingId"
                      class="rounded-2xl border border-amber-200 bg-amber-50/80 px-3 py-3 text-xs text-amber-800 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-200"
                    >
                      缺失文档：{{ missingId }}
                    </div>

                    <div
                      v-if="!selectedCase.source_document_ids.length"
                      class="text-sm text-gray-500 dark:text-dark-300"
                    >
                      当前用例没有绑定来源文档。
                    </div>
                  </div>
                </div>

                <div class="rounded-[28px] border border-gray-100 bg-white/90 px-5 py-5 dark:border-dark-700 dark:bg-dark-950/80">
                  <div class="text-sm font-semibold text-gray-900 dark:text-white">
                    meta.quality_review
                  </div>
                  <pre class="mt-3 overflow-auto whitespace-pre-wrap break-all rounded-2xl bg-gray-50 p-3 text-xs leading-6 text-gray-700 dark:bg-dark-900 dark:text-gray-200">{{ stringifyJson(detailMeta.quality_review) }}</pre>
                </div>
              </div>
            </div>
          </template>

          <EmptyState
            v-else
            icon="testcase"
            title="暂无详情"
            description="当前没有可展示的用例详情。"
          />
        </template>

        <template v-else>
          <div class="grid gap-4 md:grid-cols-2">
            <label class="block">
              <span class="pw-input-label">标题</span>
              <input
                v-model="form.title"
                class="pw-input"
                :disabled="saving"
              >
            </label>

            <label class="block">
              <span class="pw-input-label">Case ID</span>
              <input
                v-model="form.case_id"
                class="pw-input"
                :disabled="saving"
              >
            </label>
          </div>

          <div class="grid gap-4 md:grid-cols-4">
            <label class="block">
              <span class="pw-input-label">状态</span>
              <BaseSelect
                v-model="form.status"
                :disabled="saving"
              >
                <option
                  v-for="status in FORM_STATUS_OPTIONS"
                  :key="status"
                  :value="status"
                >
                  {{ status }}
                </option>
              </BaseSelect>
            </label>

            <label class="block">
              <span class="pw-input-label">优先级</span>
              <BaseSelect
                v-model="form.priority"
                :disabled="saving"
              >
                <option
                  v-for="priority in PRIORITY_OPTIONS"
                  :key="priority || 'empty'"
                  :value="priority"
                >
                  {{ priority || '未设置' }}
                </option>
              </BaseSelect>
            </label>

            <label class="block">
              <span class="pw-input-label">模块</span>
              <input
                v-model="form.module_name"
                class="pw-input"
                :disabled="saving"
              >
            </label>

            <label class="block">
              <span class="pw-input-label">批次</span>
              <BaseSelect
                v-model="form.batch_id"
                :disabled="saving"
              >
                <option value="">
                  未归属批次
                </option>
                <option
                  v-for="item in batches"
                  :key="item.batch_id"
                  :value="item.batch_id"
                >
                  {{ item.batch_id }}
                </option>
              </BaseSelect>
            </label>
          </div>

          <label class="block">
            <span class="pw-input-label">描述</span>
            <textarea
              v-model="form.description"
              rows="4"
              class="pw-input min-h-[120px] resize-y"
              :disabled="saving"
            />
          </label>

          <div class="grid gap-4 lg:grid-cols-2">
            <label class="block">
              <span class="pw-input-label">前置条件（一行一项）</span>
              <textarea
                v-model="form.preconditions_text"
                rows="8"
                class="pw-input min-h-[180px] resize-y"
                :disabled="saving"
              />
            </label>

            <label class="block">
              <span class="pw-input-label">步骤（一行一项，当前 {{ stepsCount }} 条）</span>
              <textarea
                v-model="form.steps_text"
                rows="8"
                class="pw-input min-h-[180px] resize-y"
                :disabled="saving"
              />
            </label>
          </div>

          <div class="grid gap-4 lg:grid-cols-2">
            <label class="block">
              <span class="pw-input-label">预期结果（一行一项，当前 {{ expectedResultsCount }} 条）</span>
              <textarea
                v-model="form.expected_results_text"
                rows="8"
                class="pw-input min-h-[180px] resize-y"
                :disabled="saving"
              />
            </label>

            <div class="grid gap-4">
              <label class="block">
                <span class="pw-input-label">test_type</span>
                <input
                  v-model="form.test_type"
                  class="pw-input"
                  :disabled="saving"
                >
              </label>

              <label class="block">
                <span class="pw-input-label">design_technique</span>
                <input
                  v-model="form.design_technique"
                  class="pw-input"
                  :disabled="saving"
                >
              </label>

              <label class="block">
                <span class="pw-input-label">remarks</span>
                <textarea
                  v-model="form.remarks"
                  rows="4"
                  class="pw-input min-h-[120px] resize-y"
                  :disabled="saving"
                />
              </label>
            </div>
          </div>

          <label class="block">
            <span class="pw-input-label">test_data (JSON object)</span>
            <textarea
              v-model="form.test_data_text"
              rows="10"
              class="pw-input min-h-[220px] resize-y font-mono text-xs leading-6"
              :disabled="saving"
            />
            <div
              class="mt-2 text-xs"
              :class="parsedTestData.error ? 'text-rose-500' : 'text-gray-400 dark:text-dark-400'"
            >
              {{ parsedTestData.error || '实时校验通过，保存时会按 JSON object 写入 content_json.test_data。' }}
            </div>
          </label>

          <div class="rounded-[28px] border border-gray-100 bg-gray-50/70 px-5 py-5 dark:border-dark-700 dark:bg-dark-900/50">
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div class="text-sm font-semibold text-gray-900 dark:text-white">
                  来源文档
                </div>
                <div class="mt-1 text-xs text-gray-400 dark:text-dark-400">
                  当前已选 {{ form.source_document_ids.length }} 条。这里只加载当前批次或当前项目下前 200 条文档用于快速绑定。
                </div>
              </div>
              <BaseButton
                variant="secondary"
                :disabled="sourceDocumentsLoading"
                @click="loadSourceDocuments"
              >
                {{ sourceDocumentsLoading ? '加载中...' : '重新加载文档' }}
              </BaseButton>
            </div>

            <div class="mt-4">
              <SearchInput
                v-model="sourceDocumentQuery"
                placeholder="按文件名、文档 ID、解析状态过滤来源文档"
              />
            </div>

            <div class="mt-4 max-h-[320px] space-y-3 overflow-auto pr-1">
              <label
                v-for="document in filteredSourceDocuments"
                :key="document.id"
                class="flex items-start gap-3 rounded-2xl border border-white/70 bg-white/85 px-4 py-3 text-sm dark:border-dark-700 dark:bg-dark-950/75"
              >
                <input
                  type="checkbox"
                  class="pw-table-checkbox mt-1"
                  :checked="form.source_document_ids.includes(document.id)"
                  :disabled="saving"
                  @change="toggleSourceDocument(document.id, ($event.target as HTMLInputElement).checked)"
                >
                <div class="min-w-0">
                  <div class="font-medium text-gray-900 dark:text-white">
                    {{ document.filename }}
                  </div>
                  <div class="mt-1 break-all text-xs text-gray-500 dark:text-dark-300">
                    {{ document.id }} · {{ document.parse_status }} · {{ document.batch_id || '--' }}
                  </div>
                </div>
              </label>

              <div
                v-if="!filteredSourceDocuments.length && !sourceDocumentsLoading"
                class="text-sm text-gray-500 dark:text-dark-300"
              >
                当前筛选下没有可选来源文档。
              </div>
            </div>

            <div
              v-if="unresolvedSourceDocumentIds.length > 0"
              class="mt-4 rounded-2xl border border-amber-200 bg-amber-50/80 px-4 py-3 text-xs leading-6 text-amber-800 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-200"
            >
              当前有 {{ unresolvedSourceDocumentIds.length }} 个来源文档 ID 不在已加载列表里，但保存时仍会原样提交：
              {{ unresolvedSourceDocumentIds.join(', ') }}
            </div>
          </div>
        </template>
      </div>

      <template #footer>
        <div class="flex flex-wrap items-center justify-end gap-3">
          <template v-if="caseDialogMode === 'detail'">
            <BaseButton
              variant="secondary"
              @click="closeCaseDialog"
            >
              关闭
            </BaseButton>
            <BaseButton
              v-if="canWrite && selectedSummary"
              variant="secondary"
              @click="openEditDialog(selectedSummary)"
            >
              编辑
            </BaseButton>
            <BaseButton
              v-if="canWrite && selectedSummary"
              variant="danger"
              @click="showDeleteDialog = true"
            >
              删除
            </BaseButton>
          </template>

          <template v-else>
            <BaseButton
              variant="secondary"
              :disabled="saving"
              @click="closeCaseDialog"
            >
              取消
            </BaseButton>
            <BaseButton
              :disabled="saving"
              @click="handleSave"
            >
              {{ saving ? '保存中...' : caseDialogMode === 'create' ? '创建' : '保存' }}
            </BaseButton>
          </template>
        </div>
      </template>
    </BaseDialog>

    <ConfirmDialog
      :show="showDeleteDialog"
      title="删除测试用例"
      :message="`删除 ${selectedCase?.title || selectedSummary?.title || '当前测试用例'} 后无法恢复，确认继续吗？`"
      confirm-text="删除"
      danger
      @cancel="showDeleteDialog = false"
      @confirm="handleDelete"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseSelect from '@/components/base/BaseSelect.vue'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import { usePagination } from '@/composables/usePagination'
import { useVisibleFilterSettings } from '@/composables/useVisibleFilterSettings'
import { useWorkspaceProjectContext } from '@/composables/useWorkspaceProjectContext'
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
import {
  downloadTestcaseDocument,
  exportTestcaseDocumentsByOperation,
  getTestcaseBatchDetail,
  getTestcaseDocument,
  getTestcaseDocumentRelations,
  getTestcaseOverview,
  listTestcaseBatches,
  listTestcaseDocuments,
  previewTestcaseDocument
} from '@/services/testcase/testcase.service'
import { useUiStore } from '@/stores/ui'
import type {
  TestcaseBatchDetail,
  TestcaseBatchSummary,
  TestcaseDocument,
  TestcaseDocumentRelations,
  TestcaseOverview
} from '@/types/management'
import { copyText } from '@/utils/clipboard'
import { downloadBlob } from '@/utils/browser-download'
import { formatDateTime, shortId } from '@/utils/format'

function getParseStatusTone(status: string): 'neutral' | 'success' | 'warning' | 'danger' {
  if (status === 'parsed') {
    return 'success'
  }
  if (status === 'failed') {
    return 'danger'
  }
  if (status === 'unsupported') {
    return 'warning'
  }
  return 'neutral'
}

function escapeHtml(value: string) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function openPreviewWindowShell(filename?: string) {
  const previewWindow = window.open('', '_blank')
  if (!previewWindow) {
    throw new Error('浏览器阻止了预览窗口，请允许当前站点打开新窗口后重试。')
  }

  previewWindow.document.write(`<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>${escapeHtml(filename || 'document')}</title>
    <style>
      body {
        margin: 0;
        min-height: 100dvh;
        display: grid;
        place-items: center;
        background: #eef3fa;
        color: #33465f;
        font-family: "Segoe UI", "PingFang SC", sans-serif;
      }
      .preview-loading {
        border-radius: 18px;
        border: 1px solid rgba(118, 145, 178, 0.18);
        background: rgba(255, 255, 255, 0.92);
        padding: 18px 22px;
        box-shadow: 0 18px 40px rgba(67, 93, 126, 0.08);
        font-size: 14px;
      }
    </style>
  </head>
  <body>
    <div class="preview-loading">正在加载预览…</div>
  </body>
</html>`)
  previewWindow.document.close()
  return previewWindow
}

function isTextPreviewContentType(contentType: string): boolean {
  return (
    contentType.startsWith('text/') ||
    contentType === 'application/json' ||
    contentType === 'application/xml' ||
    contentType === 'application/javascript' ||
    contentType === 'text/markdown'
  )
}

function supportsInlinePreview(contentType: string): boolean {
  return (
    contentType.startsWith('application/pdf') ||
    contentType.startsWith('image/') ||
    isTextPreviewContentType(contentType)
  )
}

async function openDocumentPreview(
  blob: Blob,
  options?: { filename?: string; contentType?: string | null; previewWindow?: Window | null }
) {
  const contentType = (options?.contentType || blob.type || 'application/octet-stream').toLowerCase()
  const previewWindow = options?.previewWindow ?? window.open('', '_blank')
  if (!previewWindow) {
    throw new Error('浏览器阻止了预览窗口，请允许当前站点打开新窗口后重试。')
  }

  if (contentType.startsWith('application/pdf')) {
    const objectUrl = URL.createObjectURL(blob)
    previewWindow.location.replace(objectUrl)
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000)
    return
  }

  if (contentType.startsWith('image/')) {
    const objectUrl = URL.createObjectURL(blob)
    previewWindow.document.write(`<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>${escapeHtml(options?.filename || 'image')}</title>
    <style>
      body {
        margin: 0;
        min-height: 100dvh;
        display: grid;
        place-items: center;
        background: #dfe7f3;
      }
      img {
        display: block;
        max-width: min(92vw, 1440px);
        max-height: 92vh;
        object-fit: contain;
        border-radius: 18px;
        box-shadow: 0 24px 60px rgba(15, 23, 42, 0.16);
        background: rgba(255, 255, 255, 0.82);
      }
    </style>
  </head>
  <body>
    <img src="${objectUrl}" alt="${escapeHtml(options?.filename || 'image')}" />
  </body>
</html>`)
    previewWindow.document.close()
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000)
    return
  }

  if (isTextPreviewContentType(contentType)) {
    const text = await blob.text()
    previewWindow.document.write(`<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>${escapeHtml(options?.filename || 'document')}</title>
    <style>
      body {
        margin: 0;
        padding: 24px;
        background: #eef3fa;
        color: #142033;
        font-family: "SFMono-Regular", "Consolas", monospace;
      }
      pre {
        margin: 0;
        white-space: pre-wrap;
        word-break: break-word;
        line-height: 1.7;
        font-size: 13px;
      }
    </style>
  </head>
  <body>
    <pre>${escapeHtml(text)}</pre>
  </body>
</html>`)
    previewWindow.document.close()
    return
  }

  throw new Error(`当前类型暂不支持在线预览：${contentType}`)
}

function stringifyJson(value: unknown) {
  return JSON.stringify(value ?? {}, null, 2)
}

function coerceText(value: unknown): string {
  if (value == null) {
    return ''
  }
  return String(value).trim()
}

function asRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {}
  }
  return value as Record<string, unknown>
}

function resolveStoragePath(document: TestcaseDocument | null): string {
  if (!document) {
    return ''
  }
  if (document.storage_path) {
    return document.storage_path
  }
  const provenance = asRecord(document.provenance)
  const asset = asRecord(provenance.asset)
  return coerceText(asset.storage_path)
}

const { activeProjectId, activeProject } = useWorkspaceProjectContext()
const uiStore = useUiStore()

const overview = ref<TestcaseOverview | null>(null)
const batches = ref<TestcaseBatchSummary[]>([])
const items = ref<TestcaseDocument[]>([])
const loading = ref(false)
const error = ref('')
const searchInput = ref('')
const batchInput = ref('')
const parseStatusInput = ref('')
const query = ref('')
const batchFilter = ref('')
const parseStatusFilter = ref('')
const selectedId = ref('')
const relations = ref<TestcaseDocumentRelations | null>(null)
const detailLoading = ref(false)
const detailError = ref('')
const batchDetail = ref<TestcaseBatchDetail | null>(null)
const batchDetailLoading = ref(false)
const batchDetailError = ref('')
const previewing = ref(false)
const downloading = ref(false)
const exporting = ref(false)
const documentRows = computed(() => items.value as unknown as Record<string, unknown>[])
const pagination = usePagination({
  initialPageSize: 20,
  storageKey: 'pw:testcase-documents:page-size'
})
const filterItems: FilterSettingItem[] = [
  { key: 'batch', label: '批次' },
  { key: 'parse_status', label: '解析状态' }
]
const { visibleFilterKeys, visibleFilterSet, setVisibleFilterKeys } = useVisibleFilterSettings(
  filterItems,
  'pw:testcase-documents:filters'
)
const columns = computed<DataTableColumn[]>(() => [
  {
    key: 'filename',
    label: '文件名',
    sortable: true,
    alwaysVisible: true,
    sortValue: (row) => row.filename || ''
  },
  {
    key: 'parse_status',
    label: '状态',
    sortable: true,
    sortValue: (row) => row.parse_status || ''
  },
  {
    key: 'source_kind',
    label: '来源',
    sortable: true,
    sortValue: (row) => row.source_kind || ''
  },
  {
    key: 'batch_id',
    label: '批次',
    sortable: true,
    defaultHidden: true,
    sortValue: (row) => row.batch_id || ''
  },
  {
    key: 'created_at',
    label: '创建时间',
    sortable: true,
    sortValue: (row) => row.created_at || ''
  }
])

function documentFromRow(row: Record<string, unknown>) {
  return row as TestcaseDocument
}

const selectedListItem = computed(
  () => items.value.find((item) => item.id === selectedId.value) ?? null
)
const selectedItem = computed(() => relations.value?.document ?? selectedListItem.value)
const storagePath = computed(() => resolveStoragePath(selectedItem.value))
const selectedContentType = computed(() => (selectedItem.value?.content_type || '').toLowerCase())
const isPreviewSupported = computed(() => supportsInlinePreview(selectedContentType.value))
const selectedBatchSummary = computed(
  () => batchDetail.value?.batch ?? batches.value.find((item) => item.batch_id === (selectedItem.value?.batch_id || '')) ?? null
)
const batchStatusEntries = computed(() =>
  Object.entries(selectedBatchSummary.value?.parse_status_summary ?? {}).sort(([left], [right]) =>
    left.localeCompare(right)
  )
)
const sameBatchDocuments = computed(() => {
  if (!selectedItem.value?.batch_id) {
    return []
  }
  return (batchDetail.value?.documents.items ?? []).filter((item) => item.id !== selectedItem.value?.id)
})
const batchPreviewCases = computed(() => batchDetail.value?.test_cases.items ?? [])

async function loadMeta(projectId: string) {
  const [overviewPayload, batchPayload] = await Promise.all([
    getTestcaseOverview(projectId),
    listTestcaseBatches(projectId, { limit: 100, offset: 0 })
  ])
  overview.value = overviewPayload
  batches.value = batchPayload.items
}

async function loadDocuments() {
  const projectId = activeProjectId.value
  if (!projectId) {
    overview.value = null
    batches.value = []
    items.value = []
    pagination.setTotal(0)
    relations.value = null
    selectedId.value = ''
    error.value = ''
    return
  }

  loading.value = true
  error.value = ''

  try {
    await loadMeta(projectId)
    const payload = await listTestcaseDocuments(projectId, {
      batch_id: batchFilter.value || undefined,
      parse_status: parseStatusFilter.value || undefined,
      query: query.value || undefined,
      limit: pagination.pageSize.value,
      offset: pagination.offset.value
    })
    items.value = payload.items
    pagination.setTotal(payload.total)

    if (!selectedId.value || !payload.items.some((item) => item.id === selectedId.value)) {
      selectedId.value = payload.items[0]?.id || ''
    }
  } catch (loadError) {
    items.value = []
    pagination.setTotal(0)
    error.value = loadError instanceof Error ? loadError.message : '文档解析列表加载失败'
  } finally {
    loading.value = false
  }
}

async function loadDetail() {
  const projectId = activeProjectId.value
  if (!projectId || !selectedId.value) {
    relations.value = null
    batchDetail.value = null
    detailError.value = ''
    batchDetailError.value = ''
    return
  }

  detailLoading.value = true
  detailError.value = ''
  batchDetailError.value = ''
  try {
    const [relationsPayload, documentPayload] = await Promise.all([
      getTestcaseDocumentRelations(projectId, selectedId.value),
      getTestcaseDocument(projectId, selectedId.value)
    ])
    relations.value = {
      ...relationsPayload,
      document: documentPayload
    }
    await loadBatchDetail(documentPayload.batch_id)
  } catch (loadError) {
    relations.value = null
    batchDetail.value = null
    detailError.value = loadError instanceof Error ? loadError.message : '文档详情加载失败'
  } finally {
    detailLoading.value = false
  }
}

function selectDocument(documentId: string) {
  selectedId.value = documentId
  detailError.value = ''
  batchDetailError.value = ''
}

async function loadBatchDetail(batchId: string | null | undefined) {
  const projectId = activeProjectId.value
  if (!projectId || !batchId) {
    batchDetail.value = null
    batchDetailError.value = ''
    return
  }

  batchDetailLoading.value = true
  batchDetailError.value = ''
  try {
    batchDetail.value = await getTestcaseBatchDetail(
      projectId,
      batchId,
      {
        document_limit: 100,
        document_offset: 0,
        case_limit: 50,
        case_offset: 0
      }
    )
  } catch (loadError) {
    batchDetail.value = null
    batchDetailError.value = loadError instanceof Error ? loadError.message : '批次上下文加载失败'
  } finally {
    batchDetailLoading.value = false
  }
}

async function handlePreview(targetDocument: TestcaseDocument | null = selectedItem.value) {
  const projectId = activeProjectId.value
  if (!projectId || !targetDocument) {
    return
  }
  const targetContentType = (targetDocument.content_type || '').toLowerCase()
  if (!supportsInlinePreview(targetContentType)) {
    detailError.value = `当前类型暂不支持在线预览：${targetDocument.content_type || 'unknown'}`
    return
  }

  previewing.value = true
  let previewWindow: Window | null = null

  try {
    selectDocument(targetDocument.id)
    previewWindow = openPreviewWindowShell(targetDocument.filename)
    const download = await previewTestcaseDocument(projectId, targetDocument.id)
    await openDocumentPreview(download.blob, {
      filename: targetDocument.filename,
      contentType: download.contentType || targetDocument.content_type,
      previewWindow
    })
  } catch (previewError) {
    previewWindow?.close()
    detailError.value = previewError instanceof Error ? previewError.message : '文档预览失败'
  } finally {
    previewing.value = false
  }
}

async function handleDownload(targetDocument: TestcaseDocument | null = selectedItem.value) {
  const projectId = activeProjectId.value
  if (!projectId || !targetDocument) {
    return
  }

  downloading.value = true
  try {
    selectDocument(targetDocument.id)
    const download = await downloadTestcaseDocument(projectId, targetDocument.id)
    downloadBlob(download.blob, download.filename || targetDocument.filename)
  } catch (downloadError) {
    detailError.value = downloadError instanceof Error ? downloadError.message : '文档下载失败'
  } finally {
    downloading.value = false
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
      parse_status: parseStatusFilter.value || undefined,
      query: query.value || undefined
    }
    const download = await (async () => {
      const result = await exportTestcaseDocumentsByOperation(projectId, exportOptions)
      if (result.operation.status !== 'succeeded') {
        throw new Error(getOperationFailureMessage(result.operation))
      }
      return result.download
    })()
    downloadBlob(
      download.blob,
      download.filename ||
        `testcase-documents-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.xlsx`
    )
    uiStore.pushToast({
      type: 'success',
      title: '导出成功',
      message: `已导出当前筛选结果，共 ${pagination.total.value} 条文档记录。`
    })
  } catch (exportError) {
    uiStore.pushToast({
      type: 'error',
      title: '导出失败',
      message: exportError instanceof Error ? exportError.message : '文档导出失败'
    })
  } finally {
    exporting.value = false
  }
}

function applyFilters() {
  query.value = searchInput.value.trim()
  batchFilter.value = batchInput.value
  parseStatusFilter.value = parseStatusInput.value
  if (pagination.page.value === 1) {
    void loadDocuments()
    return
  }

  pagination.resetPage()
}

function resetFilters() {
  searchInput.value = ''
  batchInput.value = ''
  parseStatusInput.value = ''
  query.value = ''
  batchFilter.value = ''
  parseStatusFilter.value = ''
  if (pagination.page.value === 1) {
    void loadDocuments()
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

  if (previous.has('parse_status') && !visibleFilterSet.value.has('parse_status')) {
    parseStatusInput.value = ''
    parseStatusFilter.value = ''
    shouldReload = true
  }

  if (shouldReload) {
    if (pagination.page.value === 1) {
      void loadDocuments()
    } else {
      pagination.resetPage()
    }
  }
}

async function handleCopyDocumentId(document: TestcaseDocument) {
  const copied = await copyText(document.id)
  uiStore.pushToast({
    type: copied ? 'success' : 'warning',
    title: copied ? '已复制文档 ID' : '复制失败',
    message: copied ? shortId(document.id) : '当前环境不支持自动复制，请手动复制。'
  })
}

async function handleCopyBatchId(batchId: string) {
  const copied = await copyText(batchId)
  uiStore.pushToast({
    type: copied ? 'success' : 'warning',
    title: copied ? '已复制批次 ID' : '复制失败',
    message: copied ? batchId : '当前环境不支持自动复制，请手动复制。'
  })
}

function documentActions(document: TestcaseDocument): ActionMenuItem[] {
  const path = resolveStoragePath(document)
  const previewSupported = supportsInlinePreview((document.content_type || '').toLowerCase())

  return [
    {
      key: 'detail',
      label: document.id === selectedId.value ? '当前详情文档' : '查看详情',
      icon: 'eye',
      disabled: document.id === selectedId.value,
      onSelect: () => {
        selectDocument(document.id)
      }
    },
    {
      key: 'preview',
      label: '在线预览',
      icon: 'eye',
      disabled: !path || !previewSupported,
      onSelect: () => handlePreview(document)
    },
    {
      key: 'download',
      label: '下载原始文件',
      icon: 'download',
      disabled: !path,
      onSelect: () => handleDownload(document)
    },
    {
      key: 'copy-id',
      label: '复制文档 ID',
      icon: 'copy',
      onSelect: () => handleCopyDocumentId(document)
    }
  ]
}

function documentRowClass(row: Record<string, unknown>) {
  return documentFromRow(row).id === selectedId.value ? 'bg-primary-50/80 dark:bg-primary-950/20' : ''
}

watch(
  [() => pagination.page.value, () => pagination.pageSize.value],
  () => {
    void loadDocuments()
  }
)

watch(
  () => activeProjectId.value,
  () => {
    if (pagination.page.value !== 1) {
      pagination.resetPage()
      return
    }

    void loadDocuments()
  },
  { immediate: true }
)

watch(
  () => selectedId.value,
  () => {
    void loadDetail()
  }
)
</script>

<template>
  <section class="pw-page-shell">
    <TestcaseWorkspaceNav />

    <PageHeader
      eyebrow="Testcase Agent"
      title="文档列表"
      description="查看已保存到服务端的文档解析结果，并统一承接在线预览、原始文件下载与批次上下文。"
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
            @click="loadDocuments"
          >
            刷新
          </BaseButton>
        </div>
      </template>
    </PageHeader>

    <TestcaseOverviewStrip :overview="overview" />

    <StateBanner
      v-if="error"
      title="文档解析列表加载失败"
      :description="error"
      variant="danger"
    />

    <EmptyState
      v-if="!activeProject"
      icon="project"
      title="请先选择项目"
      description="没有项目上下文，没法读取 Testcase Agent 文档解析结果。"
    />

    <div
      v-else
      class="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(360px,1fr)]"
    >
      <div class="space-y-4">
        <FilterToolbar>
          <div class="flex flex-wrap items-center gap-3">
            <div class="min-w-0 flex-1 basis-full sm:min-w-[260px]">
              <SearchInput
                v-model="searchInput"
                placeholder="按文件名或摘要搜索"
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
              v-if="visibleFilterSet.has('parse_status')"
              class="w-full sm:w-[200px]"
            >
              <BaseSelect v-model="parseStatusInput">
                <option value="">
                  全部状态
                </option>
                <option value="parsed">
                  parsed
                </option>
                <option value="failed">
                  failed
                </option>
                <option value="unsupported">
                  unsupported
                </option>
                <option value="unprocessed">
                  unprocessed
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

        <SurfaceCard class="space-y-4 overflow-hidden">
          <DataTable
            :columns="columns"
            :rows="documentRows"
            :loading="loading"
            :row-class="documentRowClass"
            row-key="id"
            sort-storage-key="pw:testcase-documents:sort"
            column-storage-key="pw:testcase-documents:columns"
            empty-title="当前没有文档解析结果"
            empty-description="当前项目下还没有保存过文档解析记录。"
            empty-icon="folder"
          >
            <template #cell-filename="{ row }">
              <button
                type="button"
                class="text-left"
                @click="selectDocument(documentFromRow(row).id)"
              >
                <div class="font-medium text-gray-900 dark:text-white">
                  {{ documentFromRow(row).filename }}
                </div>
                <div class="mt-1 text-xs text-gray-400 dark:text-dark-400">
                  {{ documentFromRow(row).content_type }} · {{ shortId(documentFromRow(row).id) }}
                </div>
                <div
                  v-if="documentFromRow(row).id === selectedId"
                  class="mt-1 text-xs uppercase tracking-[0.14em] text-primary-600 dark:text-primary-300"
                >
                  当前查看
                </div>
              </button>
            </template>

            <template #cell-parse_status="{ row }">
              <StatusPill :tone="getParseStatusTone(documentFromRow(row).parse_status)">
                {{ documentFromRow(row).parse_status }}
              </StatusPill>
            </template>

            <template #cell-source_kind="{ row }">
              <span class="text-gray-500 dark:text-dark-300">
                {{ documentFromRow(row).source_kind }}
              </span>
            </template>

            <template #cell-batch_id="{ row }">
              <span class="text-gray-500 dark:text-dark-300">
                {{ documentFromRow(row).batch_id || '--' }}
              </span>
            </template>

            <template #cell-created_at="{ row }">
              <span class="text-gray-500 dark:text-dark-300">
                {{ formatDateTime(documentFromRow(row).created_at) }}
              </span>
            </template>

            <template #cell-actions="{ row }">
              <ActionMenu :items="documentActions(documentFromRow(row))" />
            </template>
          </DataTable>

          <PaginationBar
            v-if="pagination.total.value > 0"
            :total="pagination.total.value"
            :page="pagination.page.value"
            :page-size="pagination.pageSize.value"
            :disabled="loading || previewing || downloading"
            @update:page="pagination.setPage"
            @update:page-size="pagination.setPageSize"
          />
        </SurfaceCard>
      </div>

      <SurfaceCard class="space-y-4">
        <div class="flex flex-wrap items-start justify-between gap-2">
          <div class="text-base font-semibold text-gray-900 dark:text-white">
            解析详情
          </div>
          <div class="flex flex-wrap gap-2">
            <BaseButton
              variant="secondary"
              :disabled="!selectedItem || !storagePath || !isPreviewSupported || previewing"
              @click="handlePreview"
            >
              {{ previewing ? '预览中...' : '在线预览' }}
            </BaseButton>
            <BaseButton
              variant="secondary"
              :disabled="!selectedItem || !storagePath || downloading"
              @click="handleDownload"
            >
              {{ downloading ? '下载中...' : '下载原始文件' }}
            </BaseButton>
          </div>
        </div>

        <StateBanner
          v-if="detailError"
          title="文档详情异常"
          :description="detailError"
          variant="danger"
        />

        <div
          v-if="detailLoading"
          class="text-sm text-gray-500 dark:text-dark-300"
        >
          正在加载文档详情...
        </div>

        <EmptyState
          v-else-if="!selectedItem"
          icon="folder"
          title="先选择一个文档"
          description="选中左侧文档后，这里会展示解析详情、关联用例以及在线预览/下载能力。"
        />

        <template v-else>
          <div class="space-y-1">
            <div class="text-lg font-semibold tracking-tight break-all text-gray-900 dark:text-white">
              {{ selectedItem.filename }}
            </div>
            <div class="text-xs text-gray-400 dark:text-dark-400">
              {{ selectedItem.id }}
            </div>
          </div>

          <div class="grid gap-3 text-sm">
            <div>
              <div class="text-xs uppercase tracking-[0.18em] text-gray-400 dark:text-dark-400">
                解析状态
              </div>
              <div class="mt-1 text-gray-900 dark:text-white">
                {{ selectedItem.parse_status }}
              </div>
            </div>
            <div>
              <div class="text-xs uppercase tracking-[0.18em] text-gray-400 dark:text-dark-400">
                原始文件路径
              </div>
              <div class="mt-1 break-all text-gray-500 dark:text-dark-300">
                {{ storagePath || '当前记录未保存原始文件路径，仅保留了解析结果。' }}
              </div>
            </div>
            <div>
              <div class="text-xs uppercase tracking-[0.18em] text-gray-400 dark:text-dark-400">
                预览能力
              </div>
              <div class="mt-1 text-gray-500 dark:text-dark-300">
                {{
                  isPreviewSupported
                    ? `当前支持在线预览，类型为 ${selectedItem.content_type || 'unknown'}。`
                    : `当前仅支持下载，暂不支持在线预览 ${selectedItem.content_type || 'unknown'}。`
                }}
              </div>
            </div>
            <div>
              <div class="text-xs uppercase tracking-[0.18em] text-gray-400 dark:text-dark-400">
                关联用例
              </div>
              <div class="mt-1 text-xs text-gray-400 dark:text-dark-400">
                共 {{ relations?.related_cases_count ?? 0 }} 条
              </div>
              <div class="mt-2 space-y-2">
                <div
                  v-for="item in relations?.related_cases || []"
                  :key="item.id"
                  class="rounded-xl border border-gray-200 bg-gray-50/80 px-3 py-2 text-xs dark:border-dark-700 dark:bg-dark-900/50"
                >
                  <div class="font-medium text-gray-900 dark:text-white">
                    {{ item.title }}
                  </div>
                  <div class="mt-1 text-gray-500 dark:text-dark-300">
                    {{ item.case_id || item.id }} / {{ item.status }} / {{ item.batch_id || '--' }}
                  </div>
                </div>
                <div
                  v-if="!relations?.related_cases?.length"
                  class="text-xs text-gray-500 dark:text-dark-300"
                >
                  当前 document 尚未关联到正式测试用例。
                </div>
              </div>
            </div>
            <div>
              <div class="text-xs uppercase tracking-[0.18em] text-gray-400 dark:text-dark-400">
                runtime_meta
              </div>
              <pre class="pw-code-block mt-2 max-h-[180px]">{{ stringifyJson(relations?.runtime_meta) }}</pre>
            </div>
            <div>
              <div class="text-xs uppercase tracking-[0.18em] text-gray-400 dark:text-dark-400">
                摘要
              </div>
              <div class="mt-1 whitespace-pre-wrap text-gray-500 dark:text-dark-300">
                {{ selectedItem.summary_for_model || '--' }}
              </div>
            </div>
            <div>
              <div class="text-xs uppercase tracking-[0.18em] text-gray-400 dark:text-dark-400">
                parsed_text
              </div>
              <pre class="pw-code-block mt-2 max-h-[220px]">{{ selectedItem.parsed_text || '--' }}</pre>
            </div>
            <div>
              <div class="text-xs uppercase tracking-[0.18em] text-gray-400 dark:text-dark-400">
                structured_data
              </div>
              <pre class="pw-code-block max-h-[220px]">{{ stringifyJson(selectedItem.structured_data) }}</pre>
            </div>
            <div>
              <div class="text-xs uppercase tracking-[0.18em] text-gray-400 dark:text-dark-400">
                provenance
              </div>
              <pre class="pw-code-block mt-2 max-h-[220px]">{{ stringifyJson(selectedItem.provenance) }}</pre>
            </div>
            <div v-if="selectedItem.error">
              <div class="text-xs uppercase tracking-[0.18em] text-gray-400 dark:text-dark-400">
                error
              </div>
              <pre class="mt-2 max-h-[180px] overflow-auto whitespace-pre-wrap break-words rounded-2xl bg-rose-50 p-3 text-xs text-rose-700 dark:bg-rose-950/20 dark:text-rose-200">{{ stringifyJson(selectedItem.error) }}</pre>
            </div>

            <div class="pw-panel-muted">
              <div class="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div class="text-sm font-semibold text-gray-900 dark:text-white">
                    Batch Context
                  </div>
                  <div class="mt-1 text-xs text-gray-400 dark:text-dark-400">
                    {{ selectedItem.batch_id || '当前文档未归属批次' }}
                  </div>
                </div>
                <div class="flex flex-wrap gap-2">
                  <BaseButton
                    variant="secondary"
                    :disabled="!selectedItem.batch_id || batchDetailLoading"
                    @click="loadBatchDetail(selectedItem.batch_id)"
                  >
                    {{ batchDetailLoading ? '加载中...' : '刷新批次上下文' }}
                  </BaseButton>
                  <BaseButton
                    v-if="selectedItem.batch_id"
                    variant="secondary"
                    @click="handleCopyBatchId(selectedItem.batch_id)"
                  >
                    复制批次 ID
                  </BaseButton>
                </div>
              </div>

              <StateBanner
                v-if="batchDetailError"
                class="mt-4"
                title="批次上下文加载失败"
                :description="batchDetailError"
                variant="warning"
              />

              <div
                v-else-if="batchDetailLoading"
                class="mt-4 text-sm text-gray-500 dark:text-dark-300"
              >
                正在加载批次上下文...
              </div>

              <div
                v-else-if="selectedBatchSummary"
                class="mt-4 space-y-4"
              >
                <div class="grid gap-3 md:grid-cols-3">
                  <div class="pw-panel-muted px-3 py-3 text-sm">
                    文档数：{{ selectedBatchSummary.documents_count }}
                  </div>
                  <div class="pw-panel-muted px-3 py-3 text-sm">
                    用例数：{{ selectedBatchSummary.test_cases_count }}
                  </div>
                  <div class="pw-panel-muted px-3 py-3 text-sm">
                    最新时间：{{ formatDateTime(selectedBatchSummary.latest_created_at) }}
                  </div>
                </div>

                <div>
                  <div class="text-xs uppercase tracking-[0.18em] text-gray-400 dark:text-dark-400">
                    解析状态分布
                  </div>
                  <div class="mt-2 flex flex-wrap gap-2">
                    <StatusPill
                      v-for="[status, count] in batchStatusEntries"
                      :key="status"
                      :tone="getParseStatusTone(status)"
                    >
                      {{ status }} · {{ count }}
                    </StatusPill>
                    <div
                      v-if="batchStatusEntries.length === 0"
                      class="text-xs text-gray-500 dark:text-dark-300"
                    >
                      当前批次没有状态聚合数据。
                    </div>
                  </div>
                </div>

                <div>
                  <div class="text-xs uppercase tracking-[0.18em] text-gray-400 dark:text-dark-400">
                    同批次文档
                  </div>
                  <div class="mt-2 space-y-2">
                    <button
                      v-for="document in sameBatchDocuments"
                      :key="document.id"
                      type="button"
                      class="pw-panel flex w-full items-start justify-between gap-3 px-3 py-3 text-left transition hover:border-primary-200 dark:hover:border-primary-700"
                      @click="selectDocument(document.id)"
                    >
                      <div class="min-w-0">
                        <div class="font-medium text-gray-900 dark:text-white">
                          {{ document.filename }}
                        </div>
                        <div class="mt-1 break-all text-xs text-gray-500 dark:text-dark-300">
                          {{ document.id }}
                        </div>
                      </div>
                      <StatusPill :tone="getParseStatusTone(document.parse_status)">
                        {{ document.parse_status }}
                      </StatusPill>
                    </button>
                    <div
                      v-if="sameBatchDocuments.length === 0"
                      class="text-xs text-gray-500 dark:text-dark-300"
                    >
                      当前批次没有其他文档。
                    </div>
                  </div>
                </div>

                <div>
                  <div class="text-xs uppercase tracking-[0.18em] text-gray-400 dark:text-dark-400">
                    同批次用例预览
                  </div>
                  <div class="mt-2 space-y-2">
                    <div
                      v-for="item in batchPreviewCases"
                      :key="item.id"
                      class="pw-panel px-3 py-3 text-sm"
                    >
                      <div class="font-medium text-gray-900 dark:text-white">
                        {{ item.title }}
                      </div>
                      <div class="mt-1 break-all text-xs text-gray-500 dark:text-dark-300">
                        {{ item.case_id || item.id }} · {{ item.status }} · {{ item.module_name || '--' }}
                      </div>
                    </div>
                    <div
                      v-if="batchPreviewCases.length === 0"
                      class="text-xs text-gray-500 dark:text-dark-300"
                    >
                      当前批次还没有正式测试用例。
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>
      </SurfaceCard>
    </div>
  </section>
</template>

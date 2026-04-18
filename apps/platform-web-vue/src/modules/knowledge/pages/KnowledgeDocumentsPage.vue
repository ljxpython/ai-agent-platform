<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseDialog from '@/components/base/BaseDialog.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import ConfirmDialog from '@/components/base/ConfirmDialog.vue'
import BaseSelect from '@/components/base/BaseSelect.vue'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import TablePageLayout from '@/components/layout/TablePageLayout.vue'
import DataTable from '@/components/platform/DataTable.vue'
import FilterToolbar from '@/components/platform/FilterToolbar.vue'
import PaginationBar from '@/components/platform/PaginationBar.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import StatusPill from '@/components/platform/StatusPill.vue'
import type { DataTableColumn } from '@/components/platform/data-table'
import { usePagination } from '@/composables/usePagination'
import { useAuthorization } from '@/composables/useAuthorization'
import KnowledgePipelineStatusDialog from '@/modules/knowledge/components/KnowledgePipelineStatusDialog.vue'
import KnowledgeWorkspaceNav from '@/modules/knowledge/components/KnowledgeWorkspaceNav.vue'
import { useKnowledgeProjectRoute } from '@/modules/knowledge/composables/useKnowledgeProjectRoute'
import {
  cancelProjectKnowledgePipeline,
  clearProjectKnowledgeDocuments,
  deleteProjectKnowledgeDocument,
  getProjectKnowledgeDocumentDetail,
  getProjectKnowledgePipelineStatus,
  getProjectKnowledgeScanProgress,
  getProjectKnowledgeTrackStatus,
  listProjectKnowledgeDocuments,
  reprocessFailedProjectKnowledgeDocuments,
  startProjectKnowledgeScan,
  uploadProjectKnowledgeDocument,
} from '@/services/knowledge/knowledge.service'
import { waitForOperationTerminalState } from '@/services/operations/operations.service'
import { useUiStore } from '@/stores/ui'
import type {
  KnowledgeDocument,
  KnowledgeDocumentsScanProgress,
  KnowledgePipelineStatus,
  KnowledgeTrackStatus,
} from '@/types/management'
import { formatDateTime, shortId } from '@/utils/format'
import { resolvePlatformHttpErrorMessage } from '@/utils/http-error'

const { projectId, project } = useKnowledgeProjectRoute()
const uiStore = useUiStore()
const authorization = useAuthorization()

const statusFilter = ref('')
const loading = ref(false)
const actionLoading = ref(false)
const error = ref('')
const successMessage = ref('')
const items = ref<KnowledgeDocument[]>([])
const statusCounts = ref<Record<string, number>>({})
const pagination = usePagination({
  initialPageSize: 20,
  storageKey: 'pw:knowledge-documents:page-size',
})
const pipelineStatus = ref<KnowledgePipelineStatus | null>(null)
const scanProgress = ref<KnowledgeDocumentsScanProgress | null>(null)
const selectedTrackId = ref('')
const trackStatus = ref<KnowledgeTrackStatus | null>(null)
const uploadInput = ref<HTMLInputElement | null>(null)
const uploadTagsText = ref('')
const uploadLayer = ref('')
const showClearConfirm = ref(false)
const pendingDelete = ref<KnowledgeDocument | null>(null)
const showPipelineDialog = ref(false)
const selectedDocument = ref<KnowledgeDocument | null>(null)
const selectedDocumentDetail = ref<Record<string, unknown> | null>(null)

const canRead = computed(() => authorization.can('project.knowledge.read', projectId.value))
const canWrite = computed(() => authorization.can('project.knowledge.write', projectId.value))
const canAdmin = computed(() => authorization.can('project.knowledge.admin', projectId.value))
const documentRows = computed(() => items.value as unknown as Record<string, unknown>[])
const uploadMetadata = computed(() => {
  const tags = uploadTagsText.value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)

  const attributes: Record<string, string> = {}
  if (uploadLayer.value.trim()) {
    attributes.layer = uploadLayer.value.trim()
  }

  if (!tags.length && !Object.keys(attributes).length) {
    return undefined
  }

  return {
    ...(tags.length ? { tags } : {}),
    ...(Object.keys(attributes).length ? { attributes } : {}),
  }
})
const failedCount = computed(() => {
  const entries = Object.entries(statusCounts.value)
  const failed = entries.find(([status]) => status.toUpperCase() === 'FAILED')
  return failed?.[1] || 0
})
const trackOptions = computed(() =>
  Array.from(
    new Set(
      items.value
        .map((item) => String(item.track_id || '').trim())
        .filter(Boolean),
    ),
  ),
)
const statusSummaryCards = computed(() => {
  const statuses = [
    { key: 'PENDING', label: 'pending', icon: 'info' as const },
    { key: 'PROCESSING', label: 'processing', icon: 'activity' as const },
    { key: 'PREPROCESSED', label: 'preprocessed', icon: 'shield' as const },
    { key: 'PROCESSED', label: 'processed', icon: 'check' as const },
    { key: 'FAILED', label: 'failed', icon: 'alert' as const },
    { key: 'ALL', label: 'all', icon: 'file' as const },
  ]

  return statuses.map((item) => {
    const count =
      item.key === 'ALL'
        ? pagination.total.value
        : Object.entries(statusCounts.value).find(([status]) => status.toUpperCase() === item.key)?.[1] || 0
    return {
      ...item,
      count,
      tone: statusTone(item.key),
    }
  })
})
const columns = computed<DataTableColumn[]>(() => [
  {
    key: 'file_path',
    label: '文件',
    sortable: true,
    alwaysVisible: true,
    sortValue: (row) => row.file_path || row.id || '',
    cellClass: 'max-w-[540px]',
  },
  {
    key: 'status',
    label: '状态',
    sortable: true,
    sortValue: (row) => row.status || '',
  },
  {
    key: 'track_id',
    label: 'Track',
    sortable: true,
    sortValue: (row) => row.track_id || '',
  },
  {
    key: 'updated_at',
    label: '更新时间',
    sortable: true,
    sortValue: (row) => row.updated_at || '',
  },
])

function statusTone(status: string): 'neutral' | 'success' | 'warning' | 'danger' {
  const normalized = status.toUpperCase()
  if (normalized === 'PROCESSED' || normalized === 'SUCCESS') {
    return 'success'
  }
  if (normalized === 'FAILED' || normalized === 'FAIL') {
    return 'danger'
  }
  if (normalized === 'PROCESSING' || normalized === 'PENDING' || normalized === 'PREPROCESSED') {
    return 'warning'
  }
  return 'neutral'
}

function openUploadDialog() {
  uploadInput.value?.click()
}

function documentFromRow(row: Record<string, unknown>) {
  return row as KnowledgeDocument
}

async function loadTrackStatus() {
  if (!projectId.value || !canRead.value || !selectedTrackId.value.trim()) {
    trackStatus.value = null
    return
  }
  trackStatus.value = await getProjectKnowledgeTrackStatus(projectId.value, selectedTrackId.value.trim())
}

async function loadDocuments() {
  if (!projectId.value || !canRead.value) {
    items.value = []
    pagination.setTotal(0)
    statusCounts.value = {}
    pipelineStatus.value = null
    scanProgress.value = null
    trackStatus.value = null
    return
  }

  loading.value = true
  error.value = ''
  try {
    const [pagePayload, pipeline, progress] = await Promise.all([
      listProjectKnowledgeDocuments(projectId.value, {
        page: pagination.page.value,
        page_size: pagination.pageSize.value,
        status_filter: statusFilter.value || undefined,
      }),
      getProjectKnowledgePipelineStatus(projectId.value),
      getProjectKnowledgeScanProgress(projectId.value),
    ])
    items.value = pagePayload.documents
    pagination.setTotal(pagePayload.pagination.total_count)
    statusCounts.value = pagePayload.status_counts || {}
    pipelineStatus.value = pipeline
    scanProgress.value = progress

    if (!selectedTrackId.value && trackOptions.value.length) {
      selectedTrackId.value = trackOptions.value[0]
      await loadTrackStatus()
    }
  } catch (loadError) {
    items.value = []
    pagination.setTotal(0)
    statusCounts.value = {}
    error.value = resolvePlatformHttpErrorMessage(loadError, '知识文档加载失败', '知识文档')
  } finally {
    loading.value = false
  }
}

async function handleUploadChange(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || [])
  if (!projectId.value || files.length === 0) {
    return
  }

  actionLoading.value = true
  error.value = ''
  successMessage.value = ''

  try {
    let latestTrackId = ''
    for (const file of files) {
      const result = await uploadProjectKnowledgeDocument(
        projectId.value,
        file,
        uploadMetadata.value,
      )
      const trackId = String(result.track_id || '').trim()
      if (trackId) {
        latestTrackId = trackId
      }
    }
    if (latestTrackId) {
      selectedTrackId.value = latestTrackId
      await loadTrackStatus()
    }
    await loadDocuments()
    successMessage.value =
      files.length === 1
        ? '文档上传已提交。'
        : `已提交 ${files.length} 份文档的上传任务。`
    uploadTagsText.value = ''
    uploadLayer.value = ''
    uiStore.pushToast({
      type: 'success',
      title: '上传成功',
      message: successMessage.value,
    })
  } catch (uploadError) {
    error.value = resolvePlatformHttpErrorMessage(uploadError, '知识文档上传失败', '知识文档')
  } finally {
    input.value = ''
    actionLoading.value = false
  }
}

async function handleScan() {
  if (!projectId.value || !canWrite.value) {
    return
  }

  actionLoading.value = true
  error.value = ''
  successMessage.value = ''
  try {
    const operation = await startProjectKnowledgeScan(projectId.value)
    const finalOperation = await waitForOperationTerminalState(operation.id, {
      pollMs: 1000,
      timeoutMs: 90000,
    })
    const resultTrackId = String(finalOperation.result_payload?.track_id || '').trim()
    if (resultTrackId) {
      selectedTrackId.value = resultTrackId
      await loadTrackStatus()
    }
    successMessage.value = String(finalOperation.result_payload?.message || '扫描任务已提交。')
    showPipelineDialog.value = true
    await loadDocuments()
  } catch (scanError) {
    error.value = resolvePlatformHttpErrorMessage(scanError, '知识文档扫描失败', '知识文档')
  } finally {
    actionLoading.value = false
  }
}

async function handleRetryFailed() {
  if (!projectId.value || !canWrite.value) {
    return
  }

  actionLoading.value = true
  error.value = ''
  successMessage.value = ''
  try {
    const result = await reprocessFailedProjectKnowledgeDocuments(projectId.value)
    const trackId = String(result.track_id || '').trim()
    if (trackId) {
      selectedTrackId.value = trackId
      await loadTrackStatus()
    }
    successMessage.value = String(result.message || '失败文档已重新提交处理。')
    showPipelineDialog.value = true
    await loadDocuments()
  } catch (retryError) {
    error.value = resolvePlatformHttpErrorMessage(retryError, '重试失败文档失败', '知识文档')
  } finally {
    actionLoading.value = false
  }
}

async function handleCancelPipeline() {
  if (!projectId.value || !canWrite.value) {
    return
  }

  actionLoading.value = true
  error.value = ''
  successMessage.value = ''
  try {
    const result = await cancelProjectKnowledgePipeline(projectId.value)
    successMessage.value = String(result.message || '已提交流水线取消请求。')
    await loadDocuments()
  } catch (cancelError) {
    error.value = resolvePlatformHttpErrorMessage(cancelError, '取消流水线失败', '知识文档')
  } finally {
    actionLoading.value = false
  }
}

function requestClearAll() {
  if (!projectId.value || !canAdmin.value) {
    return
  }
  showClearConfirm.value = true
}

async function confirmClearAll() {
  if (!projectId.value || !canAdmin.value) {
    return
  }

  actionLoading.value = true
  error.value = ''
  successMessage.value = ''
  try {
    const operation = await clearProjectKnowledgeDocuments(projectId.value)
    const finalOperation = await waitForOperationTerminalState(operation.id, {
      pollMs: 1000,
      timeoutMs: 90000,
    })
    successMessage.value = String(finalOperation.result_payload?.message || '知识文档已清空。')
    selectedTrackId.value = ''
    trackStatus.value = null
    showClearConfirm.value = false
    await loadDocuments()
  } catch (clearError) {
    error.value = resolvePlatformHttpErrorMessage(clearError, '清空知识文档失败', '知识文档')
  } finally {
    actionLoading.value = false
  }
}

function requestDelete(document: KnowledgeDocument) {
  if (!projectId.value || !canWrite.value) {
    return
  }
  pendingDelete.value = document
}

async function openDocumentDetail(document: KnowledgeDocument) {
  selectedDocument.value = document
  selectedDocumentDetail.value = null
  if (!projectId.value) {
    return
  }
  try {
    selectedDocumentDetail.value = await getProjectKnowledgeDocumentDetail(projectId.value, document.id)
  } catch {
    selectedDocumentDetail.value = null
  }
}

async function confirmDelete() {
  if (!projectId.value || !canWrite.value || !pendingDelete.value) {
    return
  }

  actionLoading.value = true
  error.value = ''
  successMessage.value = ''
  try {
    const result = await deleteProjectKnowledgeDocument(projectId.value, pendingDelete.value.id)
    successMessage.value = String(result.message || '文档删除已提交。')
    pendingDelete.value = null
    await loadDocuments()
  } catch (deleteError) {
    error.value = resolvePlatformHttpErrorMessage(deleteError, '删除知识文档失败', '知识文档')
  } finally {
    actionLoading.value = false
  }
}

watch(
  () => [projectId.value, canRead.value, pagination.page.value, pagination.pageSize.value],
  () => {
    void loadDocuments()
  },
  { immediate: true },
)

watch(
  () => statusFilter.value,
  () => {
    if (pagination.page.value === 1) {
      void loadDocuments()
      return
    }

    pagination.resetPage()
  },
)

watch(
  () => projectId.value,
  () => {
    pagination.resetPage()
    selectedTrackId.value = ''
    trackStatus.value = null
  },
)

watch(
  () => selectedTrackId.value,
  () => {
    void loadTrackStatus()
  },
)
</script>

<template>
  <section class="pw-page-shell h-full min-h-0 overflow-y-auto">
    <PageHeader
      eyebrow="Knowledge"
      :title="project ? `${project.name} · 知识文档` : '知识文档'"
      description="保持平台壳层不变的前提下，这里补齐了更接近 LightRAG 的文档上传、流水线、失败重试和 track 反馈工作流。"
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          @click="void loadDocuments()"
        >
          刷新
        </BaseButton>
        <BaseButton
          variant="secondary"
          :disabled="actionLoading || !canRead"
          @click="showPipelineDialog = true"
        >
          流水线状态
        </BaseButton>
        <BaseButton
          variant="secondary"
          :disabled="!canWrite || actionLoading || failedCount <= 0"
          @click="void handleRetryFailed()"
        >
          重试失败文档
        </BaseButton>
        <BaseButton
          variant="secondary"
          :disabled="!canWrite || actionLoading"
          @click="void handleScan()"
        >
          扫描目录
        </BaseButton>
        <BaseButton
          variant="danger"
          :disabled="!canAdmin || actionLoading"
          @click="requestClearAll"
        >
          清空文档
        </BaseButton>
        <BaseButton
          :disabled="!canWrite || actionLoading"
          @click="openUploadDialog"
        >
          上传文档
        </BaseButton>
        <input
          ref="uploadInput"
          class="hidden"
          type="file"
          multiple
          @change="handleUploadChange"
        >
      </template>
    </PageHeader>

    <KnowledgeWorkspaceNav
      v-if="projectId"
      :project-id="projectId"
    />

    <SurfaceCard
      v-if="projectId && canWrite"
      class="mt-4"
    >
      <div class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_220px]">
        <label class="flex flex-col gap-2 text-sm font-medium text-gray-700 dark:text-dark-200">
          上传时附带 tags（逗号分隔，可选）
          <input
            v-model="uploadTagsText"
            type="text"
            class="pw-input"
            placeholder="architecture, storage"
          >
        </label>
        <label class="flex flex-col gap-2 text-sm font-medium text-gray-700 dark:text-dark-200">
          上传时附带 layer（可选）
          <BaseSelect v-model="uploadLayer">
            <option value="">
              不设置
            </option>
            <option value="infrastructure">
              infrastructure
            </option>
            <option value="application">
              application
            </option>
            <option value="component">
              component
            </option>
          </BaseSelect>
        </label>
      </div>
      <div class="mt-3 text-xs text-gray-400 dark:text-dark-500">
        当前上传 metadata 只会作为通用 metadata 写入，不会把 AITestLab 私有 taxonomy 固化为上游协议。
      </div>
    </SurfaceCard>

    <StateBanner
      v-if="projectId && !canRead"
      class="mt-4"
      title="当前角色没有项目知识读取权限"
      description="请联系项目管理员授予 project.knowledge.read 相关权限后，再查看该项目的知识工作台。"
      variant="info"
    />
    <StateBanner
      v-else-if="error"
      class="mt-4"
      title="知识文档工作台异常"
      :description="error"
      variant="danger"
    />
    <StateBanner
      v-else-if="successMessage"
      class="mt-4"
      title="最近操作成功"
      :description="successMessage"
      variant="success"
    />

    <div class="mt-4 grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(340px,1fr)]">
      <div class="space-y-4">
        <SurfaceCard>
          <div class="grid gap-4 lg:grid-cols-[minmax(180px,240px)_minmax(0,1fr)]">
            <div>
              <div class="text-xs font-semibold uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
                文档状态概览
              </div>
              <div class="mt-2 text-sm font-semibold text-gray-900 dark:text-white">
                {{ statusFilter || '全部状态' }}
              </div>
              <div class="mt-2 text-sm leading-6 text-gray-500 dark:text-dark-300">
                筛选区、表格区和分页区统一收敛到平台列表母版，避免每个业务页重复拼装自己的列表节奏。
              </div>
            </div>
            <div class="grid flex-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
              <div
                v-for="item in statusSummaryCards"
                :key="item.key"
                class="rounded-2xl border border-gray-100 bg-gray-50/80 px-4 py-3 dark:border-dark-800 dark:bg-dark-900/70"
              >
                <div class="flex items-center gap-2 text-xs uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
                  <BaseIcon
                    :name="item.icon"
                    size="xs"
                    class="h-3 w-3"
                    :stroke-width="1.6"
                  />
                  {{ item.label }}
                </div>
                <div class="mt-2 flex items-center justify-between">
                  <div class="text-2xl font-semibold text-gray-900 dark:text-white">
                    {{ item.count }}
                  </div>
                  <StatusPill :tone="item.tone">
                    {{ item.key }}
                  </StatusPill>
                </div>
              </div>
            </div>
          </div>
        </SurfaceCard>

        <template v-if="projectId && canRead">
          <TablePageLayout>
            <template #filters>
              <FilterToolbar>
                <div class="grid gap-4 xl:grid-cols-[minmax(220px,280px)_minmax(0,1fr)]">
                  <label class="flex flex-col gap-2 text-sm font-medium text-gray-700 dark:text-dark-200">
                    文档筛选
                    <BaseSelect v-model="statusFilter">
                      <option value="">
                        全部状态
                      </option>
                      <option value="PENDING">
                        PENDING
                      </option>
                      <option value="PROCESSING">
                        PROCESSING
                      </option>
                      <option value="PREPROCESSED">
                        PREPROCESSED
                      </option>
                      <option value="PROCESSED">
                        PROCESSED
                      </option>
                      <option value="FAILED">
                        FAILED
                      </option>
                    </BaseSelect>
                  </label>
                  <div class="flex items-end text-sm leading-6 text-gray-500 dark:text-dark-300">
                    文档列表统一回到平台列表页母版，筛选、表格和分页都使用共享组件，不再单页手写。
                  </div>
                </div>
              </FilterToolbar>
            </template>

            <template #table>
              <DataTable
                :columns="columns"
                :rows="documentRows"
                :loading="loading"
                row-key="id"
                sort-storage-key="pw:knowledge-documents:sort"
                column-storage-key="pw:knowledge-documents:columns"
                empty-title="当前项目还没有知识文档"
                empty-description="你可以先上传文档，或触发一次目录扫描，让项目知识空间开始建立自己的文档集合。"
                empty-icon="file"
              >
                <template #cell-file_path="{ row }">
                  <div class="min-w-0 max-w-[44rem]">
                    <button
                      type="button"
                      class="block w-full text-left text-sm font-semibold text-gray-900 transition hover:text-primary-600 dark:text-white dark:hover:text-primary-300"
                      @click="openDocumentDetail(documentFromRow(row))"
                    >
                      {{ documentFromRow(row).file_path || documentFromRow(row).id }}
                    </button>
                    <div class="mt-2 flex flex-wrap gap-2 text-[11px] text-gray-500 dark:text-dark-400">
                      <span class="rounded-full bg-gray-100 px-2 py-1 dark:bg-dark-800">
                        id {{ shortId(documentFromRow(row).id) }}
                      </span>
                      <span
                        v-if="typeof documentFromRow(row).chunks_count === 'number'"
                        class="rounded-full bg-gray-100 px-2 py-1 dark:bg-dark-800"
                      >
                        chunks {{ documentFromRow(row).chunks_count }}
                      </span>
                      <span class="rounded-full bg-gray-100 px-2 py-1 dark:bg-dark-800">
                        {{ documentFromRow(row).content_length }} chars
                      </span>
                    </div>
                    <div class="mt-2 whitespace-pre-wrap break-words text-xs leading-6 text-gray-500 dark:text-dark-400">
                      {{ documentFromRow(row).content_summary || '暂无摘要' }}
                    </div>
                    <div
                      v-if="documentFromRow(row).error_msg"
                      class="mt-2 whitespace-pre-wrap break-words rounded-2xl border border-rose-200 bg-rose-50/80 px-3 py-2 text-xs leading-6 text-rose-600 dark:border-rose-900/50 dark:bg-rose-950/20 dark:text-rose-300"
                    >
                      {{ documentFromRow(row).error_msg }}
                    </div>
                  </div>
                </template>

                <template #cell-status="{ row }">
                  <StatusPill :tone="statusTone(documentFromRow(row).status)">
                    {{ documentFromRow(row).status }}
                  </StatusPill>
                </template>

                <template #cell-track_id="{ row }">
                  <button
                    v-if="documentFromRow(row).track_id"
                    type="button"
                    class="text-left text-xs font-medium text-primary-600 hover:text-primary-500 dark:text-primary-300"
                    @click="selectedTrackId = documentFromRow(row).track_id || ''"
                  >
                    {{ shortId(documentFromRow(row).track_id || '') }}
                  </button>
                  <span
                    v-else
                    class="text-xs text-gray-400"
                  >--</span>
                </template>

                <template #cell-updated_at="{ row }">
                  <span class="text-xs text-gray-500 dark:text-dark-400">
                    {{ formatDateTime(documentFromRow(row).updated_at) }}
                  </span>
                </template>

                <template #cell-actions="{ row }">
                  <BaseButton
                    variant="ghost"
                    :disabled="!canWrite || actionLoading"
                    @click="requestDelete(documentFromRow(row))"
                  >
                    删除
                  </BaseButton>
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
                :disabled="loading || actionLoading"
                @update:page="pagination.setPage"
                @update:page-size="pagination.setPageSize"
              />
            </template>
          </TablePageLayout>
        </template>
      </div>

      <div class="space-y-4">
        <SurfaceCard>
          <div class="text-xs font-semibold uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
            Pipeline Summary
          </div>
          <div class="mt-3 flex items-center justify-between gap-3">
            <div class="text-lg font-semibold text-gray-900 dark:text-white">
              {{ pipelineStatus?.job_name || 'Idle' }}
            </div>
            <StatusPill :tone="pipelineStatus?.busy ? 'warning' : 'success'">
              {{ pipelineStatus?.busy ? 'BUSY' : 'IDLE' }}
            </StatusPill>
          </div>
          <p class="mt-3 text-sm leading-6 text-gray-500 dark:text-dark-300">
            {{ pipelineStatus?.latest_message || '当前没有正在运行的知识处理任务。' }}
          </p>
          <div class="mt-3 text-xs text-gray-400 dark:text-dark-500">
            docs={{ pipelineStatus?.docs || 0 }} · batch={{ pipelineStatus?.cur_batch || 0 }}/{{ pipelineStatus?.batchs || 0 }}
          </div>
          <div class="mt-4 text-xs text-gray-500 dark:text-dark-400">
            scan={{ scanProgress?.is_scanning ? `${scanProgress?.progress || 0}%` : 'idle' }} ·
            failed={{ failedCount }}
          </div>
        </SurfaceCard>

        <SurfaceCard>
          <div class="flex items-center justify-between gap-3">
            <div>
              <div class="text-xs font-semibold uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
                Track Status
              </div>
              <div class="mt-2 text-sm font-semibold text-gray-900 dark:text-white">
                {{ selectedTrackId ? shortId(selectedTrackId) : '未选择 track' }}
              </div>
            </div>
            <BaseButton
              variant="secondary"
              :disabled="!selectedTrackId"
              @click="void loadTrackStatus()"
            >
              刷新 Track
            </BaseButton>
          </div>
          <div
            v-if="trackOptions.length"
            class="mt-4"
          >
            <BaseSelect v-model="selectedTrackId">
              <option
                v-for="trackId in trackOptions"
                :key="trackId"
                :value="trackId"
              >
                {{ shortId(trackId) }}
              </option>
            </BaseSelect>
          </div>
          <template v-if="trackStatus && trackStatus.documents.length > 0">
            <div class="mt-4 space-y-3">
              <div
                v-for="doc in trackStatus.documents"
                :key="doc.id"
                class="rounded-2xl border border-gray-100 px-4 py-3 dark:border-dark-800"
              >
                <div class="flex items-center justify-between gap-3">
                  <div class="text-sm font-medium text-gray-900 dark:text-white">
                    {{ doc.file_path || doc.id }}
                  </div>
                  <StatusPill :tone="statusTone(doc.status)">
                    {{ doc.status }}
                  </StatusPill>
                </div>
                <div
                  v-if="doc.error_msg"
                  class="mt-2 text-xs text-rose-500"
                >
                  {{ doc.error_msg }}
                </div>
              </div>
            </div>
          </template>
          <p
            v-else
            class="mt-4 text-sm text-gray-500 dark:text-dark-300"
          >
            上传或扫描后，选择一个 track 即可查看该批次文档处理状态。
          </p>
        </SurfaceCard>
      </div>
    </div>

    <KnowledgePipelineStatusDialog
      :show="showPipelineDialog"
      :pipeline-status="pipelineStatus"
      :scan-progress="scanProgress"
      :failed-count="failedCount"
      :action-loading="actionLoading"
      :can-write="canWrite"
      @close="showPipelineDialog = false"
      @refresh="void loadDocuments()"
      @retry-failed="void handleRetryFailed()"
      @cancel-pipeline="void handleCancelPipeline()"
    />

    <ConfirmDialog
      :show="showClearConfirm"
      title="确认清空知识文档？"
      message="清空会删除当前项目知识空间下的全部文档记录与索引结果。请确认这次操作只作用于当前 project。"
      confirm-text="确认清空"
      danger
      @cancel="showClearConfirm = false"
      @confirm="void confirmClearAll()"
    />
    <ConfirmDialog
      :show="Boolean(pendingDelete)"
      title="确认删除知识文档？"
      :message="pendingDelete ? `将删除文档：${pendingDelete.file_path || pendingDelete.id}` : '将删除当前选择的知识文档。'"
      confirm-text="确认删除"
      danger
      @cancel="pendingDelete = null"
      @confirm="void confirmDelete()"
    />
    <BaseDialog
      :show="Boolean(selectedDocument)"
      title="文档详情"
      width="wide"
      @close="selectedDocument = null; selectedDocumentDetail = null"
    >
      <template v-if="selectedDocument">
        <div class="space-y-4">
          <div class="grid gap-4 md:grid-cols-2">
            <div class="rounded-2xl border border-gray-100 bg-gray-50/80 px-4 py-3 dark:border-dark-800 dark:bg-dark-900/70">
              <div class="text-xs uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
                文件
              </div>
              <div class="mt-2 text-sm font-medium text-gray-900 dark:text-white">
                {{ selectedDocument.file_path || selectedDocument.id }}
              </div>
            </div>
            <div class="rounded-2xl border border-gray-100 bg-gray-50/80 px-4 py-3 dark:border-dark-800 dark:bg-dark-900/70">
              <div class="text-xs uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
                状态
              </div>
              <div class="mt-2">
                <StatusPill :tone="statusTone(selectedDocument.status)">
                  {{ selectedDocument.status }}
                </StatusPill>
              </div>
            </div>
            <div class="rounded-2xl border border-gray-100 bg-gray-50/80 px-4 py-3 dark:border-dark-800 dark:bg-dark-900/70">
              <div class="text-xs uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
                Track
              </div>
              <div class="mt-2 text-sm font-medium text-gray-900 dark:text-white">
                {{ selectedDocument.track_id || '--' }}
              </div>
            </div>
            <div class="rounded-2xl border border-gray-100 bg-gray-50/80 px-4 py-3 dark:border-dark-800 dark:bg-dark-900/70">
              <div class="text-xs uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
                更新时间
              </div>
              <div class="mt-2 text-sm font-medium text-gray-900 dark:text-white">
                {{ formatDateTime(selectedDocument.updated_at) }}
              </div>
            </div>
          </div>

          <div class="rounded-2xl border border-gray-100 bg-gray-50/80 px-4 py-4 dark:border-dark-800 dark:bg-dark-900/70">
            <div class="text-xs uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
              解析摘要
            </div>
            <div class="mt-3 whitespace-pre-wrap text-sm leading-6 text-gray-700 dark:text-dark-200">
              {{ String((selectedDocumentDetail?.content_summary as string) || selectedDocument.content_summary || '当前没有更详细的内容摘要。') }}
            </div>
          </div>

          <div class="rounded-2xl border border-gray-100 bg-gray-50/80 px-4 py-4 dark:border-dark-800 dark:bg-dark-900/70">
            <div class="text-xs uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
              全文
            </div>
            <div class="mt-3 whitespace-pre-wrap text-sm leading-6 text-gray-700 dark:text-dark-200">
              {{ String((selectedDocumentDetail?.full_content as string) || '当前接口还没有返回完整全文。') }}
            </div>
          </div>

          <div
            v-if="Array.isArray(selectedDocumentDetail?.chunks) && selectedDocumentDetail?.chunks.length"
            class="rounded-2xl border border-gray-100 bg-gray-50/80 px-4 py-4 dark:border-dark-800 dark:bg-dark-900/70"
          >
            <div class="text-xs uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
              Chunks
            </div>
            <div class="mt-3 space-y-3">
              <div
                v-for="chunk in (selectedDocumentDetail?.chunks as Array<Record<string, unknown>>)"
                :key="String(chunk.chunk_id || chunk.reference_id || chunk.content)"
                class="rounded-2xl border border-gray-100 bg-white px-4 py-3 dark:border-dark-800 dark:bg-dark-950/70"
              >
                <div class="text-xs text-gray-400 dark:text-dark-500">
                  {{ String(chunk.chunk_id || '--') }}
                </div>
                <div class="mt-2 whitespace-pre-wrap text-sm leading-6 text-gray-700 dark:text-dark-200">
                  {{ String(chunk.content || '') }}
                </div>
              </div>
            </div>
          </div>

          <div
            v-if="selectedDocument.error_msg"
            class="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-4 text-sm text-rose-600 dark:border-rose-900/50 dark:bg-rose-950/20 dark:text-rose-300"
          >
            {{ selectedDocument.error_msg }}
          </div>

          <div class="rounded-2xl border border-gray-100 bg-gray-950 px-4 py-4 text-xs leading-6 text-gray-100 dark:border-dark-800">
            <div class="mb-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-gray-400">
              Metadata
            </div>
            <pre class="overflow-auto whitespace-pre-wrap break-all">{{ JSON.stringify((selectedDocumentDetail?.metadata as Record<string, unknown>) || selectedDocument.metadata || {}, null, 2) }}</pre>
          </div>
        </div>
      </template>
    </BaseDialog>
  </section>
</template>

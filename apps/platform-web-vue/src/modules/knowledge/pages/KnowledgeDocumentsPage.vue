<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import ConfirmDialog from '@/components/base/ConfirmDialog.vue'
import BaseSelect from '@/components/base/BaseSelect.vue'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import EmptyState from '@/components/platform/EmptyState.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import StatusPill from '@/components/platform/StatusPill.vue'
import { useAuthorization } from '@/composables/useAuthorization'
import { useKnowledgeProjectRoute } from '@/modules/knowledge/composables/useKnowledgeProjectRoute'
import KnowledgeWorkspaceNav from '@/modules/knowledge/components/KnowledgeWorkspaceNav.vue'
import {
  clearProjectKnowledgeDocuments,
  deleteProjectKnowledgeDocument,
  getProjectKnowledgePipelineStatus,
  getProjectKnowledgeTrackStatus,
  listProjectKnowledgeDocuments,
  startProjectKnowledgeScan,
  uploadProjectKnowledgeDocument
} from '@/services/knowledge/knowledge.service'
import { waitForOperationTerminalState } from '@/services/operations/operations.service'
import { useUiStore } from '@/stores/ui'
import type { KnowledgeDocument, KnowledgePipelineStatus, KnowledgeTrackStatus } from '@/types/management'
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
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const pipelineStatus = ref<KnowledgePipelineStatus | null>(null)
const selectedTrackId = ref('')
const trackStatus = ref<KnowledgeTrackStatus | null>(null)
const uploadInput = ref<HTMLInputElement | null>(null)
const showClearConfirm = ref(false)
const pendingDelete = ref<KnowledgeDocument | null>(null)

const canRead = computed(() => authorization.can('project.knowledge.read', projectId.value))
const canWrite = computed(() => authorization.can('project.knowledge.write', projectId.value))
const canAdmin = computed(() => authorization.can('project.knowledge.admin', projectId.value))
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

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
    total.value = 0
    statusCounts.value = {}
    pipelineStatus.value = null
    trackStatus.value = null
    return
  }

  loading.value = true
  error.value = ''
  try {
    const [pagePayload, pipeline] = await Promise.all([
      listProjectKnowledgeDocuments(projectId.value, {
        page: page.value,
        page_size: pageSize.value,
        status_filter: statusFilter.value || undefined
      }),
      getProjectKnowledgePipelineStatus(projectId.value)
    ])
    items.value = pagePayload.documents
    total.value = pagePayload.pagination.total_count
    statusCounts.value = pagePayload.status_counts || {}
    pipelineStatus.value = pipeline
  } catch (loadError) {
    items.value = []
    total.value = 0
    statusCounts.value = {}
    error.value = resolvePlatformHttpErrorMessage(loadError, '知识文档加载失败', '知识文档')
  } finally {
    loading.value = false
  }
}

async function handleUploadChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!projectId.value || !file) {
    return
  }
  actionLoading.value = true
  error.value = ''
  successMessage.value = ''
  try {
    const result = await uploadProjectKnowledgeDocument(projectId.value, file)
    const trackId = String(result.track_id || '').trim()
    selectedTrackId.value = trackId
    if (trackId) {
      await loadTrackStatus()
    }
    await loadDocuments()
    successMessage.value = String(result.message || '文档上传已提交。')
    uiStore.pushToast({
      type: 'success',
      title: '上传成功',
      message: successMessage.value
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
      timeoutMs: 90000
    })
    const resultTrackId = String(finalOperation.result_payload?.track_id || '').trim()
    if (resultTrackId) {
      selectedTrackId.value = resultTrackId
      await loadTrackStatus()
    }
    successMessage.value = String(finalOperation.result_payload?.message || '扫描任务已提交。')
    await loadDocuments()
  } catch (scanError) {
    error.value = resolvePlatformHttpErrorMessage(scanError, '知识文档扫描失败', '知识文档')
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
      timeoutMs: 90000
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
  () => [projectId.value, statusFilter.value, page.value, pageSize.value],
  () => {
    void loadDocuments()
  },
  { immediate: true }
)
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Knowledge"
      :title="project ? `${project.name} · 知识文档` : '知识文档'"
      description="项目知识工作台统一走 platform-api-v2，页面只认 project_id，不直接感知 workspace_key。"
    >
      <template #actions>
        <BaseButton variant="secondary" @click="void loadDocuments()">
          刷新
        </BaseButton>
        <BaseButton variant="secondary" :disabled="!canWrite || actionLoading" @click="handleScan">
          扫描目录
        </BaseButton>
        <BaseButton variant="danger" :disabled="!canAdmin || actionLoading" @click="requestClearAll">
          清空文档
        </BaseButton>
        <BaseButton :disabled="!canWrite || actionLoading" @click="openUploadDialog">
          上传文档
        </BaseButton>
        <input ref="uploadInput" class="hidden" type="file" @change="handleUploadChange" />
      </template>
    </PageHeader>

    <KnowledgeWorkspaceNav v-if="projectId" :project-id="projectId" />

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

    <div class="mt-4 grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
      <div class="space-y-4">
        <SurfaceCard>
          <div class="flex flex-wrap items-center gap-3">
            <div class="min-w-[160px]">
              <div class="text-xs font-semibold uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
                文档筛选
              </div>
              <BaseSelect v-model="statusFilter">
                <option value="">全部状态</option>
                <option value="PENDING">PENDING</option>
                <option value="PROCESSING">PROCESSING</option>
                <option value="PREPROCESSED">PREPROCESSED</option>
                <option value="PROCESSED">PROCESSED</option>
                <option value="FAILED">FAILED</option>
              </BaseSelect>
            </div>
            <div class="flex flex-wrap gap-2 text-xs text-gray-500 dark:text-dark-400">
              <span v-for="(count, status) in statusCounts" :key="status" class="rounded-full border border-gray-200 px-3 py-1 dark:border-dark-700">
                {{ status }} · {{ count }}
              </span>
            </div>
          </div>
        </SurfaceCard>

        <template v-if="projectId && canRead">
          <SurfaceCard v-if="loading">
            <div class="text-sm text-gray-500 dark:text-dark-300">正在加载知识文档…</div>
          </SurfaceCard>
          <EmptyState
            v-else-if="items.length === 0"
            title="当前项目还没有知识文档"
            description="你可以先上传文档，或触发一次目录扫描，让项目知识空间开始建立自己的文档集合。"
            icon="file"
            action-label="上传第一份文档"
            @action="openUploadDialog"
          />
          <SurfaceCard v-else>
            <div class="overflow-x-auto">
              <table class="min-w-full divide-y divide-gray-200 text-sm dark:divide-dark-800">
                <thead>
                  <tr class="text-left text-xs uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
                    <th class="pb-3">文件</th>
                    <th class="pb-3">状态</th>
                    <th class="pb-3">Track</th>
                    <th class="pb-3">更新时间</th>
                    <th class="pb-3">操作</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-gray-100 dark:divide-dark-900/80">
                  <tr v-for="item in items" :key="item.id">
                    <td class="py-3 pr-4 align-top">
                      <div class="font-medium text-gray-900 dark:text-white">{{ item.file_path || item.id }}</div>
                      <div class="mt-1 text-xs text-gray-500 dark:text-dark-400">
                        {{ item.content_summary || '暂无摘要' }}
                      </div>
                    </td>
                    <td class="py-3 pr-4 align-top">
                      <StatusPill :tone="statusTone(item.status)">
                        {{ item.status }}
                      </StatusPill>
                    </td>
                    <td class="py-3 pr-4 align-top">
                      <button
                        v-if="item.track_id"
                        type="button"
                        class="text-xs font-medium text-primary-600 hover:text-primary-500 dark:text-primary-300"
                        @click="selectedTrackId = item.track_id || ''; void loadTrackStatus()"
                      >
                        {{ shortId(item.track_id || '') }}
                      </button>
                      <span v-else class="text-xs text-gray-400">--</span>
                    </td>
                    <td class="py-3 pr-4 align-top text-xs text-gray-500 dark:text-dark-400">
                      {{ formatDateTime(item.updated_at) }}
                    </td>
                    <td class="py-3 align-top">
                      <BaseButton
                        variant="ghost"
                        :disabled="!canWrite || actionLoading"
                        @click="requestDelete(item)"
                      >
                        删除
                      </BaseButton>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="mt-4 flex items-center justify-between text-xs text-gray-500 dark:text-dark-400">
              <span>共 {{ total }} 条 · 第 {{ page }} / {{ totalPages }} 页</span>
              <div class="flex gap-2">
                <BaseButton variant="secondary" :disabled="page <= 1" @click="page -= 1">上一页</BaseButton>
                <BaseButton variant="secondary" :disabled="page >= totalPages" @click="page += 1">下一页</BaseButton>
              </div>
            </div>
          </SurfaceCard>
        </template>
      </div>

      <div class="space-y-4">
        <SurfaceCard>
          <div class="flex items-center justify-between gap-3">
            <div>
              <div class="text-xs font-semibold uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">Pipeline Status</div>
              <div class="mt-2 text-lg font-semibold text-gray-900 dark:text-white">
                {{ pipelineStatus?.job_name || 'Idle' }}
              </div>
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
        </SurfaceCard>

        <SurfaceCard>
          <div class="flex items-center justify-between gap-3">
            <div>
              <div class="text-xs font-semibold uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">Track Status</div>
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
          <template v-if="trackStatus && trackStatus.documents.length > 0">
            <div class="mt-4 space-y-3">
              <div
                v-for="doc in trackStatus.documents"
                :key="doc.id"
                class="rounded-2xl border border-gray-100 px-4 py-3 dark:border-dark-800"
              >
                <div class="flex items-center justify-between gap-3">
                  <div class="text-sm font-medium text-gray-900 dark:text-white">{{ doc.file_path || doc.id }}</div>
                  <StatusPill :tone="statusTone(doc.status)">{{ doc.status }}</StatusPill>
                </div>
                <div v-if="doc.error_msg" class="mt-2 text-xs text-rose-500">{{ doc.error_msg }}</div>
              </div>
            </div>
          </template>
          <p v-else class="mt-4 text-sm text-gray-500 dark:text-dark-300">
            上传或扫描后，选择一个 track 即可查看该批次文档处理状态。
          </p>
        </SurfaceCard>
      </div>
    </div>

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
  </section>
</template>

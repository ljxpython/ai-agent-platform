<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseDialog from '@/components/base/BaseDialog.vue'
import BaseSelect from '@/components/base/BaseSelect.vue'
import type { KnowledgeUploadMetadata } from '@/types/management'
import { shortId } from '@/utils/format'

export type UploadResolvedRow = {
  rowId: string
  file: File
  metadata?: KnowledgeUploadMetadata
}

export type UploadBatchRowResult = {
  rowId: string
  status: 'success' | 'failed'
  errorMessage?: string
  trackId?: string
}

export type UploadBatchResult = {
  results: UploadBatchRowResult[]
  latestSuccessfulTrackId?: string
  summary: {
    succeeded: number
    failed: number
  }
}

type UploadDraftRow = {
  rowId: string
  file: File
  tagsMode: 'inherit' | 'replace'
  tags: string[]
  layerMode: 'inherit' | 'replace'
  layer: string
  submitStatus: 'idle' | 'submitting' | 'success' | 'failed'
  errorMessage: string
  lastTrackId?: string
}

const props = defineProps<{
  show: boolean
  submitting: boolean
  batchResult?: UploadBatchResult | null
}>()

const emit = defineEmits<{
  close: []
  submit: [{ rows: UploadResolvedRow[] }]
}>()

const fileInput = ref<HTMLInputElement | null>(null)
const defaultTagsText = ref('')
const defaultLayer = ref('')
const rows = ref<UploadDraftRow[]>([])
const activeRowId = ref<string | null>(null)

function createRowId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `upload-row-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function splitTags(raw: string) {
  return raw
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

const defaultTags = computed(() => splitTags(defaultTagsText.value))
const activeRow = computed(() => rows.value.find((item) => item.rowId === activeRowId.value) ?? null)
const pendingRows = computed(() => rows.value.filter((item) => item.submitStatus !== 'success'))
const failedRows = computed(() => rows.value.filter((item) => item.submitStatus === 'failed'))
const successfulTrackIds = computed(() =>
  rows.value
    .map((row) => row.lastTrackId?.trim() || '')
    .filter((value, index, collection) => value && collection.indexOf(value) === index),
)
const isSingleFile = computed(() => rows.value.length <= 1)
const canSubmit = computed(() => pendingRows.value.length > 0 && !props.submitting)

function effectiveMetadata(row: UploadDraftRow): KnowledgeUploadMetadata | undefined {
  const tags = row.tagsMode === 'inherit' ? defaultTags.value : row.tags
  const layer = row.layerMode === 'inherit' ? defaultLayer.value.trim() : row.layer.trim()

  const metadata: KnowledgeUploadMetadata = {}
  if (row.tagsMode === 'replace' || tags.length) {
    metadata.tags = tags
  }
  if (row.layerMode === 'replace' || layer) {
    metadata.attributes = { layer }
  }

  return Object.keys(metadata).length ? metadata : undefined
}

function markDraftsPendingSubmission() {
  rows.value = rows.value.map((row) =>
    row.submitStatus === 'success'
      ? row
      : {
          ...row,
          submitStatus: 'submitting',
          errorMessage: '',
        },
  )
}

function resetDialog() {
  defaultTagsText.value = ''
  defaultLayer.value = ''
  rows.value = []
  activeRowId.value = null
  if (fileInput.value) {
    fileInput.value.value = ''
  }
}

function openPicker() {
  fileInput.value?.click()
}

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || [])
  if (!files.length) {
    return
  }

  const nextRows = files.map<UploadDraftRow>((file) => ({
    rowId: createRowId(),
    file,
    tagsMode: 'inherit',
    tags: [],
    layerMode: 'inherit',
    layer: '',
    submitStatus: 'idle',
    errorMessage: '',
  }))

  rows.value = [...rows.value, ...nextRows]
  if (!activeRowId.value) {
    activeRowId.value = nextRows[0]?.rowId || null
  }
  input.value = ''
}

function removeRow(rowId: string) {
  rows.value = rows.value.filter((row) => row.rowId !== rowId)
  if (activeRowId.value === rowId) {
    activeRowId.value = rows.value[0]?.rowId || null
  }
}

function submitRows() {
  markDraftsPendingSubmission()
  emit('submit', {
    rows: pendingRows.value.map((row) => ({
      rowId: row.rowId,
      file: row.file,
      metadata: effectiveMetadata(row),
    })),
  })
}

watch(
  () => props.show,
  (isOpen) => {
    if (!isOpen) {
      resetDialog()
    }
  },
)

watch(
  () => props.batchResult,
  (batchResult) => {
    if (!batchResult) {
      return
    }

    const patchMap = new Map(batchResult.results.map((item) => [item.rowId, item]))
    rows.value = rows.value.map((row) => {
      const result = patchMap.get(row.rowId)
      if (!result) {
        return row
      }
      return {
        ...row,
        submitStatus: result.status,
        errorMessage: result.errorMessage || '',
        lastTrackId: result.trackId,
      }
    })
  },
  { deep: true },
)
</script>

<template>
  <BaseDialog
    :show="show"
    title="上传知识文档"
    width="wide"
    :close-on-click-outside="!submitting"
    :close-on-escape="!submitting"
    @close="!submitting ? emit('close') : undefined"
  >
    <div class="space-y-5">
      <section class="space-y-3">
        <div class="flex items-center justify-between gap-3">
          <div>
            <div class="text-sm font-semibold text-gray-900 dark:text-white">
              第一步：选择文件
            </div>
            <div class="text-xs text-gray-500 dark:text-dark-400">
              先选择一个或多个文件，再在同一流程里确认 metadata。
            </div>
          </div>
          <BaseButton
            :disabled="submitting"
            @click="openPicker"
          >
            选择文件
          </BaseButton>
        </div>

        <input
          ref="fileInput"
          class="hidden"
          type="file"
          multiple
          @change="onFileChange"
        >

        <div
          v-if="rows.length === 0"
          class="rounded-2xl border border-dashed border-gray-200 px-4 py-6 text-sm text-gray-500 dark:border-dark-700 dark:text-dark-300"
        >
          还没有选择文件。先点“选择文件”，再继续填写默认值或逐文件修改。
        </div>
      </section>

      <template v-if="rows.length">
        <section class="space-y-3">
          <div class="text-sm font-semibold text-gray-900 dark:text-white">
            第二步：批量默认值
          </div>
          <div class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_220px]">
            <label class="flex flex-col gap-2 text-sm font-medium text-gray-700 dark:text-dark-200">
              默认 tags（逗号分隔）
              <input
                v-model="defaultTagsText"
                type="text"
                class="pw-input"
                placeholder="architecture, storage"
              >
            </label>
            <label class="flex flex-col gap-2 text-sm font-medium text-gray-700 dark:text-dark-200">
              默认 layer
              <BaseSelect v-model="defaultLayer">
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
          <div class="text-xs text-gray-400 dark:text-dark-500">
            默认值会作用于所有文件，除非在逐文件编辑里切换为“覆盖”。
          </div>
        </section>

        <section class="space-y-3">
          <div class="text-sm font-semibold text-gray-900 dark:text-white">
            第三步：逐文件确认
          </div>

          <div
            v-if="isSingleFile && activeRow"
            class="space-y-4 rounded-2xl border border-gray-100 px-4 py-4 dark:border-dark-800"
          >
            <div class="text-sm font-medium text-gray-900 dark:text-white">
              {{ activeRow.file.name }}
            </div>

            <label class="flex flex-col gap-2 text-sm font-medium text-gray-700 dark:text-dark-200">
              <span class="flex items-center gap-2">
                <input
                  v-model="activeRow.tagsMode"
                  type="radio"
                  value="inherit"
                >
                继承默认 tags
              </span>
              <span class="flex items-center gap-2">
                <input
                  v-model="activeRow.tagsMode"
                  type="radio"
                  value="replace"
                >
                覆盖 tags（可留空表示显式清空）
              </span>
              <input
                :value="activeRow.tags.join(', ')"
                type="text"
                class="pw-input"
                :disabled="activeRow.tagsMode !== 'replace'"
                placeholder="architecture, storage"
                @input="activeRow.tags = splitTags(($event.target as HTMLInputElement).value)"
              >
            </label>

            <label class="flex flex-col gap-2 text-sm font-medium text-gray-700 dark:text-dark-200">
              <span class="flex items-center gap-2">
                <input
                  v-model="activeRow.layerMode"
                  type="radio"
                  value="inherit"
                >
                继承默认 layer
              </span>
              <span class="flex items-center gap-2">
                <input
                  v-model="activeRow.layerMode"
                  type="radio"
                  value="replace"
                >
                覆盖 layer（可留空表示显式清空）
              </span>
              <BaseSelect
                :model-value="activeRow.layer"
                :disabled="activeRow.layerMode !== 'replace'"
                @update:model-value="activeRow.layer = String($event || '')"
              >
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

            <div
              v-if="activeRow.submitStatus === 'failed'"
              class="rounded-2xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-600 dark:border-rose-900/50 dark:bg-rose-950/20 dark:text-rose-300"
            >
              {{ activeRow.errorMessage || '上传失败，请调整后重试。' }}
            </div>
            <div
              v-else-if="activeRow.lastTrackId"
              class="rounded-2xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/20 dark:text-emerald-300"
            >
              Track: {{ shortId(activeRow.lastTrackId) }}
            </div>
          </div>

          <div
            v-else
            class="grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)]"
          >
            <div class="space-y-2 rounded-2xl border border-gray-100 p-3 dark:border-dark-800">
              <button
                v-for="row in rows"
                :key="row.rowId"
                type="button"
                class="w-full rounded-2xl border px-3 py-3 text-left transition"
                :class="row.rowId === activeRowId ? 'border-primary-300 bg-primary-50 dark:border-primary-900/60 dark:bg-primary-950/20' : 'border-gray-100 dark:border-dark-800'"
                @click="activeRowId = row.rowId"
              >
                <div class="text-sm font-medium text-gray-900 dark:text-white">
                  {{ row.file.name }}
                </div>
                <div class="mt-1 text-xs text-gray-500 dark:text-dark-400">
                  {{ row.submitStatus }}
                </div>
                <div
                  v-if="row.lastTrackId"
                  class="mt-1 text-xs text-emerald-600 dark:text-emerald-300"
                >
                  Track {{ shortId(row.lastTrackId) }}
                </div>
                <div
                  v-if="row.errorMessage"
                  class="mt-1 text-xs text-rose-500"
                >
                  {{ row.errorMessage }}
                </div>
              </button>
            </div>

            <div
              v-if="activeRow"
              class="space-y-4 rounded-2xl border border-gray-100 px-4 py-4 dark:border-dark-800"
            >
              <div class="flex items-center justify-between gap-3">
                <div class="text-sm font-medium text-gray-900 dark:text-white">
                  {{ activeRow.file.name }}
                </div>
                <BaseButton
                  variant="ghost"
                  :disabled="submitting"
                  @click="removeRow(activeRow.rowId)"
                >
                  移除
                </BaseButton>
              </div>

              <label class="flex flex-col gap-2 text-sm font-medium text-gray-700 dark:text-dark-200">
                <span class="flex items-center gap-2">
                  <input
                    v-model="activeRow.tagsMode"
                    type="radio"
                    value="inherit"
                  >
                  继承默认 tags
                </span>
                <span class="flex items-center gap-2">
                  <input
                    v-model="activeRow.tagsMode"
                    type="radio"
                    value="replace"
                  >
                  覆盖 tags（可留空表示显式清空）
                </span>
                <input
                  :value="activeRow.tags.join(', ')"
                  type="text"
                  class="pw-input"
                  :disabled="activeRow.tagsMode !== 'replace'"
                  placeholder="architecture, storage"
                  @input="activeRow.tags = splitTags(($event.target as HTMLInputElement).value)"
                >
              </label>

              <label class="flex flex-col gap-2 text-sm font-medium text-gray-700 dark:text-dark-200">
                <span class="flex items-center gap-2">
                  <input
                    v-model="activeRow.layerMode"
                    type="radio"
                    value="inherit"
                  >
                  继承默认 layer
                </span>
                <span class="flex items-center gap-2">
                  <input
                    v-model="activeRow.layerMode"
                    type="radio"
                    value="replace"
                  >
                  覆盖 layer（可留空表示显式清空）
                </span>
                <BaseSelect
                  :model-value="activeRow.layer"
                  :disabled="activeRow.layerMode !== 'replace'"
                  @update:model-value="activeRow.layer = String($event || '')"
                >
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

              <div
                v-if="activeRow.submitStatus === 'failed'"
                class="rounded-2xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-600 dark:border-rose-900/50 dark:bg-rose-950/20 dark:text-rose-300"
              >
                {{ activeRow.errorMessage || '上传失败，请调整后重试。' }}
              </div>
              <div
                v-else-if="activeRow.lastTrackId"
                class="rounded-2xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/20 dark:text-emerald-300"
              >
                Track: {{ shortId(activeRow.lastTrackId) }}
              </div>
            </div>
          </div>
        </section>
      </template>
    </div>

    <template #footer>
      <div class="flex w-full items-center justify-between gap-3">
        <div class="space-y-1 text-xs text-gray-500 dark:text-dark-400">
          <div>
            {{ rows.length }} 个文件 · 待提交 {{ pendingRows.length }} 个 · 失败 {{ failedRows.length }} 个
          </div>
          <div v-if="successfulTrackIds.length">
            本次成功 Track：{{ successfulTrackIds.map((item) => shortId(item)).join('，') }}
          </div>
        </div>
        <div class="flex items-center gap-3">
          <BaseButton
            variant="secondary"
            :disabled="submitting"
            @click="emit('close')"
          >
            取消
          </BaseButton>
          <BaseButton
            :disabled="!canSubmit"
            @click="submitRows"
          >
            {{ failedRows.length ? '重试失败项 / 继续上传' : '确认上传' }}
          </BaseButton>
        </div>
      </div>
    </template>
  </BaseDialog>
</template>

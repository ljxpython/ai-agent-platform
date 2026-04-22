<script setup lang="ts">
import BaseButton from '@/components/base/BaseButton.vue'
import BaseDialog from '@/components/base/BaseDialog.vue'
import StatusPill from '@/components/platform/StatusPill.vue'
import type { KnowledgeDocumentsScanProgress, KnowledgePipelineStatus } from '@/types/management'

withDefaults(
  defineProps<{
    show: boolean
    pipelineStatus: KnowledgePipelineStatus | null
    scanProgress: KnowledgeDocumentsScanProgress | null
    failedCount?: number
    actionLoading?: boolean
    canWrite?: boolean
  }>(),
  {
    failedCount: 0,
    actionLoading: false,
    canWrite: false
  }
)

const emit = defineEmits<{
  close: []
  refresh: []
  retryFailed: []
  cancelPipeline: []
}>()
</script>

<template>
  <BaseDialog
    :show="show"
    title="流水线状态"
    width="wide"
    @close="emit('close')"
  >
    <div class="space-y-5">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div class="text-xs font-semibold uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
            Pipeline
          </div>
          <div class="mt-2 text-lg font-semibold text-gray-900 dark:text-white">
            {{ pipelineStatus?.job_name || 'Idle' }}
          </div>
        </div>
        <div class="flex items-center gap-2">
          <StatusPill :tone="pipelineStatus?.busy ? 'warning' : 'success'">
            {{ pipelineStatus?.busy ? 'BUSY' : 'IDLE' }}
          </StatusPill>
          <StatusPill
            v-if="pipelineStatus?.request_pending"
            tone="warning"
          >
            request pending
          </StatusPill>
          <StatusPill
            v-if="pipelineStatus?.cancellation_requested"
            tone="danger"
          >
            cancelling
          </StatusPill>
        </div>
      </div>

      <div class="grid gap-4 md:grid-cols-3">
        <div class="rounded-2xl border border-gray-100 bg-gray-50/70 px-4 py-3 text-sm dark:border-dark-800 dark:bg-dark-900/70">
          <div class="text-xs uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
            当前任务
          </div>
          <div class="mt-2 break-words text-gray-900 dark:text-white">
            {{ pipelineStatus?.job_name || '当前没有运行中的任务' }}
          </div>
        </div>
        <div class="rounded-2xl border border-gray-100 bg-gray-50/70 px-4 py-3 text-sm dark:border-dark-800 dark:bg-dark-900/70">
          <div class="text-xs uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
            Batch 进度
          </div>
          <div class="mt-2 text-gray-900 dark:text-white">
            {{ pipelineStatus?.cur_batch || 0 }} / {{ pipelineStatus?.batchs || 0 }}
          </div>
          <div class="mt-1 text-xs text-gray-500 dark:text-dark-400">
            docs={{ pipelineStatus?.docs || 0 }}
          </div>
        </div>
        <div class="rounded-2xl border border-gray-100 bg-gray-50/70 px-4 py-3 text-sm dark:border-dark-800 dark:bg-dark-900/70">
          <div class="text-xs uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
            扫描进度
          </div>
          <div class="mt-2 text-gray-900 dark:text-white">
            {{ scanProgress?.is_scanning ? `${scanProgress?.progress || 0}%` : '未扫描 / 已完成' }}
          </div>
          <div class="mt-1 text-xs text-gray-500 dark:text-dark-400">
            {{ scanProgress?.current_file || '当前没有扫描中的文件' }}
          </div>
        </div>
      </div>

      <div class="rounded-2xl border border-gray-100 bg-gray-50/70 px-4 py-3 text-sm dark:border-dark-800 dark:bg-dark-900/70">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div class="text-xs uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
              最新状态
            </div>
            <div class="mt-2 text-gray-900 dark:text-white">
              {{ pipelineStatus?.latest_message || '当前没有新的流水线状态。' }}
            </div>
          </div>
          <div class="flex flex-wrap gap-2">
            <BaseButton
              variant="secondary"
              :disabled="actionLoading"
              @click="emit('refresh')"
            >
              刷新状态
            </BaseButton>
            <BaseButton
              variant="secondary"
              :disabled="!canWrite || actionLoading || failedCount <= 0"
              @click="emit('retryFailed')"
            >
              重试失败文档
            </BaseButton>
            <BaseButton
              variant="danger"
              :disabled="!canWrite || actionLoading || !pipelineStatus?.busy"
              @click="emit('cancelPipeline')"
            >
              取消流水线
            </BaseButton>
          </div>
        </div>
      </div>

      <div class="rounded-2xl border border-gray-100 bg-gray-950 px-4 py-4 text-xs leading-6 text-gray-100 dark:border-dark-800">
        <div class="mb-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-gray-400">
          History Messages
        </div>
        <div class="max-h-[360px] overflow-y-auto space-y-1 whitespace-pre-wrap break-words">
          <div
            v-for="(message, index) in pipelineStatus?.history_messages || []"
            :key="`${index}-${message}`"
          >
            {{ message }}
          </div>
          <div
            v-if="!(pipelineStatus?.history_messages || []).length"
            class="text-gray-400"
          >
            当前还没有历史流水线消息。
          </div>
        </div>
      </div>
    </div>
  </BaseDialog>
</template>

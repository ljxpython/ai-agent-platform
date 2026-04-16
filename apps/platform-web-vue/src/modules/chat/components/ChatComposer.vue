<script setup lang="ts">
import { computed, ref } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import { CHAT_ATTACHMENT_ACCEPT, type ChatAttachmentBlock } from '@/utils/chat-content'
import ChatAttachmentPreview from './ChatAttachmentPreview.vue'
import ChatInterruptPanel from './ChatInterruptPanel.vue'

const props = defineProps<{
  modelValue: string
  attachments: ChatAttachmentBlock[]
  isRunning: boolean
  hasBlockingInterrupt: boolean
  interruptPayload: unknown
  canStartThread: boolean
  showContinueAction: boolean
  canSendFreshMessage: boolean
  cancelling: boolean
  sendButtonLabel: string
  lastEventAt: string
  onResumeInterruptedRun: (resumePayload: unknown) => Promise<boolean>
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  'send': []
  'cancel': []
  'continue-run': []
  'new-thread': []
  'file-input-change': [event: Event]
  'composer-paste': [event: ClipboardEvent]
  'remove-attachment': [index: number]
}>()

const fileInputRef = ref<HTMLInputElement | null>(null)

const composerModel = computed({
  get: () => props.modelValue,
  set: (value: string) => emit('update:modelValue', value)
})

const helperText = computed(() =>
  props.hasBlockingInterrupt
    ? '当前运行正在等待人工决策。你可以先编辑下一条消息草稿，处理完中断后再发送。'
    : props.isRunning
      ? 'Agent 正在实时输出。你可以继续编辑下一条消息草稿，或随时点击“停止生成”。'
      : props.lastEventAt
        ? `最近响应：${props.lastEventAt}`
        : '支持 JPEG、PNG、GIF、WEBP、PDF，也支持直接粘贴图片。'
)

function handleComposerPaste(event: ClipboardEvent) {
  emit('composer-paste', event)
}

function openFilePicker() {
  fileInputRef.value?.click()
}
</script>

<template>
  <div class="border-t border-gray-100 px-6 py-5 dark:border-dark-800">
    <div class="pw-panel p-4">
      <ChatInterruptPanel
        v-if="hasBlockingInterrupt"
        :interrupt="interruptPayload"
        :submitting="isRunning"
        :on-resume="onResumeInterruptedRun"
      />

      <div
        v-if="attachments.length > 0"
        class="mb-4 flex flex-wrap gap-3"
      >
        <ChatAttachmentPreview
          v-for="(attachment, index) in attachments"
          :key="`composer-attachment-${index}`"
          :block="attachment"
          removable
          @remove="emit('remove-attachment', index)"
        />
      </div>

      <textarea
        v-model="composerModel"
        rows="5"
        class="pw-input min-h-[132px] resize-none border-0 bg-transparent px-0 py-0 shadow-none focus:ring-0"
        placeholder="输入消息。只有点击发送按钮时才会真正提交。"
        @paste="handleComposerPaste"
      />

      <div class="mt-4 flex flex-wrap items-center justify-between gap-3">
        <div class="flex flex-wrap items-center gap-3 text-xs leading-6 text-gray-400 dark:text-dark-400">
          <button
            type="button"
            class="pw-table-tool-button h-9 rounded-lg px-3 text-xs"
            :disabled="isRunning || hasBlockingInterrupt"
            @click="openFilePicker"
          >
            <BaseIcon
              name="paperclip"
              size="sm"
            />
            <span>上传图片 / PDF</span>
          </button>
          <input
            ref="fileInputRef"
            type="file"
            class="hidden"
            multiple
            :accept="CHAT_ATTACHMENT_ACCEPT"
            @change="emit('file-input-change', $event)"
          >
          <span>{{ helperText }}</span>
        </div>
        <div class="flex flex-wrap items-center gap-3">
          <BaseButton
            variant="secondary"
            :disabled="!canStartThread"
            @click="emit('new-thread')"
          >
            空白对话
          </BaseButton>
          <BaseButton
            v-if="showContinueAction"
            variant="secondary"
            @click="emit('continue-run')"
          >
            <BaseIcon
              name="chevron-right"
              size="sm"
            />
            Continue
          </BaseButton>
          <BaseButton
            :variant="isRunning ? 'danger' : 'primary'"
            :disabled="isRunning ? cancelling : !canSendFreshMessage"
            @click="isRunning ? emit('cancel') : emit('send')"
          >
            <BaseIcon
              :name="isRunning ? 'x' : 'chat'"
              size="sm"
            />
            {{
              isRunning
                ? cancelling
                  ? '停止中...'
                  : '停止生成'
                : sendButtonLabel
            }}
          </BaseButton>
        </div>
      </div>
    </div>
  </div>
</template>

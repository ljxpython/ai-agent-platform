<script setup lang="ts">
import type { Message } from '@langchain/langgraph-sdk'
import MarkdownContent from '@/components/platform/MarkdownContent.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import { getMessageAttachments, getMessageText } from '@/utils/threads'
import type { ChatDisplayMessage } from '../message-view-model'
import ChatAttachmentPreview from './ChatAttachmentPreview.vue'
import ChatMessageMeta from './ChatMessageMeta.vue'

type BranchMeta = {
  branch?: string
  branchOptions?: string[]
}

defineProps<{
  displayMessages: ChatDisplayMessage[]
  allMessages: Message[]
  editingMessageId: string
  editingMessageValue: string
  isRunning: boolean
  getMessageMeta: (messageId: string) => BranchMeta | undefined
  getMessageBranchIndex: (messageId: string) => number
  hasBranchSwitcher: (messageId: string) => boolean
  canEditMessage: (message: Message, messageId: string) => boolean
  canRetryMessage: (message: Message, messageId: string) => boolean
}>()

const emit = defineEmits<{
  'update:editingMessageValue': [value: string]
  'copy-message': [message: Message]
  'cancel-edit': []
  'submit-edit': [message: Message, messageId: string]
  'start-edit': [message: Message, messageId: string]
  'retry-message': [messageId: string]
  'select-previous-branch': [messageId: string]
  'select-next-branch': [messageId: string]
}>()

function handleEditingInput(event: Event) {
  emit('update:editingMessageValue', (event.target as HTMLTextAreaElement | null)?.value || '')
}
</script>

<template>
  <div class="space-y-5">
    <div
      v-for="displayEntry in displayMessages"
      :key="displayEntry.id"
      class="flex flex-col gap-2"
      :class="displayEntry.wrapClass"
    >
      <div class="text-xs font-semibold uppercase tracking-[0.14em] text-gray-400 dark:text-dark-400">
        {{ displayEntry.roleLabel }}
      </div>
      <div
        class="max-w-[88%] rounded-[24px] border px-4 py-3 shadow-soft"
        :class="displayEntry.bubbleClass"
      >
        <div
          v-if="getMessageAttachments(displayEntry.message.content).length > 0"
          class="flex flex-wrap gap-3"
          :class="displayEntry.message.type === 'human' ? 'justify-end' : ''"
        >
          <ChatAttachmentPreview
            v-for="(attachment, attachmentIndex) in getMessageAttachments(displayEntry.message.content)"
            :key="`${displayEntry.id}-attachment-${attachmentIndex}`"
            :block="attachment"
            compact
          />
        </div>
        <textarea
          v-if="editingMessageId === displayEntry.id"
          :value="editingMessageValue"
          rows="5"
          class="pw-input resize-y border-0 bg-transparent px-0 py-0 text-sm leading-7 shadow-none focus:ring-0"
          :class="getMessageAttachments(displayEntry.message.content).length > 0 ? 'mt-3' : ''"
          @input="handleEditingInput"
        />
        <pre
          v-else-if="displayEntry.message.type !== 'ai' && getMessageText(displayEntry.message.content)"
          class="whitespace-pre-wrap break-words text-sm leading-7"
          :class="getMessageAttachments(displayEntry.message.content).length > 0 ? 'mt-3' : ''"
        >{{ getMessageText(displayEntry.message.content) }}</pre>
        <MarkdownContent
          v-else-if="getMessageText(displayEntry.message.content)"
          :content="getMessageText(displayEntry.message.content)"
          :class="getMessageAttachments(displayEntry.message.content).length > 0 ? 'mt-3' : ''"
        />
        <div
          v-else-if="getMessageAttachments(displayEntry.message.content).length === 0"
          class="text-sm leading-7 text-gray-500 dark:text-dark-300"
        >
          当前消息没有可渲染的文本内容。
        </div>
        <div v-if="displayEntry.message.type === 'ai'">
          <ChatMessageMeta
            :message="displayEntry.message"
            :all-messages="allMessages"
            :default-expanded="isRunning"
          />
        </div>
      </div>

      <div
        class="flex max-w-[88%] flex-wrap items-center gap-2 text-xs"
        :class="displayEntry.message.type === 'human' ? 'justify-end self-end' : 'justify-start self-start'"
      >
        <template v-if="editingMessageId === displayEntry.id">
          <button
            type="button"
            class="rounded-full border border-gray-200 px-3 py-1.5 font-medium text-gray-600 transition hover:border-gray-300 hover:bg-gray-50 hover:text-gray-900 dark:border-dark-700 dark:text-dark-200 dark:hover:bg-dark-800"
            @click="emit('cancel-edit')"
          >
            取消编辑
          </button>
          <button
            type="button"
            class="rounded-full bg-primary-600 px-3 py-1.5 font-medium text-white transition hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="isRunning"
            @click="emit('submit-edit', displayEntry.message, displayEntry.id)"
          >
            提交重发
          </button>
        </template>

        <template v-else>
          <button
            type="button"
            class="rounded-full border border-gray-200 px-3 py-1.5 font-medium text-gray-600 transition hover:border-gray-300 hover:bg-gray-50 hover:text-gray-900 dark:border-dark-700 dark:text-dark-200 dark:hover:bg-dark-800"
            @click="emit('copy-message', displayEntry.message)"
          >
            复制
          </button>
          <button
            v-if="canEditMessage(displayEntry.message, displayEntry.id)"
            type="button"
            class="rounded-full border border-gray-200 px-3 py-1.5 font-medium text-gray-600 transition hover:border-gray-300 hover:bg-gray-50 hover:text-gray-900 dark:border-dark-700 dark:text-dark-200 dark:hover:bg-dark-800"
            @click="emit('start-edit', displayEntry.message, displayEntry.id)"
          >
            编辑
          </button>
          <button
            v-if="canRetryMessage(displayEntry.message, displayEntry.id)"
            type="button"
            class="rounded-full border border-gray-200 px-3 py-1.5 font-medium text-gray-600 transition hover:border-gray-300 hover:bg-gray-50 hover:text-gray-900 dark:border-dark-700 dark:text-dark-200 dark:hover:bg-dark-800"
            @click="emit('retry-message', displayEntry.id)"
          >
            重试
          </button>

          <div
            v-if="hasBranchSwitcher(displayEntry.id)"
            class="inline-flex items-center gap-2 rounded-full border border-gray-200 px-2 py-1 dark:border-dark-700"
          >
            <button
              type="button"
              class="rounded-full p-1 text-gray-500 transition hover:bg-gray-100 hover:text-gray-900 disabled:cursor-not-allowed disabled:opacity-40 dark:text-dark-300 dark:hover:bg-dark-800 dark:hover:text-white"
              :disabled="getMessageBranchIndex(displayEntry.id) <= 0 || isRunning"
              @click="emit('select-previous-branch', displayEntry.id)"
            >
              <BaseIcon
                name="chevron-left"
                size="xs"
              />
            </button>
            <span class="min-w-[64px] text-center font-medium text-gray-500 dark:text-dark-300">
              {{ getMessageBranchIndex(displayEntry.id) + 1 }} /
              {{ getMessageMeta(displayEntry.id)?.branchOptions?.length }}
            </span>
            <button
              type="button"
              class="rounded-full p-1 text-gray-500 transition hover:bg-gray-100 hover:text-gray-900 disabled:cursor-not-allowed disabled:opacity-40 dark:text-dark-300 dark:hover:bg-dark-800 dark:hover:text-white"
              :disabled="
                getMessageBranchIndex(displayEntry.id) >=
                  ((getMessageMeta(displayEntry.id)?.branchOptions?.length ?? 1) - 1) || isRunning
              "
              @click="emit('select-next-branch', displayEntry.id)"
            >
              <BaseIcon
                name="chevron-right"
                size="xs"
              />
            </button>
          </div>
        </template>
      </div>
    </div>

    <div
      v-if="isRunning"
      class="flex items-start"
    >
      <div class="rounded-[24px] border border-white/70 bg-white/95 px-4 py-3 shadow-soft dark:border-dark-700 dark:bg-dark-900/85">
        <div class="flex items-center gap-2 text-sm text-gray-500 dark:text-dark-300">
          <span class="h-2 w-2 animate-pulse rounded-full bg-primary-400" />
          <span class="h-2 w-2 animate-pulse rounded-full bg-primary-300 [animation-delay:120ms]" />
          <span class="h-2 w-2 animate-pulse rounded-full bg-primary-200 [animation-delay:240ms]" />
          <span>正在生成回复...</span>
        </div>
      </div>
    </div>
  </div>
</template>

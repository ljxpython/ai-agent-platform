<script setup lang="ts">
import type { Message } from '@langchain/langgraph-sdk'
import type { AssembledToolCall, AnyStream, MessageMetadata } from '@langchain/vue'
import MarkdownContent from '@/components/platform/MarkdownContent.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import type { ChatMessageMetadata } from '../branching'
import type { AgentDisplayMessage } from '../agent-types'
import ChatToolCallCard from './ChatToolCallCard.vue'
import ChatReasoningBlock from './ChatReasoningBlock.vue'
import ChatMessageRuntimeMetadata from './ChatMessageRuntimeMetadata.vue'

const props = defineProps<{
  displayMessages: AgentDisplayMessage[]
  allMessages: Message[]
  editingMessageId: string
  editingMessageValue: string
  isRunning: boolean
  streamHandle: AnyStream
  toolCalls: AssembledToolCall[]
  getMessageMeta: (messageId: string) => ChatMessageMetadata | undefined
  getMessageBranchIndex: (messageId: string) => number
  hasBranchSwitcher: (messageId: string) => boolean
  canEditMessage: (message: Message, messageId: string, parentCheckpointId?: string) => boolean
  canRetryMessage: (message: Message, messageId: string, parentCheckpointId?: string) => boolean
}>()

const emit = defineEmits<{
  'update:editingMessageValue': [value: string]
  'copy-message': [message: Message]
  'cancel-edit': []
  'submit-edit': [message: Message, messageId: string, parentCheckpointId?: string]
  'start-edit': [message: Message, messageId: string]
  'retry-message': [messageId: string, parentCheckpointId?: string]
  'select-previous-branch': [messageId: string]
  'select-next-branch': [messageId: string]
  'message-meta-expanded-change': [messageId: string, expanded: boolean]
}>()

function handleEditingInput(event: Event) {
  emit('update:editingMessageValue', (event.target as HTMLTextAreaElement | null)?.value || '')
}

function getOriginalMessage(id: string): Message | undefined {
  return props.allMessages.find(m => m.id === id)
}

import { computed, ref, watch } from 'vue'

// 强制刷新key，每次displayMessages变化时递增
const forceRefreshKey = ref(0)

watch(
  () => props.displayMessages,
  () => {
    // 每次messages更新时立即触发DOM刷新
    forceRefreshKey.value++
  },
  { deep: true }
)

const visibleDisplayMessages = computed(() =>
  props.displayMessages.filter((entry) => entry.chunks && entry.chunks.length > 0)
)

function getParentCheckpointId(messageId: string, runtimeMetadata?: MessageMetadata) {
  return (
    runtimeMetadata?.parentCheckpointId?.trim() ||
    props.getMessageMeta(messageId)?.parentCheckpoint?.checkpoint_id?.trim() ||
    undefined
  )
}
</script>

<template>
  <div class="space-y-8" :key="forceRefreshKey">
    <ChatMessageRuntimeMetadata
      v-for="displayEntry in visibleDisplayMessages"
      :key="displayEntry.id"
      v-slot="{ metadata }"
      :stream="streamHandle"
      :message-id="displayEntry.id"
    >
      <article
        class="pw-chat-turn"
        :class="displayEntry.author === 'user' ? 'items-end' : 'items-start'"
      >
        <div
          class="pw-chat-turn-heading"
          :class="displayEntry.author === 'user' ? 'self-end' : 'self-start'"
        >
          <template v-if="displayEntry.author === 'agent'">
            <span class="pw-chat-agent-mark">
              <BaseIcon name="chat" size="sm" />
            </span>
            <span class="font-semibold text-gray-900 dark:text-white">Agent</span>
          </template>
          <template v-else>
            <span class="font-medium text-gray-500 dark:text-dark-300">你</span>
          </template>
        </div>

        <div
          class="max-w-[780px]"
          :class="[
            displayEntry.author === 'user'
              ? 'w-auto self-end rounded-2xl rounded-tr-sm border border-primary-200 bg-primary-50/90 px-5 py-3.5 shadow-xs text-primary-950'
              : 'w-full self-start rounded-2xl border border-gray-200/90 bg-white p-5 shadow-xs dark:border-dark-800 dark:bg-dark-900'
          ]"
        >
          <!-- Editing -->
          <textarea
            v-if="editingMessageId === displayEntry.id"
            :value="editingMessageValue"
            rows="5"
            class="pw-input resize-y border-0 bg-transparent px-0 py-0 text-sm leading-7 shadow-none focus:ring-0"
            @input="handleEditingInput"
          />

          <!-- View Chunks -->
          <template v-else>
            <div class="space-y-4">
              <div v-for="(chunk, idx) in (displayEntry.chunks || [])" :key="`${displayEntry.id}-chunk-${idx}`">
                <!-- Text -->
                <MarkdownContent v-if="chunk.kind === 'text'" :content="chunk.text" />
                <!-- Reasoning -->
                <ChatReasoningBlock
                  v-else-if="chunk.kind === 'reasoning'"
                  :content="chunk.text"
                />
                <!-- Image -->
                <div v-else-if="chunk.kind === 'image'">
                  <img :src="`data:${chunk.mimeType};base64,${chunk.base64}`" class="max-w-xs rounded shadow" />
                </div>
                <!-- Tool Execution -->
                <ChatToolCallCard v-else-if="chunk.kind === 'tool-execution'" :chunk="chunk" />
              </div>
            </div>
          </template>
        </div>

        <!-- Toolbar -->
        <div v-if="getOriginalMessage(displayEntry.id)" class="flex max-w-[780px] flex-wrap items-center gap-2 text-xs" :class="displayEntry.author === 'user' ? 'w-auto justify-end self-end' : 'w-full justify-start self-start'">
          <template v-if="editingMessageId === displayEntry.id">
            <button type="button" class="pw-table-tool-button h-8 rounded-lg px-3 text-xs" @click="emit('cancel-edit')">
              取消编辑
            </button>
            <button
              type="button"
              class="pw-btn-primary inline-flex h-8 items-center justify-center rounded-lg px-3 text-xs font-medium disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="isRunning"
              @click="emit('submit-edit', getOriginalMessage(displayEntry.id)!, displayEntry.id, getParentCheckpointId(displayEntry.id, metadata))"
            >
              提交重发
            </button>
          </template>

          <template v-else>
            <button type="button" class="pw-table-tool-button h-8 rounded-lg px-3 text-xs" @click="emit('copy-message', getOriginalMessage(displayEntry.id)!)">
              复制
            </button>
            <button
              v-if="canEditMessage(getOriginalMessage(displayEntry.id)!, displayEntry.id, getParentCheckpointId(displayEntry.id, metadata))"
              type="button"
              class="pw-table-tool-button h-8 rounded-lg px-3 text-xs"
              @click="emit('start-edit', getOriginalMessage(displayEntry.id)!, displayEntry.id)"
            >
              编辑
            </button>
            <button
              v-if="canRetryMessage(getOriginalMessage(displayEntry.id)!, displayEntry.id, getParentCheckpointId(displayEntry.id, metadata))"
              type="button"
              class="pw-table-tool-button h-8 rounded-lg px-3 text-xs"
              @click="emit('retry-message', displayEntry.id, getParentCheckpointId(displayEntry.id, metadata))"
            >
              重试
            </button>

            <div v-if="hasBranchSwitcher(displayEntry.id)" class="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-2 py-1">
              <button
                type="button"
                class="rounded-md p-1 text-gray-500 hover:bg-gray-100 disabled:opacity-40"
                :disabled="getMessageBranchIndex(displayEntry.id) <= 0 || isRunning"
                @click="emit('select-previous-branch', displayEntry.id)"
              >
                <BaseIcon name="chevron-left" size="xs" />
              </button>
              <span class="min-w-[64px] text-center font-medium text-gray-500">
                {{ getMessageBranchIndex(displayEntry.id) + 1 }} / {{ getMessageMeta(displayEntry.id)?.branchOptions?.length }}
              </span>
              <button
                type="button"
                class="rounded-md p-1 text-gray-500 hover:bg-gray-100 disabled:opacity-40"
                :disabled="getMessageBranchIndex(displayEntry.id) >= ((getMessageMeta(displayEntry.id)?.branchOptions?.length ?? 1) - 1) || isRunning"
                @click="emit('select-next-branch', displayEntry.id)"
              >
                <BaseIcon name="chevron-right" size="xs" />
              </button>
            </div>
          </template>
        </div>

      </article>
    </ChatMessageRuntimeMetadata>

    <div v-if="isRunning" class="pw-chat-live-step">
      <span class="pw-chat-live-dot animate-pulse" />
      <span>Agent 正在处理当前回合</span>
    </div>
  </div>
</template>

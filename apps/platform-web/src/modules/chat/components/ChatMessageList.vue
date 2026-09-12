<script setup lang="ts">
import { computed, ref } from "vue";
import type { BaseMessage } from "@langchain/core/messages";
import type { AssembledToolCall } from "@langchain/vue";
import type { ChatMessageMetadata } from "../branching";
import BaseIcon from "@/components/base/BaseIcon.vue";
import MessageContent from "./MessageContent.vue";
import ToolResult from "./ToolResult.vue";
import { buildTranscript, type MessageItem, type ToolItem } from "../transcript";
const props = defineProps<{
  messages: readonly BaseMessage[];
  calls: readonly AssembledToolCall[];
  isRunning: boolean;
  canEdit?: boolean;
  metadata?: Record<string, ChatMessageMetadata>;
  editingMessageId?: string;
  editingMessageValue?: string;
}>();
const emit = defineEmits<{
  inspect: [tool: ToolItem]; edit: [id: string, text: string]; retry: [id: string];
  "select-branch": [branch: string];
  "update:editingMessageValue": [value: string]; "cancel-edit": []; "submit-edit": [];
}>();
const text = (items: MessageItem[]) =>
  items
    .flatMap((item) =>
      item.blocks
        .filter((block) => block.kind === "text")
        .map((block) => block.text),
    )
    .join("\n\n");
const visibleDisplayMessages = computed(() => {
  const turns = buildTranscript(props.messages, props.calls, props.isRunning);
  return turns.flatMap((turn, turnIndex) => {
    const isLastTurn = turnIndex === turns.length - 1;
    const user = turn.user;
    const entries = [];
    if (user) {
      entries.push({
        id: user.id ?? user.key,
        messageId: user.id,
        author: "user" as const,
        work: [],
        content: [user],
        text: text([user]),
        userId: user.id,
        userText: text([user]),
        isStreaming: false,
      });
    }
    if (turn.work.length || turn.answer.length) {
      entries.push({
        id: turn.key + ":agent",
        messageId: turn.answer[turn.answer.length - 1]?.id,
        author: "agent" as const,
        work: turn.work,
        content: turn.answer,
        text: text(turn.answer),
        userId: user?.id,
        userText: user ? text([user]) : "",
        isStreaming: props.isRunning && isLastTurn,
      });
    } else if (props.isRunning && user && isLastTurn) {
      entries.push({
        id: turn.key + ":agent:loading",
        messageId: undefined,
        author: "agent" as const,
        work: [],
        content: [
          {
            key: turn.key + ":pending",
            role: "ai",
            blocks: [
              {
                key: turn.key + ":pending:loading",
                kind: "loading" as const,
                text: "Agent 正在组织答复...",
              },
            ],
            tools: [],
          },
        ],
        text: "",
        userId: user.id,
        userText: text([user]),
        isStreaming: true,
      });
    }
    return entries;
  });
});
function getMessageMeta(id: string) { return props.metadata?.[id]; }
function getMessageBranchIndex(id: string) {
  const meta = getMessageMeta(id); return meta?.branchOptions?.indexOf(meta.branch || "") ?? -1;
}
function hasBranchSwitcher(id: string) { return (getMessageMeta(id)?.branchOptions?.length ?? 0) > 1; }
function selectBranch(id: string, offset: number) {
  const path = getMessageMeta(id)?.branchOptions?.[getMessageBranchIndex(id) + offset];
  if (path) emit("select-branch", path);
}
function handleEditingInput(event: Event) { emit("update:editingMessageValue", (event.target as HTMLTextAreaElement).value); }
const copyError = ref("");
async function copy(value: string) {
  try { await navigator.clipboard.writeText(value); copyError.value = ""; }
  catch { copyError.value = "复制失败，请手动选择文本复制"; }
}
</script>

<template>
  <div
    class="space-y-8"
    data-testid="transcript"
  >
    <template
      v-for="displayEntry in visibleDisplayMessages"
      :key="displayEntry.id"
    >
      <article
        class="pw-chat-turn"
        :data-author="displayEntry.author"
        :class="displayEntry.author === 'user' ? 'items-end' : 'items-start'"
      >
        <div
          class="pw-chat-turn-heading"
          :class="displayEntry.author === 'user' ? 'self-end' : 'self-start'"
        >
          <template v-if="displayEntry.author === 'agent'">
            <span class="pw-chat-agent-mark">
              <BaseIcon
                name="chat"
                size="sm"
              />
            </span>
            <span class="font-semibold text-gray-900 dark:text-white">Agent</span>
          </template>
          <template v-else>
            <span class="font-medium text-gray-500 dark:text-dark-300">你</span>
          </template>
        </div>

        <div
          :class="[
            displayEntry.author === 'user'
              ? 'w-auto max-w-[85%] self-end rounded-2xl rounded-tr-sm border border-primary-200 bg-primary-50/90 px-5 py-3.5 shadow-xs text-primary-950 dark:border-primary-900/50 dark:bg-primary-950/30 dark:text-primary-100'
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

          <template v-else>
            <div class="space-y-4">
              <details
                v-if="displayEntry.work.length"
                :open="isRunning"
              >
                <summary class="cursor-pointer text-xs text-gray-500">
                  工作过程 · {{ displayEntry.work.length }} 项
                </summary>
                <div
                  v-for="item in displayEntry.work"
                  :key="item.key"
                  class="mt-3 space-y-3"
                >
                  <MessageContent
                    :blocks="item.blocks"
                    :is-streaming="displayEntry.isStreaming"
                  />
                  <ToolResult
                    v-for="tool in item.tools"
                    :key="tool.key"
                    :tool="tool"
                    @inspect="emit('inspect', $event)"
                  />
                </div>
              </details>
              <div
                v-for="item in displayEntry.content"
                :key="item.key"
                class="space-y-3"
              >
                <MessageContent
                  :blocks="item.blocks"
                  :is-streaming="displayEntry.isStreaming"
                />
                <ToolResult
                  v-for="tool in item.tools"
                  :key="tool.key"
                  :tool="tool"
                  @inspect="emit('inspect', $event)"
                />
              </div>
            </div>
          </template>
        </div>

        <div
          class="flex max-w-[780px] flex-wrap items-center gap-2 text-xs"
          :class="displayEntry.author === 'user' ? 'w-auto justify-end self-end' : 'w-full justify-start self-start'"
        >
          <template v-if="editingMessageId === displayEntry.id">
            <button
              type="button"
              class="pw-table-tool-button h-8 rounded-lg px-3 text-xs"
              @click="emit('cancel-edit')"
            >
              取消编辑
            </button>
            <button
              type="button"
              class="pw-btn-primary inline-flex h-8 items-center justify-center rounded-lg px-3 text-xs font-medium disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="!canEdit || !editingMessageValue?.trim()"
              @click="emit('submit-edit')"
            >
              提交重发
            </button>
          </template>
          <template v-else>
            <button
              type="button"
              class="pw-table-tool-button h-8 rounded-lg px-3 text-xs"
              @click="copy(displayEntry.text)"
            >
              复制
            </button>
            <button
              v-if="displayEntry.author === 'user' && canEdit && displayEntry.messageId"
              type="button"
              class="pw-table-tool-button h-8 rounded-lg px-3 text-xs"
              @click="emit('edit', displayEntry.messageId, displayEntry.text)"
            >
              编辑
            </button>
            <button
              v-if="displayEntry.author === 'agent' && canEdit && displayEntry.messageId"
              type="button"
              class="pw-table-tool-button h-8 rounded-lg px-3 text-xs"
              @click="emit('retry', displayEntry.messageId!)"
            >
              重试
            </button>
            <div
              v-if="hasBranchSwitcher(displayEntry.messageId || '')"
              class="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-2 py-1"
            >
              <button
                type="button"
                class="rounded-md p-1 text-gray-500 hover:bg-gray-100 disabled:opacity-40"
                :disabled="getMessageBranchIndex(displayEntry.messageId || '') <= 0 || isRunning"
                aria-label="上一个分支"
                @click="selectBranch(displayEntry.messageId || '', -1)"
              >
                <BaseIcon
                  name="chevron-left"
                  size="xs"
                />
              </button>
              <span class="min-w-[64px] text-center font-medium text-gray-500">
                {{ getMessageBranchIndex(displayEntry.messageId || '') + 1 }} / {{ getMessageMeta(displayEntry.messageId || '')?.branchOptions?.length }}
              </span>
              <button
                type="button"
                class="rounded-md p-1 text-gray-500 hover:bg-gray-100 disabled:opacity-40"
                :disabled="getMessageBranchIndex(displayEntry.messageId || '') >= ((getMessageMeta(displayEntry.messageId || '')?.branchOptions?.length ?? 1) - 1) || isRunning"
                aria-label="下一个分支"
                @click="selectBranch(displayEntry.messageId || '', 1)"
              >
                <BaseIcon
                  name="chevron-right"
                  size="xs"
                />
              </button>
            </div>
          </template>
        </div>
      </article>
    </template>

    <p
      v-if="copyError"
      role="alert"
      class="text-xs text-red-600"
    >
      {{ copyError }}
    </p>
    <div
      v-if="isRunning"
      class="pw-chat-live-step"
    >
      <span class="pw-chat-live-dot animate-pulse" />
      <span>Agent 正在处理当前回合</span>
    </div>
  </div>
</template>

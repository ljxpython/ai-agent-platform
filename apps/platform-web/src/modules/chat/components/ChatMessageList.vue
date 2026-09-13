<script setup lang="ts">
import { computed, ref } from "vue";
import type { BaseMessage } from "@langchain/core/messages";
import type { AnyStream, AssembledToolCall } from "@langchain/vue";
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
  stream?: AnyStream;
  targetName?: string;
  projectId?: string;
  threadId?: string;
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
const copiedId = ref("");
let copyTimeout: ReturnType<typeof setTimeout> | null = null;
async function copy(value: string, id?: string) {
  try {
    await navigator.clipboard.writeText(value);
    copyError.value = "";
    if (id) {
      copiedId.value = id;
      if (copyTimeout) clearTimeout(copyTimeout);
      copyTimeout = setTimeout(() => {
        copiedId.value = "";
      }, 2000);
    }
  } catch {
    copyError.value = "复制失败，请手动选择文本复制";
  }
}
</script>

<template>
  <div
    class="space-y-7"
    data-testid="transcript"
  >
    <template
      v-for="displayEntry in visibleDisplayMessages"
      :key="displayEntry.id"
    >
      <article
        class="group relative pw-chat-turn transition-all duration-200"
        :data-author="displayEntry.author"
        :class="displayEntry.author === 'user' ? 'items-end' : 'items-start'"
      >
        <div
          class="pw-chat-turn-heading mb-1.5"
          :class="displayEntry.author === 'user' ? 'self-end' : 'self-start'"
        >
          <template v-if="displayEntry.author === 'agent'">
            <span class="inline-flex h-6 w-6 items-center justify-center rounded-lg bg-gradient-to-tr from-primary-600 to-indigo-500 text-white shadow-xs">
              <BaseIcon
                name="sparkle"
                size="xs"
              />
            </span>
            <span class="text-xs font-semibold text-gray-900 dark:text-white">{{ targetName || 'Agent' }}</span>
          </template>
          <template v-else>
            <span class="inline-flex h-6 w-6 items-center justify-center rounded-full bg-primary-100 text-primary-700 dark:bg-primary-950/80 dark:text-primary-300 text-xs font-semibold">
              你
            </span>
          </template>
        </div>

        <div
          :class="[
            displayEntry.author === 'user'
              ? 'w-auto max-w-[85%] self-end rounded-2xl rounded-tr-sm border border-primary-200/90 bg-gradient-to-br from-primary-50/90 to-primary-100/40 px-4.5 py-3 shadow-2xs text-primary-950 dark:border-primary-800/60 dark:bg-gradient-to-br dark:from-primary-950/40 dark:to-dark-900 dark:text-primary-50'
              : 'w-full self-start rounded-2xl border border-gray-200/80 bg-white/95 p-5 shadow-2xs transition-shadow hover:shadow-xs dark:border-dark-800/80 dark:bg-dark-900/95'
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
                class="group/work rounded-xl border border-gray-200/70 bg-gray-50/60 p-3 transition-colors dark:border-dark-800 dark:bg-dark-950/40"
              >
                <summary class="cursor-pointer select-none text-xs font-medium text-gray-500 hover:text-gray-800 dark:text-dark-400 dark:hover:text-dark-200 flex items-center justify-between">
                  <span class="flex items-center gap-2">
                    <span class="inline-flex h-4 w-4 items-center justify-center rounded-full bg-primary-100 text-primary-600 dark:bg-primary-950 dark:text-primary-400 text-[10px] font-bold">
                      {{ displayEntry.work.length }}
                    </span>
                    <span>执行步骤与工具调用</span>
                  </span>
                  <span class="text-[11px] text-gray-400 dark:text-dark-500">点击展开/收起</span>
                </summary>
                <div
                  v-for="item in displayEntry.work"
                  :key="item.key"
                  class="mt-3 space-y-3 pt-2 border-t border-gray-200/50 dark:border-dark-800/60"
                >
                  <MessageContent
                    :blocks="item.blocks"
                    :is-streaming="displayEntry.isStreaming"
                    :project-id="projectId"
                    :thread-id="threadId"
                  />
                  <ToolResult
                    v-for="tool in item.tools"
                    :key="tool.key"
                    :tool="tool"
                    :stream="stream"
                    :project-id="projectId"
                    :thread-id="threadId"
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
                  :project-id="projectId"
                  :thread-id="threadId"
                />
                <ToolResult
                  v-for="tool in item.tools"
                  :key="tool.key"
                  :tool="tool"
                  :stream="stream"
                  :project-id="projectId"
                  :thread-id="threadId"
                  @inspect="emit('inspect', $event)"
                />
              </div>
            </div>
          </template>
        </div>

        <div
          class="flex max-w-[780px] flex-wrap items-center gap-1.5 pt-1 text-xs transition-all duration-200"
          :class="[
            displayEntry.author === 'user' ? 'w-auto justify-end self-end' : 'w-full justify-start self-start',
            editingMessageId === displayEntry.id || copiedId === displayEntry.id
              ? 'opacity-100'
              : 'opacity-0 group-hover:opacity-100 focus-within:opacity-100'
          ]"
        >
          <template v-if="editingMessageId === displayEntry.id">
            <button
              type="button"
              class="inline-flex items-center gap-1 rounded-lg border border-gray-200 bg-white px-3 py-1 text-xs text-gray-600 transition hover:bg-gray-50 dark:border-dark-700 dark:bg-dark-800 dark:text-dark-300"
              @click="emit('cancel-edit')"
            >
              取消编辑
            </button>
            <button
              type="button"
              class="pw-btn-primary inline-flex h-7 items-center justify-center rounded-lg px-3 text-xs font-medium shadow-xs disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="!canEdit || !editingMessageValue?.trim()"
              @click="emit('submit-edit')"
            >
              提交重发
            </button>
          </template>
          <template v-else>
            <button
              type="button"
              class="inline-flex items-center gap-1 rounded-lg border border-gray-200/80 bg-white/90 px-2 py-1 text-xs text-gray-500 shadow-2xs transition hover:border-gray-300 hover:bg-gray-50 hover:text-gray-900 dark:border-dark-700/80 dark:bg-dark-800/90 dark:text-dark-300 dark:hover:border-dark-600 dark:hover:text-white"
              :class="copiedId === displayEntry.id ? '!border-emerald-500 !text-emerald-600 dark:!text-emerald-400' : ''"
              :title="copiedId === displayEntry.id ? '已复制' : '复制'"
              @click="copy(displayEntry.text, displayEntry.id)"
            >
              <BaseIcon
                :name="copiedId === displayEntry.id ? 'check' : 'copy'"
                size="xs"
              />
              <span class="text-[11px]">{{ copiedId === displayEntry.id ? '已复制' : '复制' }}</span>
            </button>
            <button
              v-if="displayEntry.author === 'user' && canEdit && displayEntry.messageId"
              type="button"
              class="inline-flex items-center gap-1 rounded-lg border border-gray-200/80 bg-white/90 px-2 py-1 text-xs text-gray-500 shadow-2xs transition hover:border-gray-300 hover:bg-gray-50 hover:text-gray-900 dark:border-dark-700/80 dark:bg-dark-800/90 dark:text-dark-300 dark:hover:border-dark-600 dark:hover:text-white"
              title="编辑"
              @click="emit('edit', displayEntry.messageId, displayEntry.text)"
            >
              <BaseIcon
                name="pencil"
                size="xs"
              />
              <span class="text-[11px]">编辑</span>
            </button>
            <button
              v-if="displayEntry.author === 'agent' && canEdit && displayEntry.messageId"
              type="button"
              class="inline-flex items-center gap-1 rounded-lg border border-gray-200/80 bg-white/90 px-2 py-1 text-xs text-gray-500 shadow-2xs transition hover:border-gray-300 hover:bg-gray-50 hover:text-gray-900 dark:border-dark-700/80 dark:bg-dark-800/90 dark:text-dark-300 dark:hover:border-dark-600 dark:hover:text-white"
              title="重试"
              @click="emit('retry', displayEntry.messageId!)"
            >
              <BaseIcon
                name="refresh"
                size="xs"
              />
              <span class="text-[11px]">重试</span>
            </button>
            <div
              v-if="hasBranchSwitcher(displayEntry.messageId || '')"
              class="inline-flex items-center gap-1 rounded-lg border border-gray-200/80 bg-white/90 px-1.5 py-0.5 shadow-2xs dark:border-dark-700/80 dark:bg-dark-800/90"
            >
              <button
                type="button"
                class="rounded p-0.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700 disabled:opacity-30 dark:hover:bg-dark-700 dark:hover:text-dark-200"
                :disabled="getMessageBranchIndex(displayEntry.messageId || '') <= 0 || isRunning"
                aria-label="上一个分支"
                title="上一个分支"
                @click="selectBranch(displayEntry.messageId || '', -1)"
              >
                <BaseIcon
                  name="chevron-left"
                  size="xs"
                />
              </button>
              <span class="min-w-[48px] text-center font-mono text-[11px] font-medium text-gray-500 dark:text-dark-300">
                {{ getMessageBranchIndex(displayEntry.messageId || '') + 1 }} / {{ getMessageMeta(displayEntry.messageId || '')?.branchOptions?.length }}
              </span>
              <button
                type="button"
                class="rounded p-0.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700 disabled:opacity-30 dark:hover:bg-dark-700 dark:hover:text-dark-200"
                :disabled="getMessageBranchIndex(displayEntry.messageId || '') >= ((getMessageMeta(displayEntry.messageId || '')?.branchOptions?.length ?? 1) - 1) || isRunning"
                aria-label="下一个分支"
                title="下一个分支"
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

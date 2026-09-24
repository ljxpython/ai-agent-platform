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
  isInterrupted?: boolean;
  canEdit?: boolean;
  metadata?: Record<string, ChatMessageMetadata>;
  editingMessageId?: string;
  editingMessageValue?: string;
  stream?: AnyStream;
  targetName?: string;
  projectId?: string;
  threadId?: string;
  forkingCheckpointId?: string;
}>();
const emit = defineEmits<{
  inspect: [tool: ToolItem]; edit: [id: string, text: string]; retry: [id: string];
  fork: [messageId: string, checkpointId?: string];
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
  const turns = buildTranscript(
    props.messages,
    props.calls,
    props.isRunning || Boolean(props.isInterrupted),
  );
  const totalTurns = turns.length;
  return turns.flatMap((turn, turnIndex) => {
    const isLastTurn = turnIndex === totalTurns - 1;
    const user = turn.user;
    const entries = [];
    if (user) {
      entries.push({
        id: user.id ?? user.key,
        renderKey: `turn-${turnIndex}:user`,
        messageId: user.id,
        author: "user" as const,
        turnIndex,
        totalTurns,
        isLastUserTurn: isLastTurn,
        work: [],
        content: [user],
        text: text([user]),
        userId: user.id,
        userText: text([user]),
        isStreaming: false,
      });
    }
    const hasVisibleAgentOutput =
      turn.work.some(
        (item) =>
          (item.tools?.length ?? 0) > 0 ||
          item.blocks?.some(
            (b) =>
              b.kind === "loading" ||
              b.kind === "image" ||
              b.kind === "file" ||
              b.kind === "unknown" ||
              ((b.kind === "reasoning" || b.kind === "text") && b.text.trim().length > 0),
          ),
      ) ||
      turn.answer.some((item) =>
        item.blocks?.some(
          (b) =>
            b.kind === "loading" ||
            b.kind === "image" ||
            b.kind === "file" ||
            b.kind === "unknown" ||
            ((b.kind === "reasoning" || b.kind === "text") && b.text.trim().length > 0),
        ),
      );
    const showPendingPlaceholder =
      props.isRunning && Boolean(user) && isLastTurn && !hasVisibleAgentOutput;
    if (turn.work.length || turn.answer.length || showPendingPlaceholder) {
      const pendingContent = [
        {
          key: turn.key + ":pending",
          role: "ai" as const,
          blocks: [
            {
              key: turn.key + ":pending:loading",
              kind: "loading" as const,
              text: "Agent 正在组织答复...",
            },
          ],
          tools: [],
        },
      ];
      entries.push({
        id: turn.key + ":agent",
        renderKey: `turn-${turnIndex}:agent`,
        messageId: turn.answer[turn.answer.length - 1]?.id,
        author: "agent" as const,
        turnIndex,
        totalTurns,
        isLastUserTurn: false,
        work: turn.work,
        content: showPendingPlaceholder ? pendingContent : turn.answer,
        text: text(turn.answer),
        userId: user?.id,
        userText: user ? text([user]) : "",
        isStreaming: props.isRunning && isLastTurn,
      });
    }
    return entries;
  });
});

const shouldShowLiveStep = computed(() => {
  if (!props.isRunning) return false;
  const turns = visibleDisplayMessages.value;
  if (!turns.length) return true;
  const lastEntry = turns[turns.length - 1];

  if (lastEntry?.author === "user") return true;

  const hasRunningTools = lastEntry?.work?.some((w) =>
    w.tools?.some((t) => t.status === "running")
  );
  if (hasRunningTools) return true;

  const hasVisibleBlocks = lastEntry?.content?.some((item) =>
    item.blocks?.some(
      (b) =>
        b.kind === "loading" ||
        ((b.kind === "reasoning" || b.kind === "text") && b.text.trim().length > 0),
    ),
  );
  if (hasVisibleBlocks) return false;

  const hasVisibleWorkReasoningOrText = lastEntry?.work?.some((item) =>
    item.blocks?.some(
      (b) =>
        b.kind === "loading" ||
        ((b.kind === "reasoning" || b.kind === "text") && b.text.trim().length > 0),
    ),
  );
  if (hasVisibleWorkReasoningOrText && !lastEntry?.work?.some((w) => (w.tools?.length ?? 0) > 0)) {
    return false;
  }

  return true;
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
function getForkCheckpointId(entry: (typeof visibleDisplayMessages.value)[number]): string | undefined {
  if (entry.author !== "agent" || !entry.messageId) return undefined;
  return getMessageMeta(entry.messageId)?.checkpointId;
}
function handleEditingInput(event: Event) { emit("update:editingMessageValue", (event.target as HTMLTextAreaElement).value); }
const copyError = ref("");
const copiedId = ref("");
const workOpenState = ref<Record<string, boolean>>({});
function isWorkOpen(entryId: string): boolean {
  return workOpenState.value[entryId] ?? true;
}
function toggleWork(entryId: string) {
  workOpenState.value[entryId] = !isWorkOpen(entryId);
}
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
      :key="displayEntry.renderKey"
    >
      <article
        class="group relative pw-chat-turn transition-colors duration-200"
        :data-author="displayEntry.author"
        :data-turn-index="displayEntry.turnIndex"
        :data-is-last-user="displayEntry.isLastUserTurn ? 'true' : undefined"
        :class="displayEntry.author === 'user' ? 'items-end' : 'items-start'"
      >
        <div
          v-if="displayEntry.author === 'agent'"
          class="pw-chat-turn-heading mb-1.5 flex items-center gap-2"
        >
          <span class="inline-flex h-5 w-5 items-center justify-center rounded-md bg-gradient-to-tr from-blue-600 to-indigo-600 text-white shadow-xs">
            <BaseIcon
              name="sparkle"
              size="xs"
            />
          </span>
          <span class="text-xs font-semibold text-gray-800 dark:text-gray-200">{{ targetName || 'Agent' }}</span>
        </div>

        <div
          :class="[
            displayEntry.author === 'user'
              ? 'w-auto max-w-[85%] sm:max-w-[75%] self-end rounded-2xl rounded-tr-xs bg-blue-50/85 text-gray-900 border border-blue-100/90 px-4 py-2.5 shadow-2xs dark:bg-blue-950/40 dark:border-blue-900/50 dark:text-gray-100'
              : 'w-full self-start border-0 bg-transparent p-0 shadow-none'
          ]"
        >
          <!-- Editing -->
          <textarea
            v-if="editingMessageId === displayEntry.id || (displayEntry.messageId && editingMessageId === displayEntry.messageId)"
            :value="editingMessageValue"
            rows="5"
            class="pw-input resize-y border-0 bg-transparent px-0 py-0 text-sm leading-7 shadow-none focus:ring-0"
            @input="handleEditingInput"
          />

          <template v-else>
            <div class="space-y-4">
              <details
                v-if="displayEntry.work.length"
                :open="isWorkOpen(displayEntry.renderKey)"
                class="group/work rounded-xl border border-gray-200/70 bg-gray-50/60 p-3 transition-colors dark:border-dark-800 dark:bg-dark-950/40"
              >
                <summary
                  class="cursor-pointer select-none text-xs font-medium text-gray-500 hover:text-gray-800 dark:text-dark-400 dark:hover:text-dark-200 flex items-center justify-between"
                  @click.prevent="toggleWork(displayEntry.renderKey)"
                >
                  <span class="flex items-center gap-2">
                    <span class="inline-flex h-4 w-4 items-center justify-center rounded-full bg-primary-100 text-primary-600 dark:bg-primary-950 dark:text-primary-400 text-[10px] font-bold">
                      {{ displayEntry.work.length }}
                    </span>
                    <span>执行步骤与工具调用</span>
                  </span>
                  <span class="text-[11px] text-gray-400 dark:text-dark-500">点击展开/收起</span>
                </summary>
                <div
                  v-for="(item, workIdx) in displayEntry.work"
                  :key="workIdx"
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
                    :key="tool.id || tool.key"
                    :tool="tool"
                    :stream="stream"
                    :project-id="projectId"
                    :thread-id="threadId"
                    @inspect="emit('inspect', $event)"
                  />
                </div>
              </details>
              <div
                v-for="(item, contentIdx) in displayEntry.content"
                :key="contentIdx"
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
                  :key="tool.id || tool.key"
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
            editingMessageId === displayEntry.id || (displayEntry.messageId && editingMessageId === displayEntry.messageId) || copiedId === displayEntry.id
              ? 'opacity-100'
              : 'opacity-0 group-hover:opacity-100 focus-within:opacity-100'
          ]"
        >
          <template v-if="editingMessageId === displayEntry.id || (displayEntry.messageId && editingMessageId === displayEntry.messageId)">
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
              class="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs text-gray-400 hover:text-gray-700 hover:bg-gray-100/80 dark:text-dark-400 dark:hover:text-gray-200 dark:hover:bg-dark-800/80 transition-colors"
              :class="copiedId === displayEntry.id ? '!text-emerald-600 dark:!text-emerald-400' : ''"
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
              class="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs text-gray-400 hover:text-gray-700 hover:bg-gray-100/80 dark:text-dark-400 dark:hover:text-gray-200 dark:hover:bg-dark-800/80 transition-colors"
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
              v-if="displayEntry.author === 'agent' && displayEntry.messageId"
              type="button"
              class="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs text-gray-400 hover:text-gray-700 hover:bg-gray-100/80 dark:text-dark-400 dark:hover:text-gray-200 dark:hover:bg-dark-800/80 transition-colors"
              title="重试"
              @click="emit('retry', displayEntry.messageId)"
            >
              <BaseIcon
                name="refresh"
                size="xs"
              />
              <span class="text-[11px]">重试</span>
            </button>
            <button
              v-if="displayEntry.author === 'agent' && displayEntry.messageId"
              type="button"
              class="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs text-gray-400 hover:text-gray-700 hover:bg-gray-100/80 disabled:cursor-not-allowed disabled:opacity-40 dark:text-dark-400 dark:hover:text-gray-200 dark:hover:bg-dark-800/80 transition-colors"
              :disabled="isRunning || displayEntry.isStreaming || Boolean(forkingCheckpointId)"
              aria-label="在新对话中分支"
              :title="isRunning || displayEntry.isStreaming ? '仅可从已完成轮次分支' : '在新对话中分支'"
              @click="emit('fork', displayEntry.messageId!, getForkCheckpointId(displayEntry))"
            >
              <BaseIcon
                name="branch"
                size="xs"
                :class="forkingCheckpointId && (forkingCheckpointId === getForkCheckpointId(displayEntry) || forkingCheckpointId === displayEntry.messageId) ? 'animate-spin' : ''"
              />
              <span class="text-[11px]">分支</span>
            </button>
            <div
              v-if="hasBranchSwitcher(displayEntry.messageId || '')"
              class="inline-flex items-center gap-1 rounded-md border border-gray-200/60 bg-white/70 px-1 py-0.5 text-xs dark:border-dark-800 dark:bg-dark-900/60"
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
      v-if="shouldShowLiveStep"
      class="pw-chat-live-step"
    >
      <span class="pw-chat-live-dot animate-pulse" />
      <span>Agent 正在处理当前回合</span>
    </div>
  </div>
</template>

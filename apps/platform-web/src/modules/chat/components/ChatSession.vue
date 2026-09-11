<script setup lang="ts">
import {
  computed,
  reactive,
  nextTick,
  onScopeDispose,
  ref,
  shallowRef,
  toRef,
  watch,
} from "vue";
import { coerceMessageLikeToMessage, type BaseMessage } from "@langchain/core/messages";
import { parseAgentContext } from "@/services/agents/context";
import ChatRunOptionsDialog from "./ChatRunOptionsDialog.vue";
import ChatContextDrawer from "./ChatContextDrawer.vue";
import ChatArtifactPanel from "./ChatArtifactPanel.vue";
import ChatAgentStatusBar from "./ChatAgentStatusBar.vue";
import { RouterLink } from "vue-router";
import { buildChatMessageMetadata, getChatBranchContext } from "../branching";
import { buildChatLiveFollowView } from "../live-follow-view-model";
import type { Message } from "@langchain/langgraph-sdk";
import type { Checkpoint } from "@langchain/langgraph-sdk";
import { useAuthStore } from "@/stores/auth";
import BaseIcon from "@/components/base/BaseIcon.vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseDialog from "@/components/base/BaseDialog.vue";
import type { AgentContext } from "@/services/agents/types";
import {
  isChatAttachmentBlock,
  type ChatAttachmentBlock,
} from "@/utils/chat-content";
import type { ChatCheckpoint } from "@/services/threads/session.service";
import { listRuntimeModels } from "@/services/runtime/runtime.service";
import type { RuntimeModelItem } from "@/types/management";
import { listRuntimeModelPolicies } from "@/services/runtime-policies/runtime-policies.service";
import { useChatSession } from "../composables/useChatSession";
import { useChatAttachments } from "../composables/useChatAttachments";
import { useTranscriptMessages } from "../composables/useTranscriptMessages";
import { asObject, buildTranscript, contentItems, readable, type ToolItem } from "../transcript";
import { isChatViewportNearBottom } from "../scroll-state";
import ChatComposer from "./ChatComposer.vue";
import ChatMessageList from "./ChatMessageList.vue";
import ApprovalPanel from "./ApprovalPanel.vue";
import SubtaskDetail from "./SubtaskDetail.vue";
import MessageContent from "./MessageContent.vue";

const props = defineProps<{
  projectId: string;
  graphId: string;
  agentId?: string;
  threadId?: string;
  canWrite: boolean;
  draft: string;
  focusMode?: boolean;
  targetName?: string;
  projectName?: string;
}>();
const emit = defineEmits<{
  thread: [id: string];
  refresh: [];
  reconnect: [];
  "update:draft": [value: string];
}>();
const context = defineModel<AgentContext>("context", { required: true });
const recursionLimit = defineModel<number>("recursionLimit", {
  required: true,
});
const draftAttachments = defineModel<ChatAttachmentBlock[]>("attachments", {
  required: true,
});
const {
  attachments,
  loading: attachmentsLoading,
  handleInputChange,
  handlePaste,
  removeAttachment,
} = useChatAttachments(draftAttachments);
let submittedDraft: string | undefined;
let submittedAttachments = new Set<unknown>();
const session = useChatSession({
  projectId: props.projectId,
  userId: useAuthStore().user?.id,
  graphId: props.graphId,
  agentId: props.agentId,
  threadId: props.threadId,
  context,
  canWrite: toRef(props, "canWrite"),
  onThread: (id) => emit("thread", id),
  onRefresh: () => emit("refresh"),
  onReconnect: () => emit("reconnect"),
  onAccepted: () => {
    if (props.draft === submittedDraft) emit("update:draft", "");
    attachments.value = attachments.value.filter(
      (item) => !submittedAttachments.has(item),
    );
    submittedDraft = undefined;
    submittedAttachments = new Set();
  },
});
const {
  stream,
  reviews,
  checking,
  cancelling,
  error,
  busy,
  canSend,
  status,
  actions,
} = session;
const action = actions.current;
const messages = useTranscriptMessages(stream);
const calls = stream.toolCalls;
const approvalElement = ref<HTMLElement | null>(null);
const streamError = computed(() =>
  stream.error.value instanceof Error
    ? stream.error.value.message === "[object Object]" ? "运行失败，请检查模型与工具授权，或打开运行详情查看原因" : stream.error.value.message
    : stream.error.value
      ? "流连接异常，请恢复连接"
      : "",
);
const canSubmit = computed(
  () =>
    canSend.value && !snapshotMessages.value &&
    !modelsLoading.value && !!models.value.length &&
    !attachmentsLoading.value &&
    (!!props.draft.trim() || !!attachments.value.length),
);
const models = ref<RuntimeModelItem[]>([]);
const modelsLoading = ref(true);
const defaultModelName = ref("");
const optionsOpen = ref(false);
const optionsError = ref("");
const initialContext = { ...context.value };
const draftRunOptions = reactive({ modelId: "", temperature: "", maxTokens: "" });
function resetOptions(value: AgentContext) {
  Object.assign(draftRunOptions, { modelId: value.model_id ?? "", temperature: value.temperature?.toString() ?? "", maxTokens: value.max_tokens?.toString() ?? "" });
  optionsError.value = "";
}
function openOptions() { resetOptions(context.value); optionsOpen.value = true; }
function applyOptions() {
  try {
    const updated = parseAgentContext({ ...context.value, model_id: draftRunOptions.modelId || undefined,
      temperature: draftRunOptions.temperature.trim() ? Number(draftRunOptions.temperature) : undefined,
      max_tokens: draftRunOptions.maxTokens.trim() ? Number(draftRunOptions.maxTokens) : undefined });
    context.value = updated;
    optionsOpen.value = false;
  } catch (cause) { optionsError.value = cause instanceof Error ? cause.message : "运行参数无效"; }
}
const drawerOpen = ref(false);
const drawerTab = ref<"overview" | "tasks" | "files" | "history">("overview");
function openDrawer() { drawerOpen.value = true; drawerTab.value = "overview"; void loadHistory(true); }
const snapshotMessages = shallowRef<BaseMessage[] | null>(null);
const displayedMessages = computed(() => snapshotMessages.value ?? messages.value);
const branchPath = ref("");
const branchContext = computed(() => getChatBranchContext(branchPath.value, history.value));
const messageMetadata = computed(() => buildChatMessageMetadata(displayedMessages.value as unknown as Message[], history.value, branchContext.value));
function selectMessageBranch(path: string) {
  const head = getChatBranchContext(path, history.value).threadHead;
  if (head?.checkpoint.checkpoint_id) {
    selectSnapshot(head.checkpoint.checkpoint_id);
    branchPath.value = path;
  }
}
function selectSnapshot(id: string) {
  if (!id) { branchPath.value = ""; selectedCheckpoint.value = null; snapshotMessages.value = null; return; }
  const row = history.value.find(item => item.checkpoint.checkpoint_id === id);
  if (!row) return;
  try {
    const converted = (row.values.messages ?? []).map(message => coerceMessageLikeToMessage(message as Parameters<typeof coerceMessageLikeToMessage>[0]));
    selectedCheckpoint.value = row;
    snapshotMessages.value = converted;
  } catch { localError.value = "该快照消息无法解析，请选择其他快照"; }
}
const drawerHistory = computed(() => history.value.map(row => ({ ...row, metadata: { ...row.metadata, created_at: row.created_at } })));
const drawerFiles = computed(() => files.value.map(([path, value]) => {
  const content = typeof value.content === "string" ? value.content : readable(value.content);
  return { path, content, lineCount: content.split("\n").length, completeness: value.completeness };
}));
const planView = computed(() => {
  const planTodos = todos.value.map((todo, index) => ({ id: String(todo.id ?? index), content: String(todo.content), status: todo.status as "pending" | "in_progress" | "completed" }));
  const completedTasks = planTodos.filter(todo => todo.status === "completed").length;
  return { planTodos, ephemeralTodos: [], activeTask: planTodos.find(todo => todo.status === "in_progress") ?? null, totalTasks: planTodos.length, completedTasks, allTasksCompleted: !!planTodos.length && completedTasks === planTodos.length, hasFrozenPlan: false };
});
const hasArtifacts = computed(() => Array.isArray(stream.values.value.ui) && stream.values.value.ui.length > 0);
const localError = ref("");
let disposed = false;
void Promise.all([listRuntimeModels(props.projectId), listRuntimeModelPolicies(props.projectId)])
  .then(([value, policies]) => {
    if (disposed) return;
    models.value = value.models.filter((model) => model.enabled && model.credential_configured && policies.items.find(item => item.catalog_id === model.id)?.policy.is_enabled !== false);
    const projectDefault = policies.items.find(item => item.policy.is_default_for_project);
    defaultModelName.value = models.value.find(model => model.id === projectDefault?.catalog_id)?.display_name ?? "";
  })
  .catch(() => {
    if (!disposed) localError.value = "模型列表读取失败，可恢复连接后重试";
  }).finally(() => { if (!disposed) modelsLoading.value = false; });

async function send(queued = false) {
  if (
    queued
      ? !props.canWrite ||
        cancelling.value ||
        reviews.value.length ||
        !props.draft.trim()
      : !canSubmit.value
  )
    return;
  submittedDraft = props.draft;
  submittedAttachments = new Set(attachments.value);
  const content = attachments.value.length
    ? [{ type: "text", text: props.draft }, ...attachments.value]
    : props.draft;
  if (queued) await session.queueMessage(content);
  else await session.send(content, recursionLimit.value);
}

function restoreQueuedDraft(content?: unknown) {
  const restoringPending = content === undefined;
  content ??= session.pendingMessage.value?.payload.content;
  const append = (text: string) => emit("update:draft", props.draft === text ? text : [props.draft, text].filter(Boolean).join("\n"));
  if (typeof content === "string") append(content);
  else if (Array.isArray(content)) {
    append(
      content
        .filter((item) => item?.type === "text")
        .map((item) => item.text)
        .join("\n"),
    );
    attachments.value = [...attachments.value, ...content.filter(isChatAttachmentBlock)];
  }
  if (restoringPending) session.pendingMessage.value = null;
}

const viewport = ref<HTMLElement | null>(null);
const following = ref(true);
const unreadMessageCount = ref(0);
const bufferedStreamActivity = ref(false);
const lastEventAt = ref("");
const liveFollowView = computed(() => buildChatLiveFollowView({
  autoFollowEnabled: following.value && !drawerOpen.value && !optionsOpen.value && !inspector.value,
  isRunning: busy.value, unreadMessageCount: unreadMessageCount.value, bufferedStreamActivity: bufferedStreamActivity.value,
}));
watch(
  messages,
  async (next, previous) => {
    lastEventAt.value = new Date().toISOString();
    if (!following.value) {
      unreadMessageCount.value += Math.max(0, next.length - previous.length);
      bufferedStreamActivity.value = true;
    }
    if (following.value && !drawerOpen.value && !optionsOpen.value && !inspector.value && !snapshotMessages.value) {
      await nextTick();
      if (viewport.value)
        viewport.value.scrollTop = viewport.value.scrollHeight;
    }
  },
  { flush: "post" },
);
function follow() {
  following.value = true;
  unreadMessageCount.value = 0;
  bufferedStreamActivity.value = false;
  if (viewport.value) viewport.value.scrollTop = viewport.value.scrollHeight;
}

const expanded = ref<Record<string, boolean>>({});
const subtasks = computed(() => {
  const agents = [...stream.subagents.value.values()];
  const known = new Set(agents.map((agent) => JSON.stringify(agent.namespace)));
  const tasks = [
    ...agents.map((agent) => ({
      ...agent,
      key: JSON.stringify(agent.namespace),
      label: agent.name,
      description: agent.taskInput,
      parent: agent.parentId,
    })),
    ...[...stream.subgraphs.value.values()]
      .filter((graph) => !known.has(JSON.stringify(graph.namespace)))
      .map((graph) => ({
        ...graph,
        key: JSON.stringify(graph.namespace),
        label: graph.nodeName,
        description: undefined,
        parent: undefined,
      })),
  ];
  return tasks.map(task => {
    const parent = tasks.filter(candidate => candidate.key !== task.key &&
      candidate.namespace.length < task.namespace.length &&
      candidate.namespace.every((part, index) => task.namespace[index] === part))
      .sort((a, b) => b.namespace.length - a.namespace.length)[0];
    return { ...task, parent: task.parent ?? parent?.label,
      depth: Math.max(0, task.namespace.length - 1) };
  }).sort((a, b) => a.key.localeCompare(b.key));
});
const todos = computed(() =>
  Array.isArray(stream.values.value.todos)
    ? stream.values.value.todos
        .map(asObject)
        .filter(
          (todo) =>
            typeof todo.content === "string" &&
            ["pending", "in_progress", "completed"].includes(
              String(todo.status),
            ),
        )
    : [],
);
const files = computed(() => {
  const visible = new Map(Object.entries(asObject(stream.values.value.files)).map(([path, value]) => [path, {
    content: asObject(value).content ?? value,
    source: "公开状态",
    completeness: asObject(value).complete === true ? "完整内容" : "可见片段，完整性未声明",
  }]));
  const statePaths = new Set(visible.keys());
  // Hydrated SDK calls may be empty; the same transcript projection joins
  // persisted AI tool_calls with ToolMessages after a refresh.
  const tools = buildTranscript(messages.value, calls.value, busy.value)
    .flatMap(turn => [...turn.work, ...turn.answer].flatMap(item => item.tools));
  for (const tool of tools) {
    const input = asObject(tool.input);
    const path = input.file_path ?? input.path;
    if (tool.name === "read_file" && tool.status === "finished" && typeof path === "string" && tool.output !== undefined && !statePaths.has(path))
      visible.set(path, { content: tool.output, source: `工具调用 ${tool.id}`, completeness: "读取结果，可能包含截断" });
  }
  return [...visible.entries()];
});
const inspector = shallowRef<{
  title: string;
  source: string;
  value: unknown;
} | null>(null);
function inspect(tool: ToolItem) {
  const path = asObject(tool.input).file_path ?? asObject(tool.input).path;
  inspector.value = {
    title: tool.name === "read_file" && typeof path === "string" && path.startsWith("/skills/") ? "已读取技能" : tool.name,
    source: `工具调用 ${tool.id} · ${tool.status}${typeof path === "string" ? ` · ${path} · 可见片段` : ""}`,
    value: tool.artifact ?? tool.output,
  };
}

async function submitEditedBranch() {
  const checkpoint = editCheckpoint.value;
  if (!checkpoint) return;
  await session.fork(checkpoint, editDraft.value);
  if (actions.current.value?.status === "acknowledged") { editCheckpoint.value = null; editingMessageId.value = ""; }
}
const historyLoading = ref(false);
const history = shallowRef<ChatCheckpoint[]>([]);
const hasMoreHistory = ref(true);
const selectedCheckpoint = shallowRef<ChatCheckpoint | null>(null);
async function loadHistory(reset = false) {
  if (!session.threadId.value || historyLoading.value) return;
  historyLoading.value = true;
  localError.value = "";
  try {
    const rows = await session.service.history(
      session.threadId.value,
      reset ? undefined : history.value[history.value.length - 1]?.checkpoint,
    );
    if (disposed) return;
    history.value = reset ? rows : [...history.value, ...rows];
    hasMoreHistory.value = rows.length === 20;
  } catch (cause) {
    if (!disposed)
      localError.value =
        cause instanceof Error ? cause.message : "历史加载失败";
  } finally {
    if (!disposed) historyLoading.value = false;
  }
}

const editDraft = ref("");
const editingMessageId = ref("");
async function retryMessage(id: string) {
  await edit(id, "");
  if (!disposed && editCheckpoint.value) {
    await session.fork(editCheckpoint.value);
    if (actions.current.value?.status === "acknowledged") { editCheckpoint.value = null; editingMessageId.value = ""; }
  }
}
const editCheckpoint = shallowRef<Checkpoint | null>(null);
const editLoading = ref(false);
async function edit(messageId: string, text: string) {
  if (!canSend.value || !session.threadId.value || editLoading.value) return;
  editLoading.value = true;
  localError.value = "";
  try {
    // Walk the current branch only; timestamps from other branches cannot locate an edit.
    let current = await session.service.state(session.threadId.value);
    const contains = (state: ChatCheckpoint) =>
      (state.values.messages ?? []).some(
        (message) => asObject(message).id === messageId,
      );
    for (let depth = 0; depth < 200 && !disposed; depth++) {
      if (!contains(current) || !current.parent_checkpoint) break;
      const parent = await session.service.state(
        session.threadId.value,
        current.parent_checkpoint,
      );
      if (!contains(parent)) {
        editCheckpoint.value = parent.checkpoint;
        editDraft.value = text;
        editingMessageId.value = messageId;
        return;
      }
      current = parent;
    }
    if (!disposed)
      localError.value = "未找到该消息之前可恢复的检查点，无法安全创建分支";
  } catch (cause) {
    if (!disposed)
      localError.value =
        cause instanceof Error ? cause.message : "读取分支失败";
  } finally {
    if (!disposed) editLoading.value = false;
  }
}
watch([session.threadId, busy, checking], ([id, running, verifying]) => {
  if (id && !running && !verifying) void loadHistory(true);
}, { immediate: true });
function visibilityChanged() {
  if (!document.hidden && !busy.value && action.value?.status !== "unknown")
    void session.verify();
}
document.addEventListener("visibilitychange", visibilityChanged);
onScopeDispose(() => {
  disposed = true;
  document.removeEventListener("visibilitychange", visibilityChanged);
});
</script>

<template>
  <div
    class="pw-chat-workspace min-w-0"
  >
    <header
      v-if="!focusMode"
      class="pw-chat-workspace-header"
    >
      <div class="flex min-h-8 flex-wrap items-center gap-2 xl:flex-nowrap">
        <div class="flex min-w-0 items-center gap-2">
          <slot name="target" />
          <span class="pw-pill shrink-0 px-2.5 py-1 text-[11px]"><span class="text-gray-400">Thread</span><span>{{ session.threadId.value?.slice(0, 8) || '未创建' }}</span></span>
        </div>
        <div class="ml-auto flex flex-wrap items-center gap-2 xl:flex-nowrap">
          <slot name="actions" />
          <BaseButton
            variant="secondary"
            class="h-8 shrink-0 px-3 text-xs"
            @click="openDrawer"
          >
            <BaseIcon
              name="overview"
              size="sm"
            />会话详情
          </BaseButton>
          <BaseButton
            variant="secondary"
            class="h-8 shrink-0 px-3 text-xs"
            @click="openOptions"
          >
            <BaseIcon
              name="runtime"
              size="sm"
            />运行参数
          </BaseButton>
        </div>
      </div>
    </header>
    <span
      role="status"
      aria-live="polite"
      class="sr-only"
    >{{ status }}<span v-if="!canWrite"> · 只读</span></span>
    <div
      v-if="snapshotMessages"
      class="pw-panel-info mx-5 mt-3 flex items-center justify-between gap-3 text-sm"
    >
      正在查看历史快照
      <BaseButton
        variant="ghost"
        @click="selectSnapshot('')"
      >
        返回最新
      </BaseButton>
    </div>
    <div
      v-if="!modelsLoading && !models.length"
      role="alert"
      class="px-5 py-3 text-sm text-amber-700 dark:text-amber-300"
    >
      当前项目没有可用模型，请先在模型与工具页面配置并授权模型。
      <RouterLink
        :to="`/workspace/projects/${projectId}/models`"
        class="underline"
      >
        配置模型
      </RouterLink>
    </div>
    <div
      v-if="error || streamError || localError"
      role="alert"
      class="flex flex-wrap items-center gap-2 bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-950/20"
    >
      <span class="min-w-0 flex-1 break-words">{{
        error || streamError || localError
      }}</span>
      <button
        v-if="action?.status !== 'unknown' && action?.status !== 'submitting'"
        class="underline"
        @click="emit('reconnect')"
      >
        恢复连接
      </button>
    </div>
    <div
      v-if="action?.status === 'unknown'"
      class="bg-amber-50 px-4 py-3 text-sm text-amber-900"
    >
      提交结果尚未确认，草稿已保留。
      <button
        class="underline"
        :disabled="!canWrite"
        @click="session.retry()"
      >
        核实原请求
      </button>
    </div>
    <div
      class="relative z-10 flex min-h-0 flex-1 flex-col overflow-hidden"
      :class="hasArtifacts ? 'lg:grid lg:grid-cols-[minmax(0,1fr)_320px]' : ''"
    >
      <div class="relative flex min-w-0 flex-1 flex-col">
        <div
          ref="viewport"
          class="pw-chat-stream overscroll-contain"
          @scroll="
            following = viewport ? isChatViewportNearBottom(viewport) : true
          "
        >
          <div class="pw-chat-stream-content space-y-6">
            <ChatAgentStatusBar
              class="sticky top-0 z-10 mb-4"
              :is-running="busy"
              :is-interrupted="!!reviews.length"
              :last-event-at="lastEventAt"
              :error="error || streamError"
              :disabled="!canWrite || cancelling"
              @cancel="session.stop"
              @resume="approvalElement?.scrollIntoView({ block: 'center', behavior: 'smooth' })"
            />
            <div
              v-if="!messages.length && !checking"
              class="pw-chat-empty-state"
            >
              <span class="pw-chat-empty-mark">
                <BaseIcon
                  name="chat"
                  size="lg"
                />
              </span>
              <h2 class="mt-4 text-xl font-semibold text-gray-900 dark:text-white">
                开始新的对话
              </h2>
              <p class="mt-2 max-w-lg text-sm leading-7 text-gray-500 dark:text-dark-300">
                输入任务目标后，Agent 会在这里展示回复、执行步骤与需要你确认的操作。
              </p>
            </div>
            <ChatMessageList
              :messages="displayedMessages"
              :calls="snapshotMessages ? [] : calls"
              :is-running="busy && !snapshotMessages"
              :can-edit="canSend && !editLoading && !snapshotMessages"
              :metadata="messageMetadata"
              :editing-message-id="editingMessageId"
              :editing-message-value="editDraft"
              @select-branch="selectMessageBranch"
              @inspect="inspect"
              @edit="edit"
              @retry="retryMessage"
              @update:editing-message-value="editDraft = $event"
              @cancel-edit="editCheckpoint = null; editingMessageId = ''"
              @submit-edit="submitEditedBranch"
            />
            <section
              v-if="
                session.receipts.value.length ||
                  session.pendingMessage.value ||
                  session.receiptError.value
              "
              aria-label="消息投递状态"
              class="space-y-2 rounded-lg border p-3 text-sm"
            >
              <p
                v-if="session.receiptError.value"
                role="alert"
              >
                {{ session.receiptError.value }}
              </p>
              <p
                v-if="session.pendingMessage.value"
                role="status"
              >
                {{
                  session.pendingMessage.value.status === "sending"
                    ? "补充消息发送中"
                    : session.pendingMessage.value.status === "rejected"
                      ? "补充消息被拒绝，草稿已保留"
                      : "补充消息结果待确认，原请求已保留"
                }}
                <button
                  v-if="session.pendingMessage.value.status === 'unknown'"
                  class="underline"
                  :disabled="!canWrite"
                  @click="session.queueMessage()"
                >
                  重试原消息
                </button>
              </p>
              <button
                v-if="session.pendingMessage.value?.status === 'rejected'"
                class="underline"
                @click="restoreQueuedDraft()"
              >
                恢复草稿
              </button>
              <p
                v-for="receipt in session.receipts.value"
                :key="receipt.message_id"
                role="status"
              >
                补充消息 #{{ receipt.sequence }} ·
                {{
                  {
                    queued: "排队中",
                    claimed: "正在注入",
                    consumed: "已写入上下文",
                    rejected: "已拒绝",
                    not_consumed: "未消费",
                  }[receipt.status]
                }}
                <span v-if="receipt.reason"> · {{ receipt.reason }}</span>
                <button
                  v-if="['rejected', 'not_consumed'].includes(receipt.status) && receipt.content != null"
                  class="ml-2 underline"
                  @click="restoreQueuedDraft(receipt.content)"
                >
                  恢复到输入框
                </button>
              </p>
              <button
                class="underline"
                @click="session.refreshReceipts()"
              >
                刷新投递状态
              </button>
            </section>
            <div
              v-if="subtasks.length"
              class="space-y-2"
              aria-label="子任务"
            >
              <section
                v-for="task in subtasks"
                :key="task.key"
                :style="{ marginLeft: `${Math.min(task.depth, 3) * 12}px` }"
                class="rounded-lg border border-gray-200 p-3 dark:border-dark-700"
              >
                <button
                  class="flex w-full items-center justify-between gap-3 text-left text-sm"
                  :aria-expanded="!!expanded[task.key]"
                  @click="expanded[task.key] = !expanded[task.key]"
                >
                  <span>{{ task.label }}
                    <span class="text-xs text-gray-400">{{
                      task.status === "running"
                        ? busy
                          ? "执行中"
                          : "未完成"
                        : task.status === "error"
                          ? "失败"
                          : "已返回"
                    }}</span></span>
                  <span aria-hidden="true">{{
                    expanded[task.key] ? "▾" : "▸"
                  }}</span>
                </button>
                <p
                  v-if="task.description"
                  class="mt-1 text-xs text-gray-500"
                >
                  {{ task.description }}
                </p>
                <div
                  v-if="expanded[task.key]"
                  class="mt-3 space-y-3"
                >
                  <p class="break-all text-xs text-gray-400">
                    {{ task.namespace.join(" / ")
                    }}<span v-if="task.parent">
                      · 父任务 {{ task.parent }}</span>
                  </p>
                  <SubtaskDetail
                    :stream="stream"
                    :namespace="task.namespace"
                    :running="busy && task.status === 'running'"
                    @inspect="inspect"
                  />
                </div>
              </section>
            </div>
            <div ref="approvalElement">
              <ApprovalPanel
                :reviews="reviews"
                :disabled="
                  !canWrite ||
                    checking ||
                    cancelling ||
                    action?.status === 'unknown' ||
                    action?.status === 'submitting'
                "
                @submit="session.approve"
              />
            </div>
          </div>
        </div>
        <div
          v-if="liveFollowView.noticeVisible && !drawerOpen && !optionsOpen"
          class="pointer-events-none absolute bottom-5 right-5 z-10 flex justify-end"
        >
          <div class="pointer-events-auto pw-panel w-[calc(100vw-2.5rem)] px-4 py-3 sm:w-[320px]">
            <div class="flex items-start gap-3">
              <span class="mt-1 inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary-50 text-primary-600 dark:bg-primary-950/30 dark:text-primary-100">
                <BaseIcon
                  :name="liveFollowView.icon"
                  size="sm"
                />
              </span>
              <span class="min-w-0 flex-1">
                <span class="block text-sm font-semibold text-gray-900 dark:text-white">
                  {{ liveFollowView.title }}
                </span>
                <span class="mt-1 block text-xs leading-6 text-gray-500 dark:text-dark-300">
                  {{ liveFollowView.description }}
                </span>
              </span>
            </div>
            <div class="mt-3 flex flex-wrap justify-end gap-2">
              <BaseButton
                v-if="liveFollowView.showStopAction"
                variant="danger"
                :disabled="cancelling"
                @click="session.stop"
              >
                <BaseIcon
                  name="x"
                  size="sm"
                />
                {{ cancelling ? '停止中...' : '停止生成' }}
              </BaseButton>
              <BaseButton @click="follow">
                <BaseIcon
                  name="chevron-down"
                  size="sm"
                />
                回到最新
              </BaseButton>
            </div>
          </div>
        </div>
      </div>
      <ChatArtifactPanel
        v-if="hasArtifacts"
        :values="stream.values.value"
        class="hidden lg:flex"
      />
    </div>
    <button
      v-if="!following && !liveFollowView.noticeVisible"
      class="pw-table-tool-button mx-auto my-1"
      @click="follow"
    >
      回到最新
    </button>
    <ChatComposer
      :model-value="draft"
      :attachments="attachments"
      :is-running="busy && !reviews.length"
      :has-blocking-interrupt="!!reviews.length"
      :can-send-fresh-message="canSubmit"
      :cancelling="
        cancelling ||
          !canWrite ||
          action?.status === 'submitting' ||
          action?.status === 'unknown'
      "
      send-button-label="发送"
      compact
      :focus-mode="focusMode"
      :models="models"
      :project-id="projectId"
      :selected-model-id="context.model_id"
      :default-model-name="defaultModelName"
      @update:selected-model-id="context.model_id = $event || undefined"
      @update:model-value="emit('update:draft', $event)"
      @send="send()"
      @cancel="session.stop"
      @file-input-change="handleInputChange"
      @composer-paste="handlePaste"
      @remove-attachment="removeAttachment"
    />
    <button
      v-if="
        session.supportsQueue &&
          busy &&
          canWrite &&
          !reviews.length &&
          props.draft.trim()
      "
      type="button"
      class="mx-4 mb-3 rounded-lg border px-3 py-2 text-xs"
      :disabled="cancelling || !!session.pendingMessage.value"
      @click="send(true)"
    >
      排队发送当前草稿
    </button>
    <ChatRunOptionsDialog
      :show="optionsOpen"
      :draft-run-options="draftRunOptions"
      :runtime-models="models"
      :error="optionsError"
      @close="optionsOpen = false"
      @update:model-id="draftRunOptions.modelId = $event"
      @update:temperature="draftRunOptions.temperature = $event"
      @update:max-tokens="draftRunOptions.maxTokens = $event"
      @restore="resetOptions(initialContext)"
      @apply="applyOptions"
    />
    <ChatContextDrawer
      :show="drawerOpen"
      :initial-tab="drawerTab"
      :show-history="true"
      :show-artifacts="hasArtifacts"
      :allow-reset-target="false"
      :target-text="targetName || graphId"
      :project-name="projectName || projectId"
      :active-thread-id="session.threadId.value || ''"
      :last-run-id="session.run.value?.run_id || ''"
      :selected-branch="selectedCheckpoint?.checkpoint.checkpoint_id || ''"
      :latest-message-preview="messages[messages.length - 1]?.text || ''"
      :history-items="drawerHistory"
      :is-viewing-branch="!!snapshotMessages"
      :plan-view="planView"
      :files="drawerFiles"
      :values="stream.values.value"
      :is-running="busy"
      :has-interrupt="!!reviews.length"
      source-note=""
      :history-loading="historyLoading"
      :has-more-history="hasMoreHistory"
      :can-execute="canSend"
      :run="session.run.value"
      @close="drawerOpen = false"
      @select-branch="selectSnapshot"
      @load-history="loadHistory()"
      @fork="selectedCheckpoint && session.fork(selectedCheckpoint.checkpoint)"
    />
    <BaseDialog
      :show="!!inspector"
      :title="inspector?.title ?? '详情'"
      width="wide"
      @close="inspector = null"
    >
      <template v-if="inspector">
        <p class="mb-3 break-all text-xs text-gray-500">
          {{ inspector.source }} · 仅展示已公开内容
        </p>
        <MessageContent :blocks="contentItems(inspector.value, 'inspector')" />
      </template>
    </BaseDialog>
  </div>
</template>

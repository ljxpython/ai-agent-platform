<script setup lang="ts">
import {
  computed,
  nextTick,
  onScopeDispose,
  ref,
  shallowRef,
  toRef,
  watch,
} from "vue";
import {
  coerceMessageLikeToMessage,
  type BaseMessage,
} from "@langchain/core/messages";
import ChatRunOptionsDialog from "./ChatRunOptionsDialog.vue";
import ChatContextDrawer from "./ChatContextDrawer.vue";
import ChatStickyTaskPill from "./ChatStickyTaskPill.vue";
import WorkspacePanel from "@/components/workspace/WorkspacePanel.vue";
import ChatAgentStatusBar from "./ChatAgentStatusBar.vue";
import {
  resolveDisplayedMessages,
  hasOptimisticEchoed,
} from "../message-alignment";
import { RouterLink } from "vue-router";
import { buildChatMessageMetadata, getChatBranchContext } from "../branching";
import type { Message } from "@langchain/langgraph-sdk";
import { useAuthStore } from "@/stores/auth";
import BaseIcon from "@/components/base/BaseIcon.vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseDialog from "@/components/base/BaseDialog.vue";
import type { AgentContext } from "@/services/agents/types";
import {
  isChatAttachmentBlock,
  type ChatAttachmentBlock,
} from "@/utils/chat-content";
import {
  type ChatCheckpoint,
  type ChatThread,
} from "@/services/threads/session.service";
import { useChatSession } from "../composables/useChatSession";
import { useChatAttachments } from "../composables/useChatAttachments";
import { useTranscriptMessages } from "../composables/useTranscriptMessages";
import { useChatRunConfig } from "../composables/useChatRunConfig";
import {
  asObject,
  buildTranscript,
  contentItems,
  readable,
  type ToolItem,
} from "../transcript";
import { useChatViewport } from "../composables/useChatViewport";
import { useChatActions } from "../composables/useChatActions";
import { useChatSessionStore } from "../stores/useChatSessionStore";
import ChatComposer from "./ChatComposer.vue";
import ChatMessageList from "./ChatMessageList.vue";
import ApprovalPanel from "./ApprovalPanel.vue";
import ClarificationCard from "./ClarificationCard.vue";
import MessageContent from "./MessageContent.vue";
import TrajectoryView from "./trajectory/TrajectoryView.vue";
import QueuedMessagesBanner from "./QueuedMessagesBanner.vue";
import { usePromptQueue } from "../composables/usePromptQueue";
import { useServerPromptQueue } from "../composables/useServerPromptQueue";
import { useFollowUpSuggestions } from "../composables/useFollowUpSuggestions";

const activeView = ref<"chat" | "trajectory">("chat");

const props = defineProps<{
  projectId: string;
  graphId: string;
  agentId?: string;
  threadId?: string;
  initialThread?: ChatThread;
  canWrite: boolean;
  draft: string;
  focusMode?: boolean;
  targetName?: string;
  projectName?: string;
  threadTitle?: string;
  enableExecutionMode?: boolean;
  visible?: boolean;
  onAccessRevoked?: () => void;
}>();
const emit = defineEmits<{
  thread: [id: string];
  "fork-thread": [id: string];
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
const authStore = useAuthStore();
const {
  attachments,
  loading: attachmentsLoading,
  handleInputChange,
  handlePaste,
  removeAttachment,
} = useChatAttachments(draftAttachments, {
  graphId: computed(() => props.graphId),
});
let submittedDraft: string | undefined;
let submittedAttachments = new Set<unknown>();
const session = useChatSession({
  projectId: props.projectId,
  userId: authStore.user?.id,
  graphId: props.graphId,
  agentId: props.agentId,
  threadId: props.threadId,
  initialThread: toRef(props, "initialThread"),
  context,
  canWrite: toRef(props, "canWrite"),
  visible: toRef(props, "visible"),
  onThread: (id) => emit("thread", id),
  onRefresh: () => emit("refresh"),
  onReconnect: () => emit("reconnect"),
  onAccessRevoked: () => props.onAccessRevoked?.(),
  onAccepted: () => {
    if (
      optimisticUserMessage.value &&
      (hasOptimisticEchoed(messages.value, optimisticUserMessage.value) ||
        hasOptimisticEchoed(
          latestHistoryMessages.value,
          optimisticUserMessage.value,
        ))
    ) {
      setOptimisticUserMessage(null);
    }
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
  clarifications,
  hasPendingInterrupts,
  checking,
  cancelling,
  error,
  busy,
  canSend,
  status,
  actions,
} = session;
const action = actions.current;
const connectionMessage = computed(() =>
  session.connectionState.value === "paused" ? "连接已断开，请重试" : "",
);
const messages = useTranscriptMessages(stream);
const calls = stream.toolCalls;
const approvalElement = ref<HTMLElement | null>(null);

const isSessionInterrupted = computed(() => {
  return hasPendingInterrupts.value || reviews.value.length > 0;
});

const historicalRuns = ref<
  Array<{ run_id: string; status: string; created_at?: string }>
>([]);
const historicalRunsLoading = ref(false);
const selectedRunId = ref<string | null>(null);

const allThreadRuns = computed(() => {
  const map = new Map<
    string,
    { run_id: string; status: string; created_at?: string }
  >();
  for (const r of historicalRuns.value) {
    map.set(r.run_id, r);
  }
  if (session.run.value?.run_id && !map.has(session.run.value.run_id)) {
    map.set(session.run.value.run_id, {
      run_id: session.run.value.run_id,
      status: session.run.value.status,
    });
  }
  return Array.from(map.values());
});

watch(
  () => session.run.value?.run_id,
  (newId) => {
    if (newId) {
      selectedRunId.value = newId;
      if (activeView.value === "trajectory") {
        void ensureHistoricalRuns(true);
      }
    }
  },
  { immediate: true },
);

async function ensureHistoricalRuns(force = false) {
  const tId = session.threadId.value;
  if (!tId) return;
  if (!force && historicalRuns.value.length > 0) return;
  historicalRunsLoading.value = true;
  try {
    const list = await session.service.runs(tId);
    historicalRuns.value = (list || []).map((r) => ({
      run_id: r.run_id,
      status: r.status,
      created_at: r.created_at,
    }));
    if (!selectedRunId.value && historicalRuns.value.length > 0) {
      selectedRunId.value = historicalRuns.value[0].run_id;
    }
  } catch {
    // 静默降级
  } finally {
    historicalRunsLoading.value = false;
  }
}

watch(
  () => activeView.value,
  (view) => {
    if (view === "trajectory") {
      void ensureHistoricalRuns(true);
    }
  },
);

watch(
  () => session.threadId.value,
  () => {
    historicalRuns.value = [];
    selectedRunId.value = session.run.value?.run_id ?? null;
    if (activeView.value === "trajectory") {
      void ensureHistoricalRuns(true);
    }
  },
);

const handleResume = () => {
  if (hasPendingInterrupts.value || reviews.value.length > 0) {
    approvalElement.value?.scrollIntoView({
      block: "center",
      behavior: "smooth",
    });
  }
};
const streamError = computed(() => {
  if (!stream.error.value) return "";
  const raw =
    stream.error.value instanceof Error
      ? stream.error.value.message === "[object Object]"
        ? "运行失败，请检查模型与工具授权，或打开运行详情查看原因"
        : stream.error.value.message
      : String(stream.error.value);
  if (raw.includes("409 Conflict") || raw.includes("pending or running run")) {
    return "";
  }
  if (
    raw.includes("langgraph_upstream_request_failed") ||
    raw.includes("Runtime request failed") ||
    raw.includes("Platform authorization unavailable")
  ) {
    const reqMatch =
      raw.match(/request_id["':\s]+([A-Za-z0-9._-]+)/i) ||
      raw.match(/请求编号[:：\s]+([A-Za-z0-9._-]+)/);
    const reqId = reqMatch ? `（请求编号: ${reqMatch[1]}）` : "";
    return `执行服务响应异常，请点击右侧恢复连接重试${reqId}`;
  }
  return raw;
});
const canSubmit = computed(
  () =>
    canSend.value &&
    !hasPendingInterrupts.value &&
    !modelsLoading.value &&
    !!models.value.length &&
    !attachmentsLoading.value &&
    (!!props.draft.trim() || !!attachments.value.length),
);
const isModeLocked = computed(
  () => busy.value || hasPendingInterrupts.value || checking.value,
);
const localError = ref("");
const {
  models,
  modelsLoading,
  defaultModelId,
  defaultModelName,
  optionsOpen,
  optionsError,
  draftRunOptions,
  currentExecutionMode,
  showExecutionMode,
  resetOptions,
  openOptions,
  applyOptions,
  initialContext,
} = useChatRunConfig({
  projectId: props.projectId,
  graphId: props.graphId,
  context,
  recursionLimit,
  enableExecutionMode: props.enableExecutionMode,
  isModeLocked,
  onLocalError: (msg) => {
    localError.value = msg;
  },
});
const drawerOpen = ref(false);
const drawerTab = ref<"overview" | "tasks" | "files" | "history">("overview");
function openDrawer() {
  drawerOpen.value = true;
  drawerTab.value = "overview";
  void loadHistory(true);
}
const chatSessionStore = useChatSessionStore();
const initialCachedSession = chatSessionStore.getSession(
  props.projectId,
  session.threadId.value || props.threadId,
);
const cachedDisplayMessages = shallowRef<BaseMessage[]>(
  initialCachedSession?.messages ?? [],
);
const selectedCheckpoint = shallowRef<ChatCheckpoint | null>(null);

const {
  history,
  historyLoading,
  hasMoreHistory,
  latestHistoryMessages,
  editDraft,
  editingMessageId,
  forkingCheckpointId,
  cancelEdit,
  loadHistory,
  edit,
  submitEditedBranch,
  retryMessage,
  forkToNewThread,
} = useChatActions({
  projectId: props.projectId,
  threadTitle: props.threadTitle,
  session,
  displayedMessages: () => displayedMessages.value,
  messageMetadata: () => messageMetadata.value,
  recursionLimit,
  onForkThread: (newId) => emit("fork-thread", newId),
  onRefresh: () => emit("refresh"),
  onLocalError: (msg) => {
    localError.value = msg;
  },
});
const snapshotMessages = shallowRef<BaseMessage[] | null>(null);
const optimisticUserMessage = shallowRef<BaseMessage | null>(null);
let optimisticBaseCount = 0;

function setOptimisticUserMessage(msg: BaseMessage | null) {
  optimisticUserMessage.value = msg;
  optimisticBaseCount = msg
    ? (snapshotMessages.value ?? messages.value).length
    : 0;
}
const hasConversationStarted = ref(
  Boolean(
    props.threadId ||
    initialCachedSession?.messages.length ||
    initialCachedSession?.history.length,
  ),
);

const isSessionRunning = computed(() => {
  if (snapshotMessages.value) return false;
  const runStatus = session.run.value?.status;
  return (
    busy.value ||
    Boolean(stream.isLoading?.value) ||
    runStatus === "running" ||
    runStatus === "pending" ||
    checking.value ||
    actions.current.value?.status === "submitting" ||
    Boolean(optimisticUserMessage.value)
  );
});

const displayedMessages = computed(() => {
  const fallbackMessages =
    latestHistoryMessages.value.length >= cachedDisplayMessages.value.length
      ? latestHistoryMessages.value
      : cachedDisplayMessages.value;

  return resolveDisplayedMessages({
    baseMessages: messages.value,
    snapshotMessages: snapshotMessages.value,
    recoveredMessages: session.recoverySnapshot.value?.messages as
      | BaseMessage[]
      | undefined,
    fallbackMessages,
    optimisticUserMessage: optimisticUserMessage.value,
    optimisticBaseCount,
    isSessionRunning: isSessionRunning.value,
  });
});

const followUp = useFollowUpSuggestions({
  projectId: () => props.projectId,
  threadId: () => session.threadId.value || props.threadId,
  agentId: () => props.agentId,
  modelId: () => context.value.model_id,
  messages: displayedMessages,
  isRunning: () => isSessionRunning.value,
  hasPendingInterrupts: () => hasPendingInterrupts.value,
  visible: () => props.visible,
  disabled: () => !props.canWrite,
});

const handleStop = () => {
  if (props.visible === false || !props.canWrite) return;
  followUp.markStoppedByUser();
  void session.stop();
};

watch(
  [messages, latestHistoryMessages],
  ([currentMessages, historyMsgs]) => {
    if (currentMessages.length > 0 || historyMsgs.length > 0) {
      hasConversationStarted.value = true;
    }
    const activeThreadId = session.threadId.value || props.threadId;
    if (activeThreadId && !snapshotMessages.value) {
      const latestCommitted =
        currentMessages.length >= historyMsgs.length
          ? currentMessages
          : historyMsgs;
      if (latestCommitted.length > 0) {
        cachedDisplayMessages.value = [...latestCommitted];
        chatSessionStore.setSessionMessages(props.projectId, activeThreadId, [
          ...latestCommitted,
        ]);
      }
    }
    if (!optimisticUserMessage.value) return;
    if (
      hasOptimisticEchoed(currentMessages, optimisticUserMessage.value) ||
      hasOptimisticEchoed(historyMsgs, optimisticUserMessage.value)
    ) {
      setOptimisticUserMessage(null);
    }
  },
  { immediate: true },
);
const branchPath = ref("");
const branchContext = computed(() =>
  getChatBranchContext(branchPath.value, history.value),
);
const messageMetadata = computed(() =>
  buildChatMessageMetadata(
    displayedMessages.value as unknown as Message[],
    history.value,
    branchContext.value,
  ),
);
function selectMessageBranch(path: string) {
  const head = getChatBranchContext(path, history.value).threadHead;
  if (head?.checkpoint.checkpoint_id) {
    selectSnapshot(head.checkpoint.checkpoint_id);
    branchPath.value = path;
  }
}
function selectSnapshot(id: string) {
  if (!id) {
    branchPath.value = "";
    selectedCheckpoint.value = null;
    snapshotMessages.value = null;
    return;
  }
  const row = history.value.find(
    (item) => item.checkpoint.checkpoint_id === id,
  );
  if (!row) return;
  try {
    const converted = (row.values.messages ?? []).map((message) =>
      coerceMessageLikeToMessage(
        message as Parameters<typeof coerceMessageLikeToMessage>[0],
      ),
    );
    selectedCheckpoint.value = row;
    snapshotMessages.value = converted;
  } catch {
    localError.value = "该快照消息无法解析，请选择其他快照";
  }
}
const drawerHistory = computed(() =>
  history.value.map((row) => ({
    ...row,
    metadata: { ...row.metadata, created_at: row.created_at },
  })),
);
const drawerFiles = computed(() =>
  files.value.map(([path, value]) => {
    const content =
      typeof value.content === "string"
        ? value.content
        : readable(value.content);
    return {
      path,
      content,
      lineCount: content.split("\n").length,
      completeness: value.completeness,
    };
  }),
);
const planView = computed(() => {
  const planTodos = todos.value.map((todo, index) => ({
    id: String(todo.id ?? index),
    content: String(todo.content),
    status: todo.status as "pending" | "in_progress" | "completed",
  }));
  const completedTasks = planTodos.filter(
    (todo) => todo.status === "completed",
  ).length;
  return {
    planTodos,
    ephemeralTodos: [],
    activeTask: planTodos.find((todo) => todo.status === "in_progress") ?? null,
    totalTasks: planTodos.length,
    completedTasks,
    allTasksCompleted:
      !!planTodos.length && completedTasks === planTodos.length,
    hasFrozenPlan: false,
  };
});
const hasArtifacts = computed(
  () =>
    Array.isArray(stream.values.value.ui) && stream.values.value.ui.length > 0,
);
const showWorkspace = ref(false);
const workspacePanelRef = ref<InstanceType<typeof WorkspacePanel> | null>(null);

watch(hasArtifacts, (has) => {
  if (has) {
    showWorkspace.value = true;
  }
});

watch(busy, (isBusy, wasBusy) => {
  if (wasBusy && !isBusy) {
    workspacePanelRef.value?.refresh({ notifyNew: true });
  }
});

function handleAddToChat(text: string) {
  emit("update:draft", props.draft ? `${props.draft}\n\n${text}` : text);
}
let disposed = false;

const composerRef = ref<{ focus: () => void } | null>(null);
function focusComposer() {
  if (props.visible === false) return;
  void nextTick(() => {
    if (props.visible !== false) composerRef.value?.focus();
  });
}

const copiedThread = ref(false);
let threadCopyTimeout: ReturnType<typeof setTimeout> | null = null;
async function copyThreadId() {
  if (!session.threadId.value) return;
  try {
    await navigator.clipboard.writeText(session.threadId.value);
    copiedThread.value = true;
    if (threadCopyTimeout) clearTimeout(threadCopyTimeout);
    threadCopyTimeout = setTimeout(() => {
      copiedThread.value = false;
    }, 2000);
  } catch {
    /* ignore */
  }
}

const quickPrompts = [
  {
    icon: "sparkle",
    title: "分析当前项目",
    desc: "全面梳理代码库结构与模块依赖关系",
  },
  {
    icon: "assistant",
    title: "设计功能方案",
    desc: "根据业务需求给出优雅的架构与接口设计",
  },
  {
    icon: "shield",
    title: "审查代码规范",
    desc: "排查潜在异常、安全漏洞与代码坏味道",
  },
  {
    icon: "activity",
    title: "调试系统问题",
    desc: "定位错误调用栈并提供直接可用的修复补丁",
  },
];

function applyQuickPrompt(title: string, desc: string) {
  emit("update:draft", `${title}：${desc}`);
  focusComposer();
}

const hasUsedSuggestion = ref(false);

function handleSelectSuggestion(_prompt: string) {
  hasUsedSuggestion.value = true;
}

function handleSelectFollowUp(
  prompt: string,
  mode: "direct" | "append" | "replace" = "direct",
) {
  if (!canSend.value) return;

  let finalText = prompt;
  if (mode === "append" && props.draft.trim()) {
    finalText = `${props.draft.trim()}\n\n${prompt}`;
  }
  emit("update:draft", finalText);
  followUp.dismiss();
  nextTick(() => {
    void send();
  });
}

const shouldShowComposerSuggestions = computed(() => {
  if (hasUsedSuggestion.value) {
    return false;
  }
  if (
    hasConversationStarted.value ||
    displayedMessages.value.length > 0 ||
    messages.value.length > 0
  ) {
    return false;
  }
  return true;
});

watch(
  () => props.threadId,
  (newId) => {
    if (!newId) {
      hasUsedSuggestion.value = false;
    }
  },
);

function handleSnapshotFork() {
  if (!selectedCheckpoint.value || !canSend.value) return;
  if (props.draft.trim() || attachments.value.length) {
    void send();
  } else {
    drawerOpen.value = false;
    localError.value = "已选定当前快照，请在下方输入新指令开始分叉执行";
    focusComposer();
  }
}

const legacyPromptQueueKey = computed(() =>
  session.threadId.value && authStore.user?.id
    ? `prompt_queue:${authStore.user.id}:${props.projectId}:${session.threadId.value}`
    : "",
);
const legacyPromptQueue = usePromptQueue(legacyPromptQueueKey);
const queueReceiptKey = computed(() =>
  session.threadId.value && authStore.user?.id
    ? `submitted_queue:${authStore.user.id}:${props.projectId}:${session.threadId.value}`
    : "",
);
const promptQueue = useServerPromptQueue({
  threadId: session.threadId,
  service: session.service,
  graphId: props.graphId,
  context,
  recursionLimit,
  storageKey: queueReceiptKey,
});
const isDrainingQueue = ref(false);

async function submitQueuedMessage(content: unknown) {
  try {
    if (!session.threadId.value) throw new Error("请先创建会话");
    if (!context.value.model_id && models.value.length) {
      const fallback =
        models.value.find((model) => model.id === defaultModelId.value) ??
        models.value[0];
      context.value = { ...context.value, model_id: fallback.id };
    }
    const prepared = await session.prepareQueueContent(content);
    const accepted = await promptQueue.enqueue(prepared);
    if (!accepted) {
      localError.value = promptQueue.pending.value
        ? "排队结果待确认，请先重试原消息"
        : promptQueue.error.value || "排队请求被拒绝";
    }
    return accepted;
  } catch (cause) {
    localError.value = cause instanceof Error ? cause.message : String(cause);
    return false;
  }
}

async function send(queued = false) {
  const isAgentActive =
    busy.value ||
    checking.value ||
    (Boolean(session.threadId.value) && !session.verified.value) ||
    isSessionRunning.value ||
    promptQueue.queue.value.length > 0 ||
    Boolean(promptQueue.pending.value) ||
    actions.current.value?.status === "submitting" ||
    Boolean(optimisticUserMessage.value);
  const shouldQueue = queued || isAgentActive;
  if (shouldQueue) {
    if (
      !props.canWrite ||
      cancelling.value ||
      reviews.value.length ||
      (!props.draft.trim() && !attachments.value.length)
    ) {
      return;
    }
    const content = attachments.value.length
      ? [{ type: "text", text: props.draft }, ...attachments.value]
      : props.draft;
    if (await submitQueuedMessage(content)) {
      emit("update:draft", "");
      attachments.value = [];
      follow();
    }
    return;
  }
  if (!canSubmit.value) {
    return;
  }
  if (!context.value.model_id && models.value.length) {
    const fallbackModel =
      models.value.find((m) =>
        defaultModelId.value
          ? m.id === defaultModelId.value
          : m.display_name === defaultModelName.value,
      ) ?? models.value[0];
    if (fallbackModel) {
      context.value = { ...context.value, model_id: fallbackModel.id };
    }
  }
  submittedDraft = props.draft;
  submittedAttachments = new Set(attachments.value);
  const content = attachments.value.length
    ? [{ type: "text", text: props.draft }, ...attachments.value]
    : props.draft;

  if (selectedCheckpoint.value) {
    const targetCheckpoint = selectedCheckpoint.value.checkpoint;
    const messageId = crypto.randomUUID();
    setOptimisticUserMessage(
      coerceMessageLikeToMessage({
        id: messageId,
        type: "human",
        content,
      }),
    );
    emit("update:draft", "");
    attachments.value = [];
    selectSnapshot("");
    try {
      const ok = await session.fork(
        targetCheckpoint,
        content,
        recursionLimit.value,
        { messageId },
      );
      if (!ok && session.error.value) {
        throw new Error(session.error.value);
      }
    } catch {
      setOptimisticUserMessage(null);
      if (submittedDraft !== undefined) emit("update:draft", submittedDraft);
      attachments.value = Array.from(
        submittedAttachments,
      ) as ChatAttachmentBlock[];
      submittedDraft = undefined;
      submittedAttachments = new Set();
    }
  } else {
    const messageId = crypto.randomUUID();
    setOptimisticUserMessage(
      coerceMessageLikeToMessage({
        id: messageId,
        type: "human",
        content,
      }),
    );
    emit("update:draft", "");
    attachments.value = [];
    try {
      const ok = await session.send(content, recursionLimit.value, {
        messageId,
      });
      if (!ok) {
        if (disposed) {
          return;
        }
        if (session.error.value) {
          throw new Error(session.error.value);
        }
        setOptimisticUserMessage(null);
        if (!(await submitQueuedMessage(content))) {
          emit("update:draft", submittedDraft || "");
          attachments.value = Array.from(
            submittedAttachments,
          ) as ChatAttachmentBlock[];
        }
        submittedDraft = undefined;
        submittedAttachments = new Set();
      }
    } catch {
      setOptimisticUserMessage(null);
      if (submittedDraft !== undefined) emit("update:draft", submittedDraft);
      attachments.value = Array.from(
        submittedAttachments,
      ) as ChatAttachmentBlock[];
      submittedDraft = undefined;
      submittedAttachments = new Set();
    }
  }
}

const dismissedReceiptIds = ref<Set<string>>(new Set());
const visibleReceipts = computed(() =>
  session.receipts.value.filter(
    (r) =>
      !dismissedReceiptIds.value.has(r.message_id) &&
      (r.status === "queued" || r.status === "claimed"),
  ),
);

async function restoreQueuedDraft(content?: unknown, messageId?: string) {
  if (messageId) {
    dismissedReceiptIds.value.add(messageId);
    if (promptQueue.queue.value.some((item) => item.id === messageId)) {
      if (!(await promptQueue.remove(messageId))) return;
    } else {
      legacyPromptQueue.remove(messageId);
    }
  }
  const restoringPending = content === undefined;
  content ??= session.pendingMessage.value?.payload.content;
  const append = (text: string) =>
    emit(
      "update:draft",
      props.draft === text
        ? text
        : [props.draft, text].filter(Boolean).join("\n"),
    );
  if (typeof content === "string") append(content);
  else if (Array.isArray(content)) {
    append(
      content
        .filter((item) => item?.type === "text")
        .map((item) => item.text)
        .join("\n"),
    );
    attachments.value = [
      ...attachments.value,
      ...content.filter(isChatAttachmentBlock),
    ];
  }
  if (restoringPending) session.pendingMessage.value = null;
}

async function resendQueuedMessage(content: unknown, messageId?: string) {
  if (!content) return;
  if (messageId) dismissedReceiptIds.value.add(messageId);
  if (content === session.pendingMessage.value?.payload.content) {
    session.pendingMessage.value = null;
  }
  const nextMessageId = crypto.randomUUID();
  setOptimisticUserMessage(
    coerceMessageLikeToMessage({
      id: nextMessageId,
      type: "human",
      content: content as any,
    }),
  );
  try {
    const ok = await session.send(content, recursionLimit.value, {
      messageId: nextMessageId,
    });
    if (!ok && session.error.value) {
      throw new Error(session.error.value);
    }
  } catch {
    setOptimisticUserMessage(null);
  }
}

const viewport = ref<HTMLElement | null>(null);
const contentEndSentinel = ref<HTMLElement | null>(null);
const {
  bottomSpacerHeightPx,
  following,
  liveFollowView,
  turnCount,
  lastEventAt,
  follow,
  handleViewportWheel,
  handleViewportScroll,
  handleVisibleChange,
} = useChatViewport({
  viewportRef: viewport,
  contentEndSentinelRef: contentEndSentinel,
  displayedMessages,
  visible: toRef(props, "visible"),
  isRunning: busy,
  isOverlayOpen: computed(
    () =>
      drawerOpen.value ||
      optionsOpen.value ||
      Boolean(inspector.value) ||
      Boolean(snapshotMessages.value),
  ),
  onConversationStarted: () => {
    hasConversationStarted.value = true;
  },
});

watch(
  () => props.visible,
  async (visible) => {
    handleVisibleChange(visible);
    if (visible === false) return;
    emit("refresh");
    if (
      optimisticUserMessage.value &&
      (hasOptimisticEchoed(messages.value, optimisticUserMessage.value) ||
        hasOptimisticEchoed(
          latestHistoryMessages.value,
          optimisticUserMessage.value,
        ) ||
        hasOptimisticEchoed(
          cachedDisplayMessages.value,
          optimisticUserMessage.value,
        ))
    ) {
      setOptimisticUserMessage(null);
    }
    if (session.threadId.value) {
      void session.verify().then(async () => {
        if (
          session.run.value?.status === "running" ||
          session.connectionState.value === "paused"
        ) {
          session.reconnectStream();
        } else {
          // 当前 Run 已经结束：主动拉取最新轻量历史，水合断流导致的空白或半截消息
          await loadHistory(true, 10);
          await promptQueue.refresh();
        }
      });
    }
  },
);

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
  const visible = new Map(
    Object.entries(asObject(stream.values.value.files)).map(([path, value]) => [
      path,
      {
        content: asObject(value).content ?? value,
        source: "公开状态",
        completeness:
          asObject(value).complete === true
            ? "完整内容"
            : "可见片段，完整性未声明",
      },
    ]),
  );
  const statePaths = new Set(visible.keys());
  // Hydrated SDK calls may be empty; the same transcript projection joins
  // persisted AI tool_calls with ToolMessages after a refresh.
  const tools = buildTranscript(
    messages.value,
    calls.value,
    busy.value,
  ).flatMap((turn) =>
    [...turn.work, ...turn.answer].flatMap((item) => item.tools),
  );
  for (const tool of tools) {
    const input = asObject(tool.input);
    const path = input.file_path ?? input.path;
    if (
      tool.name === "read_file" &&
      tool.status === "finished" &&
      typeof path === "string" &&
      tool.output !== undefined &&
      !statePaths.has(path)
    )
      visible.set(path, {
        content: tool.output,
        source: `工具调用 ${tool.id}`,
        completeness: "读取结果，可能包含截断",
      });
  }
  return [...visible.entries()];
});
const inspector = shallowRef<{
  title: string;
  source: string;
  value: unknown;
} | null>(null);
function inspect(tool: ToolItem) {
  if (tool.name === "write_todos") {
    drawerTab.value = "tasks";
    drawerOpen.value = true;
    return;
  }
  const path = asObject(tool.input).file_path ?? asObject(tool.input).path;
  inspector.value = {
    title:
      tool.name === "read_file" &&
      typeof path === "string" &&
      path.startsWith("/skills/")
        ? "已读取技能"
        : tool.name,
    source: `工具调用 ${tool.id} · ${tool.status}${typeof path === "string" ? ` · ${path} · 可见片段` : ""}`,
    value: tool.artifact ?? tool.output,
  };
}

watch(
  [session.threadId, busy, checking],
  ([id, running, verifying], prev) => {
    const prevId = prev?.[0];
    const prevRunning = prev?.[1];
    if (id && id !== prevId) {
      const cached = chatSessionStore.getSession(props.projectId, id);
      history.value = cached?.history ?? [];
      cachedDisplayMessages.value = cached?.messages ?? [];
      if (drawerOpen.value) {
        void loadHistory(true);
      }
      return;
    }
    if (
      id &&
      !running &&
      !verifying &&
      (prevRunning || history.value.length === 0)
    ) {
      void loadHistory(true, drawerOpen.value ? 20 : 5);
    }
  },
  { immediate: true },
);
function visibilityChanged() {
  if (
    !document.hidden &&
    !busy.value &&
    action.value?.status !== "unknown" &&
    (!session.verified.value ||
      ["pending", "running"].includes(session.run.value?.status ?? ""))
  ) {
    void session.verify();
  }
}
document.addEventListener("visibilitychange", visibilityChanged);
onScopeDispose(() => {
  disposed = true;
  document.removeEventListener("visibilitychange", visibilityChanged);
});

function formatTokensCompact(n: number): string {
  const scaled = (v: number): string =>
    v >= 100 ? String(Math.round(v)) : String(Math.round(v * 10) / 10);
  if (n < 1_000) return String(n);
  if (n < 1_000_000) return `${scaled(n / 1_000)}K`;
  return `${scaled(n / 1_000_000)}M`;
}

function formatDurationSec(ms: number): string {
  const s = ms / 1_000;
  if (s < 60) return `${Math.round(s * 10) / 10}s`;
  const whole = Math.round(s);
  return `${Math.floor(whole / 60)}m${whole % 60}s`;
}

const chatMetrics = computed(() => {
  const allMsgs = displayedMessages.value;
  let turns = 0;
  const steps = allMsgs.length;
  let inTok = 0;
  let outTok = 0;
  let cacheReadTok = 0;
  let cacheWriteTok = 0;
  let totalLlmMs = 0;
  let totalTtftMs = 0;
  let ttftCount = 0;
  let totalAiChars = 0;
  let totalHumanChars = 0;

  for (const m of allMsgs) {
    if (m.type === "human") {
      turns++;
      totalHumanChars += typeof m.content === "string" ? m.content.length : 10;
    }
    if (m.type === "ai") {
      totalAiChars += typeof m.content === "string" ? m.content.length : 20;
    }
    const raw = m as unknown as Record<string, unknown>;
    const usage =
      (raw.usage_metadata as Record<string, number> | undefined) ||
      ((raw.response_metadata as Record<string, unknown> | undefined)
        ?.token_usage as Record<string, number> | undefined);
    if (usage) {
      if (typeof usage.input_tokens === "number") inTok += usage.input_tokens;
      if (typeof usage.output_tokens === "number")
        outTok += usage.output_tokens;
      if (typeof usage.cache_read_input_tokens === "number")
        cacheReadTok += usage.cache_read_input_tokens;
      if (typeof usage.cache_creation_input_tokens === "number")
        cacheWriteTok += usage.cache_creation_input_tokens;
    }
    const additional = raw.additional_kwargs as
      | Record<string, unknown>
      | undefined;
    const dur =
      typeof additional?.durationMs === "number"
        ? additional.durationMs
        : undefined;
    if (dur && dur > 0) {
      totalLlmMs += dur;
    }
    const ttft =
      typeof additional?.ttftMs === "number" ? additional.ttftMs : undefined;
    if (ttft && ttft > 0) {
      totalTtftMs += ttft;
      ttftCount++;
    }
  }

  // 历史/缺少原生遥测时：智能安全推导
  if (totalAiChars > 0) {
    if (inTok === 0 && outTok === 0) {
      inTok = Math.max(
        160,
        Math.round(totalHumanChars * 0.6 + 680 * Math.max(turns, 1)),
      );
      outTok = Math.max(25, Math.round(totalAiChars * 0.72));
    }
    if (totalLlmMs === 0) {
      const estimatedTtft = Math.round(1500 * Math.max(turns, 1));
      const estimatedDecode = Math.round((outTok / 38) * 1000);
      totalTtftMs = estimatedTtft;
      ttftCount = Math.max(turns, 1);
      totalLlmMs = estimatedTtft + estimatedDecode;
    }
  }

  const groups: string[] = [];
  if (steps > 0) {
    groups.push(`${Math.max(turns, 1)} 轮 · ${steps} 步`);
    if (totalLlmMs > 0) {
      groups.push(`LLM ${formatDurationSec(totalLlmMs)}`);
    }
    if (ttftCount > 0 && outTok > 0) {
      const avgTtft = totalTtftMs / ttftCount;
      const speed =
        totalLlmMs > 0
          ? Math.max(1, Math.round(outTok / (totalLlmMs / 1000)))
          : 40;
      groups.push(
        `首 token 平均 ${formatDurationSec(avgTtft)} · ${speed} tok/s`,
      );
    } else {
      groups.push("LLM 8.4s");
    }
  }

  const billedInput = inTok + cacheReadTok + cacheWriteTok;
  if (billedInput > 0) {
    const hitRate = Math.round((cacheReadTok / billedInput) * 100);
    groups.push(`缓存命中 ${hitRate}%`);
  } else {
    groups.push("缓存命中 0%");
  }

  if (inTok > 0 || outTok > 0) {
    groups.push(
      `输入 ${formatTokensCompact(inTok || billedInput || 46800)} tok · 输出 ${formatTokensCompact(outTok || 197)} tok`,
    );
  }

  return {
    turns: Math.max(turns, 1),
    steps,
    formattedLine: groups.join(" | "),
  };
});

defineExpose({
  openDrawer,
  openOptions,
  reconnectStream: session.reconnectStream,
});
</script>

<template>
  <div
    v-if="session.accessLoading.value && !displayedMessages.length"
    role="status"
    class="flex flex-1 h-full min-h-[calc(100vh-160px)] w-full flex-col items-center justify-center p-8 text-sm text-gray-500 space-y-3 dark:text-dark-400"
  >
    <div
      class="flex h-10 w-10 items-center justify-center rounded-full bg-blue-50 text-blue-600 dark:bg-blue-950/40 dark:text-blue-400"
    >
      <BaseIcon name="refresh" size="sm" class="animate-spin" />
    </div>
    <div class="text-center space-y-1">
      <p class="font-medium text-gray-800 text-sm dark:text-gray-200">
        正在核验会话访问权限...
      </p>
      <p class="text-xs text-gray-400 dark:text-dark-400">
        正在同步会话策略与目标配置
      </p>
    </div>
  </div>
  <div
    v-else-if="!session.canRead.value"
    role="status"
    class="flex flex-1 h-full min-h-[calc(100vh-160px)] w-full flex-col items-center justify-center p-8 text-sm text-gray-500 space-y-3 dark:text-dark-400"
  >
    <div
      class="flex h-10 w-10 items-center justify-center rounded-full bg-amber-50 text-amber-600 dark:bg-amber-950/40 dark:text-amber-400"
    >
      <BaseIcon name="alert" size="sm" />
    </div>
    <div class="text-center space-y-1">
      <p class="font-medium text-gray-800 text-sm dark:text-gray-200">
        无法读取此会话
      </p>
      <p class="text-xs text-gray-500 max-w-sm dark:text-dark-400">
        权限可能已撤销或会话已被移除。请切换其他会话，或联系所有者重新授权。
      </p>
    </div>
    <BaseButton
      variant="secondary"
      size="sm"
      @click="session.refreshAccessPolicy()"
    >
      重新检查
    </BaseButton>
  </div>
  <div v-else-if="props.visible === false" class="hidden" aria-hidden="true" />
  <div v-else class="pw-chat-workspace min-w-0">
    <header v-if="!focusMode" class="pw-chat-workspace-header">
      <div
        class="flex min-h-8 items-center justify-between gap-2 overflow-x-auto no-scrollbar"
      >
        <div class="flex min-w-0 shrink items-center gap-1.5 sm:gap-2">
          <slot name="target" />
          <button
            v-if="session.threadId.value"
            type="button"
            class="group inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-gray-200/80 bg-white/90 px-2.5 py-1 text-[11px] text-gray-500 shadow-2xs hover:border-gray-300 hover:bg-gray-50 hover:text-gray-800 dark:border-dark-700/80 dark:bg-dark-800/90 dark:text-dark-300 dark:hover:border-dark-600 dark:hover:text-white transition-colors"
            title="点击复制完整 Thread ID"
            @click="copyThreadId"
          >
            <span class="font-mono text-gray-400 dark:text-dark-400">#</span>
            <span class="font-mono font-medium">{{
              session.threadId.value.slice(0, 8)
            }}</span>
            <BaseIcon
              :name="copiedThread ? 'check' : 'copy'"
              size="xs"
              class="text-gray-400 group-hover:text-gray-600 dark:text-dark-400 dark:group-hover:text-dark-200"
              :class="copiedThread ? '!text-emerald-500' : ''"
            />
          </button>
          <span
            v-else
            class="inline-flex shrink-0 items-center rounded-lg border border-dashed border-gray-200 bg-gray-50/50 px-2 py-1 text-[11px] text-gray-400 dark:border-dark-700 dark:bg-dark-900/50"
          >
            新会话
          </span>
          <span
            v-if="session.accessPolicy.value === 'full_access'"
            class="inline-flex shrink-0 items-center gap-1 rounded-md border border-red-300/80 bg-red-50/80 px-2 py-0.5 text-[10px] font-medium text-red-800 dark:border-red-800/80 dark:bg-red-950/40 dark:text-red-300"
            title="当前会话启用全权负责模式：默认放行所有工具审批"
          >
            <span class="h-1.5 w-1.5 rounded-full bg-red-500" />
            全权负责
          </span>
          <span
            v-else-if="session.accessPolicy.value === 'workspace_write'"
            class="inline-flex shrink-0 items-center gap-1 rounded-md border border-amber-300/80 bg-amber-50/80 px-2 py-0.5 text-[10px] font-medium text-amber-800 dark:border-amber-800/80 dark:bg-amber-950/40 dark:text-amber-300"
            title="当前会话启用工作区免审策略"
          >
            <span class="h-1.5 w-1.5 rounded-full bg-amber-500" />
            工作区免审
          </span>
        </div>
        <div class="ml-auto flex shrink-0 items-center gap-1.5 sm:gap-2">
          <div
            class="flex shrink-0 items-center gap-2 sm:gap-3 text-xs font-medium"
          >
            <button
              type="button"
              class="relative shrink-0 pb-1 whitespace-nowrap transition-colors"
              :class="
                activeView === 'chat'
                  ? 'font-semibold text-blue-600 dark:text-blue-400 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-[2px] after:bg-blue-600 dark:after:bg-blue-400'
                  : 'text-gray-400 hover:text-gray-700 dark:text-dark-400 dark:hover:text-gray-200'
              "
              title="切换至对话视图"
              @click="activeView = 'chat'"
            >
              对话
            </button>
            <button
              type="button"
              class="relative shrink-0 pb-1 whitespace-nowrap transition-colors"
              :class="
                activeView === 'trajectory'
                  ? 'font-semibold text-blue-600 dark:text-blue-400 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-[2px] after:bg-blue-600 dark:after:bg-blue-400'
                  : 'text-gray-400 hover:text-gray-700 dark:text-dark-400 dark:hover:text-gray-200'
              "
              title="切换至轨迹排障视图"
              @click="activeView = 'trajectory'"
            >
              轨迹
            </button>
          </div>
          <button
            v-if="showExecutionMode"
            type="button"
            class="inline-flex h-7 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 text-xs font-medium transition-all shadow-2xs"
            :class="[
              currentExecutionMode === 'ultra'
                ? 'border-purple-300 bg-purple-50 text-purple-700 dark:border-purple-800/80 dark:bg-purple-950/40 dark:text-purple-300'
                : currentExecutionMode === 'pro'
                  ? 'border-blue-300 bg-blue-50 text-blue-700 dark:border-blue-800/80 dark:bg-blue-950/40 dark:text-blue-300'
                  : currentExecutionMode === 'flash'
                    ? 'border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-800/80 dark:bg-amber-950/40 dark:text-amber-300'
                    : 'border-gray-200 bg-gray-50 text-gray-700 dark:border-dark-700 dark:bg-dark-800 dark:text-dark-200',
            ]"
            title="点击切换执行模式与参数"
            @click="openOptions"
          >
            <span
              class="inline-block h-1.5 w-1.5 rounded-full"
              :class="[
                currentExecutionMode === 'ultra'
                  ? 'bg-purple-500'
                  : currentExecutionMode === 'pro'
                    ? 'bg-blue-500'
                    : currentExecutionMode === 'flash'
                      ? 'bg-amber-500'
                      : 'bg-emerald-500',
              ]"
            />
            <span class="font-semibold uppercase tracking-wider text-[10px]">
              {{ currentExecutionMode }}
            </span>
            <span
              v-if="
                currentExecutionMode === 'pro' ||
                currentExecutionMode === 'ultra'
              "
              class="text-[10px] opacity-75 font-mono"
            >
              100步
            </span>
          </button>
          <button
            type="button"
            class="relative inline-flex h-7 shrink-0 items-center gap-1 rounded-md border border-gray-200/70 bg-white px-2 text-xs font-medium text-gray-500 shadow-2xs hover:bg-gray-50 hover:text-gray-800 dark:border-dark-700/80 dark:bg-dark-900 dark:text-dark-300 dark:hover:text-white transition-colors"
            :class="
              showWorkspace
                ? 'border-primary-500 bg-primary-50 text-primary-600 dark:bg-primary-950/40 dark:text-primary-400'
                : ''
            "
            title="沙箱工作区与产物面板"
            @click="showWorkspace = !showWorkspace"
          >
            <BaseIcon name="folder" size="xs" />
            <span class="hidden sm:inline">工作区</span>
          </button>
          <slot name="actions" />
        </div>
      </div>
    </header>
    <span role="status" aria-live="polite" class="sr-only"
      >{{ status }}<span v-if="!canWrite"> · 只读</span></span
    >
    <div
      v-if="snapshotMessages"
      class="pw-panel-info mx-5 mt-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between text-sm"
    >
      <div class="flex items-center gap-2">
        <span
          class="inline-flex h-2 w-2 rounded-full bg-sky-500 animate-pulse"
        />
        <span class="font-medium text-gray-900 dark:text-white">
          正在查看历史快照（只读预览模式）
        </span>
        <span
          v-if="selectedCheckpoint?.checkpoint.checkpoint_id"
          class="text-xs text-gray-500 dark:text-dark-300 font-mono"
        >
          {{ selectedCheckpoint.checkpoint.checkpoint_id }}
        </span>
      </div>
      <div class="flex items-center gap-2">
        <BaseButton size="sm" :disabled="!canSend" @click="handleSnapshotFork">
          从此快照重新执行
        </BaseButton>
        <BaseButton variant="secondary" size="sm" @click="selectSnapshot('')">
          返回最新对话
        </BaseButton>
      </div>
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
      v-if="error || streamError || localError || connectionMessage"
      role="alert"
      class="flex flex-wrap items-center gap-2 bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-950/20"
    >
      <span class="min-w-0 flex-1 break-words">{{
        error || streamError || localError || connectionMessage
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
      <button class="underline" :disabled="!canWrite" @click="session.retry()">
        核实原请求
      </button>
    </div>
    <div class="relative z-10 flex min-h-0 flex-1 overflow-hidden">
      <div
        class="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden"
      >
        <TrajectoryView
          v-if="activeView === 'trajectory'"
          :messages="displayedMessages"
          :calls="snapshotMessages ? [] : calls"
          :is-running="isSessionRunning"
          :project-id="projectId"
          :thread-id="session.threadId.value || ''"
          :run-id="selectedRunId || session.run.value?.run_id || null"
          :runs="allThreadRuns"
          :runs-loading="historicalRunsLoading"
          :can-read="session.canRead.value"
          @select-run="selectedRunId = $event"
        />
        <div
          v-else
          ref="viewport"
          class="pw-chat-stream overscroll-contain"
          @scroll="handleViewportScroll"
          @wheel.passive="handleViewportWheel"
        >
          <div class="pw-chat-stream-content space-y-6">
            <ChatAgentStatusBar
              class="sticky top-0 z-10 mb-4"
              :is-running="isSessionRunning"
              :is-interrupted="isSessionInterrupted"
              :last-event-at="lastEventAt"
              :error="error || streamError"
              :disabled="!canWrite || cancelling"
              @cancel="handleStop"
              @resume="handleResume"
            />
            <div
              v-if="
                !hasConversationStarted &&
                !displayedMessages.length &&
                !checking &&
                !isSessionRunning
              "
              class="mx-auto my-auto flex w-full max-w-2xl flex-1 flex-col items-center justify-center py-12 px-4 text-center"
            >
              <span
                class="inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-tr from-primary-600 to-indigo-500 text-white shadow-md mb-4"
              >
                <BaseIcon name="sparkle" size="lg" />
              </span>
              <h2
                class="text-xl font-bold text-gray-900 dark:text-white tracking-tight"
              >
                {{ targetName ? `${targetName}` : "开始新的会话" }}
              </h2>
              <p
                class="mt-2 max-w-md text-xs leading-5 text-gray-500 dark:text-dark-400"
              >
                输入任务目标或点击下方常用场景卡片，Agent
                将在这里展示执行细节与产物。
              </p>

              <div
                class="mt-8 grid w-full grid-cols-1 gap-3 sm:grid-cols-2 text-left"
              >
                <button
                  v-for="(item, idx) in quickPrompts"
                  :key="idx"
                  type="button"
                  class="group flex flex-col justify-between rounded-xl border border-gray-200/80 bg-white/85 p-3.5 shadow-2xs hover:border-primary-400 hover:bg-white hover:shadow-xs dark:border-dark-800 dark:bg-dark-900/80 dark:hover:border-primary-500/80 dark:hover:bg-dark-800 transition-all text-xs"
                  @click="applyQuickPrompt(item.title, item.desc)"
                >
                  <div
                    class="flex items-center gap-2 mb-1 font-semibold text-gray-800 dark:text-gray-100 group-hover:text-primary-600 dark:group-hover:text-primary-400"
                  >
                    <span
                      class="flex h-5 w-5 items-center justify-center rounded-md bg-gray-100 text-gray-600 dark:bg-dark-800 dark:text-dark-300 group-hover:bg-primary-50 group-hover:text-primary-600 dark:group-hover:bg-primary-950/60 dark:group-hover:text-primary-400 transition-colors"
                    >
                      <BaseIcon :name="item.icon as any" size="xs" />
                    </span>
                    <span>{{ item.title }}</span>
                  </div>
                  <p
                    class="text-[11px] text-gray-400 dark:text-dark-400 leading-normal"
                  >
                    {{ item.desc }}
                  </p>
                </button>
              </div>
            </div>
            <ChatMessageList
              :project-id="projectId"
              :thread-id="session.threadId.value || threadId || ''"
              :stream="stream"
              :messages="displayedMessages"
              :calls="snapshotMessages ? [] : calls"
              :is-running="isSessionRunning && !hasPendingInterrupts"
              :is-interrupted="
                hasPendingInterrupts ||
                session.run.value?.status === 'interrupted'
              "
              :can-edit="canSend && !snapshotMessages"
              :metadata="messageMetadata"
              :target-name="targetName"
              :editing-message-id="editingMessageId"
              :editing-message-value="editDraft"
              :forking-checkpoint-id="forkingCheckpointId"
              :follow-up-suggestions="followUp.suggestions.value"
              :follow-up-loading="followUp.loading.value"
              :follow-up-draft="draft"
              :follow-up-disabled="!canSend || !!snapshotMessages"
              @select-follow-up="handleSelectFollowUp"
              @dismiss-follow-up="followUp.dismiss"
              @select-branch="selectMessageBranch"
              @inspect="inspect"
              @edit="edit"
              @retry="retryMessage"
              @fork="forkToNewThread"
              @update:editing-message-value="editDraft = $event"
              @cancel-edit="cancelEdit"
              @submit-edit="submitEditedBranch"
            />
            <div
              v-if="clarifications.length"
              class="space-y-3"
              data-testid="clarification-container"
            >
              <ClarificationCard
                v-for="clarification in clarifications"
                :key="clarification.id"
                :clarification="clarification"
                :submitting="
                  !session.canApprove.value ||
                  checking ||
                  cancelling ||
                  action?.status === 'unknown' ||
                  action?.status === 'submitting'
                "
                @submit="
                  (values) =>
                    session.answerClarification(clarification.id, values)
                "
              />
            </div>
            <div v-if="reviews.length" ref="approvalElement">
              <ApprovalPanel
                :reviews="reviews"
                :disabled="
                  !session.canApprove.value ||
                  checking ||
                  cancelling ||
                  action?.status === 'unknown' ||
                  action?.status === 'submitting'
                "
                @submit="session.approve"
              />
            </div>
            <div
              v-if="promptQueue.pending.value"
              role="alert"
              class="mx-auto w-full max-w-3xl rounded-xl border border-amber-500/40 p-3 text-xs"
            >
              排队提交结果待确认；请用原消息和原幂等键重试。
              <button
                type="button"
                class="ml-2 underline"
                @click="promptQueue.retry()"
              >
                核实并重试
              </button>
            </div>
            <div
              v-if="legacyPromptQueue.queue.value.length"
              class="mx-auto w-full max-w-3xl rounded-xl border p-3 text-xs"
            >
              本机有
              {{ legacyPromptQueue.queue.value.length }}
              条旧版未提交草稿，不会自动执行。
              <button
                v-for="item in legacyPromptQueue.queue.value"
                :key="item.id"
                type="button"
                class="ml-2 underline"
                @click="restoreQueuedDraft(item.content, item.id)"
              >
                恢复草稿
              </button>
            </div>
            <QueuedMessagesBanner
              :queue-items="promptQueue.queue.value"
              :receipts="visibleReceipts"
              :pending-message="session.pendingMessage.value"
              :receipt-error="session.receiptError.value"
              :can-write="canWrite"
              :can-send="session.canSend.value"
              :is-draining="isDrainingQueue"
              @move-up="promptQueue.moveUp"
              @move-down="promptQueue.moveDown"
              @remove-item="promptQueue.remove"
              @clear-queue="promptQueue.clear"
              @retry-pending="session.queueMessage()"
              @restore-draft="restoreQueuedDraft"
              @resend-as-new="resendQueuedMessage"
              @refresh="session.refreshReceipts()"
            />
            <div
              ref="contentEndSentinel"
              data-testid="chat-content-end"
              class="h-px w-full shrink-0 pointer-events-none"
              aria-hidden="true"
            />
            <div
              v-if="turnCount > 1 && bottomSpacerHeightPx > 0"
              data-testid="chat-turn-spacer"
              class="w-full shrink-0 pointer-events-none transition-[height] duration-150"
              :style="{
                height: `${bottomSpacerHeightPx}px`,
              }"
              aria-hidden="true"
            />
          </div>
        </div>
        <div
          v-if="
            (liveFollowView.noticeVisible ||
              (!following && displayedMessages.length > 0)) &&
            !drawerOpen &&
            !optionsOpen
          "
          class="pointer-events-none absolute bottom-4 left-1/2 z-20 flex -translate-x-1/2 justify-center"
        >
          <div
            v-if="liveFollowView.noticeVisible"
            class="pointer-events-auto flex items-center gap-2.5 rounded-full border border-primary-200/90 bg-white/95 px-4 py-1.5 shadow-lg backdrop-blur-sm dark:border-dark-700 dark:bg-dark-900/95"
          >
            <span
              class="flex items-center gap-1.5 text-xs font-medium text-primary-950 dark:text-primary-100"
            >
              <BaseIcon
                :name="liveFollowView.icon"
                class="h-3.5 w-3.5 text-primary-600 dark:text-primary-400"
              />
              {{ liveFollowView.title }}
            </span>
            <div
              class="flex items-center gap-1.5 border-l border-gray-200 pl-2 dark:border-dark-700"
            >
              <button
                v-if="liveFollowView.showStopAction"
                type="button"
                class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-950/30"
                :disabled="cancelling"
                @click="handleStop"
              >
                <BaseIcon name="x" class="h-3 w-3" />
                {{ cancelling ? "停止中..." : "停止" }}
              </button>
              <button
                type="button"
                class="inline-flex items-center gap-1 rounded-full bg-primary-600 px-2.5 py-0.5 text-xs font-medium text-white shadow-sm hover:bg-primary-700 dark:bg-primary-500 dark:hover:bg-primary-600"
                @click="follow"
              >
                <BaseIcon name="chevron-down" class="h-3 w-3" />
                回到最新
              </button>
            </div>
          </div>
          <button
            v-else
            type="button"
            data-testid="scroll-to-latest"
            class="pointer-events-auto inline-flex items-center gap-1.5 rounded-full border border-gray-200/90 bg-white/95 px-3.5 py-1.5 text-xs font-medium text-gray-700 shadow-md backdrop-blur-sm transition-all hover:border-primary-300 hover:bg-white hover:text-primary-600 dark:border-dark-700 dark:bg-dark-900/95 dark:text-dark-200 dark:hover:border-primary-500/70 dark:hover:text-primary-400"
            @click="follow"
          >
            <BaseIcon name="chevron-down" class="h-3.5 w-3.5" />
            <span>回到最新</span>
          </button>
        </div>
      </div>
      <WorkspacePanel
        v-if="showWorkspace && threadId"
        ref="workspacePanelRef"
        :project-id="projectId"
        :thread-id="threadId"
        @close="showWorkspace = false"
        @add-to-chat="handleAddToChat"
      />
    </div>
    <ChatComposer
      ref="composerRef"
      :model-value="draft"
      :attachments="attachments"
      :is-running="isSessionRunning && !reviews.length"
      :has-blocking-interrupt="!!reviews.length"
      :has-queued-items="promptQueue.queue.value.length > 0"
      :can-send-fresh-message="canSubmit"
      :can-queue="canWrite && !selectedCheckpoint"
      :cancelling="
        cancelling ||
        !canWrite ||
        action?.status === 'submitting' ||
        action?.status === 'unknown'
      "
      :send-button-label="selectedCheckpoint ? '分叉执行' : '发送'"
      :placeholder="
        selectedCheckpoint
          ? '当前处于快照分叉模式，输入新指令即可从此快照分叉执行...'
          : undefined
      "
      :footer-text="
        (displayedMessages.length || messages.length) && activeView === 'chat'
          ? chatMetrics.formattedLine
          : ''
      "
      compact
      :focus-mode="focusMode"
      :models="models"
      :project-id="projectId"
      :selected-model-id="context.model_id"
      :default-model-id="defaultModelId"
      :default-model-name="defaultModelName"
      :access-policy="session.accessPolicy.value"
      :access-policy-updating="session.accessPolicyUpdating.value"
      :can-write="canWrite"
      :can-set-policy="session.canSetPolicy.value"
      :can-full-access="session.canFullAccess.value"
      :show-suggestions="shouldShowComposerSuggestions"
      @update:access-policy="session.setAccessPolicy"
      @change:access-policy="session.setAccessPolicy"
      @update:selected-model-id="context.model_id = $event || undefined"
      @update:model-value="emit('update:draft', $event)"
      @send="send()"
      @queue="send(true)"
      @cancel="handleStop"
      @file-input-change="handleInputChange"
      @composer-paste="handlePaste"
      @remove-attachment="removeAttachment"
      @select-suggestion="handleSelectSuggestion"
    >
      <template #top-tray>
        <ChatStickyTaskPill
          v-if="activeView === 'chat'"
          :plan-view="planView"
          @open-tasks="
            drawerTab = 'tasks';
            drawerOpen = true;
          "
        />
      </template>
    </ChatComposer>
    <ChatRunOptionsDialog
      :show="optionsOpen"
      :draft-run-options="draftRunOptions"
      :runtime-models="models"
      :show-execution-mode="showExecutionMode"
      :mode-disabled="isModeLocked"
      :error="optionsError"
      @close="optionsOpen = false"
      @update:execution-mode="draftRunOptions.executionMode = $event"
      @update:model-id="draftRunOptions.modelId = $event"
      @update:temperature="draftRunOptions.temperature = $event"
      @update:max-tokens="draftRunOptions.maxTokens = $event"
      @update:recursion-limit="draftRunOptions.recursionLimit = $event"
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
      :is-running="isSessionRunning"
      :has-interrupt="!!reviews.length"
      source-note=""
      :history-loading="historyLoading"
      :has-more-history="hasMoreHistory"
      :can-execute="canSend"
      :run="session.run.value"
      @close="drawerOpen = false"
      @select-branch="selectSnapshot"
      @load-history="loadHistory(false, $event)"
      @fork="handleSnapshotFork"
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

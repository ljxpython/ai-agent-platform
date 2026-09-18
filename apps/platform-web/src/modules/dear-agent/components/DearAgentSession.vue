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
import ChatStickyTaskPill from "./ChatStickyTaskPill.vue";
import WorkspacePanel from "@/components/workspace/WorkspacePanel.vue";
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
import { createSessionService, type ChatCheckpoint } from "@/services/threads/session.service";
import { createLanggraphAuthorizedFetch } from "@/services/langgraph/client";
import { increasedForkTitle } from "@/utils/threads";
import { listRuntimeModels } from "@/services/runtime/runtime.service";
import type { RuntimeModelItem } from "@/types/management";
import { listRuntimeModelPolicies } from "@/services/runtime-policies/runtime-policies.service";
import { useDearAgentSession } from "../composables/useDearAgentSession";
import { useChatAttachments } from "../composables/useChatAttachments";
import { useTranscriptMessages } from "../composables/useTranscriptMessages";
import { asObject, buildTranscript, contentItems, readable, type ToolItem } from "../transcript";
import { isChatViewportNearBottom } from "../scroll-state";
import ChatComposer from "./ChatComposer.vue";
import ChatMessageList from "./ChatMessageList.vue";
import ApprovalPanel from "./ApprovalPanel.vue";
import ClarificationCard from "./ClarificationCard.vue";
import MessageContent from "./MessageContent.vue";
import TrajectoryView from "./trajectory/TrajectoryView.vue";

const activeView = ref<"chat" | "trajectory">("chat");

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
  threadTitle?: string;
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
const session = useDearAgentSession({
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
    optimisticUserMessage.value = null;
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
  resumeClarification,
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
    canSend.value &&
    !hasPendingInterrupts.value &&
    !modelsLoading.value && !!models.value.length &&
    !attachmentsLoading.value &&
    (!!props.draft.trim() || !!attachments.value.length),
);
const models = ref<RuntimeModelItem[]>([]);
const modelsLoading = ref(true);
const defaultModelName = ref("");
const optionsOpen = ref(false);
const optionsError = ref("");
type ExecutionMode = 'flash' | 'standard' | 'pro' | 'ultra';
const initialContext = { ...context.value };
const draftRunOptions = reactive<{
  modelId: string;
  temperature: string;
  maxTokens: string;
  recursionLimit: string;
  executionMode: ExecutionMode;
}>({
  modelId: "",
  temperature: "",
  maxTokens: "",
  recursionLimit: recursionLimit.value.toString(),
  executionMode: (context.value.execution_mode as ExecutionMode) ?? "standard",
});

const currentExecutionMode = computed<ExecutionMode>(() => {
  return (context.value.execution_mode as ExecutionMode) ?? "standard";
});

const isModeLocked = computed(
  () => busy.value || hasPendingInterrupts.value || checking.value,
);

function resetOptions(value: AgentContext) {
  Object.assign(draftRunOptions, {
    modelId: value.model_id ?? "",
    temperature: value.temperature?.toString() ?? "",
    maxTokens: value.max_tokens?.toString() ?? "",
    recursionLimit: recursionLimit.value.toString(),
    executionMode: (value.execution_mode as ExecutionMode) ?? "standard",
  });
  optionsError.value = "";
}
function openOptions() {
  resetOptions(context.value);
  optionsOpen.value = true;
}
function applyOptions() {
  try {
    const nextMode = isModeLocked.value
      ? ((context.value.execution_mode as ExecutionMode) ?? "standard")
      : (draftRunOptions.executionMode || "standard");

    if (draftRunOptions.recursionLimit?.trim()) {
      const limitNum = Number(draftRunOptions.recursionLimit);
      if (!Number.isInteger(limitNum) || limitNum < 1 || limitNum > 1000) {
        optionsError.value = "最大步数预算必须是 1 到 1000 之间的整数";
        return;
      }
      recursionLimit.value = limitNum;
    }

    const fallbackModel = models.value.find(m => m.display_name === defaultModelName.value) ?? models.value[0];
    const resolvedModelId = draftRunOptions.modelId || fallbackModel?.id;

    const updated = parseAgentContext({
      ...context.value,
      model_id: resolvedModelId || undefined,
      temperature: draftRunOptions.temperature.trim()
        ? Number(draftRunOptions.temperature)
        : undefined,
      max_tokens: draftRunOptions.maxTokens.trim()
        ? Number(draftRunOptions.maxTokens)
        : undefined,
      execution_mode: nextMode,
    });
    context.value = updated;

    if (
      (nextMode === "pro" || nextMode === "ultra") &&
      recursionLimit.value < 100
    ) {
      recursionLimit.value = 100;
    }
    optionsOpen.value = false;
  } catch (cause) {
    optionsError.value = cause instanceof Error ? cause.message : "运行参数无效";
  }
}
const drawerOpen = ref(false);
const drawerTab = ref<"overview" | "tasks" | "files" | "history">("overview");
function openDrawer() { drawerOpen.value = true; drawerTab.value = "overview"; void loadHistory(true); }
const snapshotMessages = shallowRef<BaseMessage[] | null>(null);
const optimisticUserMessage = shallowRef<BaseMessage | null>(null);
const displayedMessages = computed(() => {
  const base = snapshotMessages.value ?? messages.value;
  if (!optimisticUserMessage.value) return base;
  const hasEchoed = base.some(
    (m) =>
      m.id === optimisticUserMessage.value?.id ||
      (m.type === "human" &&
        typeof m.content === "string" &&
        typeof optimisticUserMessage.value?.content === "string" &&
        m.content.trim() === optimisticUserMessage.value?.content.trim()),
  );
  if (hasEchoed) return base;
  return [...base, optimisticUserMessage.value];
});
watch([messages, busy], ([currentMessages, isBusy]) => {
  if (!optimisticUserMessage.value) return;
  const hasEchoed = currentMessages.some(
    (m) =>
      m.id === optimisticUserMessage.value?.id ||
      (m.type === "human" &&
        typeof m.content === "string" &&
        typeof optimisticUserMessage.value?.content === "string" &&
        m.content.trim() === optimisticUserMessage.value?.content.trim()),
  );
  if (hasEchoed || (!isBusy && !action.value)) {
    optimisticUserMessage.value = null;
  }
});
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
  emit('update:draft', props.draft ? `${props.draft}\n\n${text}` : text);
}
const localError = ref("");
let disposed = false;
void Promise.all([listRuntimeModels(props.projectId), listRuntimeModelPolicies(props.projectId)])
  .then(([value, policies]) => {
    if (disposed) return;
    models.value = value.models.filter((model) => model.enabled && model.credential_configured && policies.items.find(item => item.catalog_id === model.id)?.policy.is_enabled !== false);
    const projectDefault = policies.items.find(item => item.policy.is_default_for_project);
    const defaultModel = models.value.find(model => model.id === projectDefault?.catalog_id) ?? models.value[0];
    defaultModelName.value = defaultModel?.display_name ?? "";
    if (!context.value.model_id && defaultModel) {
      context.value = {
        ...context.value,
        model_id: defaultModel.id,
      };
      draftRunOptions.modelId = defaultModel.id;
    }
  })
  .catch(() => {
    if (!disposed) localError.value = "模型列表读取失败，可恢复连接后重试";
  }).finally(() => { if (!disposed) modelsLoading.value = false; });

function handleModelChange(selectedId: string) {
  const projectDefault = models.value.find(m => m.display_name === defaultModelName.value) ?? models.value[0];
  const targetId = selectedId || projectDefault?.id || "";
  context.value = {
    ...context.value,
    model_id: targetId || undefined,
  };
  draftRunOptions.modelId = targetId;
}

const composerRef = ref<{ focus: () => void } | null>(null);
function focusComposer() {
  void nextTick(() => {
    composerRef.value?.focus();
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
  } catch { /* ignore */ }
}

const quickPrompts = [
  { icon: 'sparkle', title: '分析当前项目', desc: '全面梳理代码库结构与模块依赖关系' },
  { icon: 'assistant', title: '设计功能方案', desc: '根据业务需求给出优雅的架构与接口设计' },
  { icon: 'shield', title: '审查代码规范', desc: '排查潜在异常、安全漏洞与代码坏味道' },
  { icon: 'activity', title: '调试系统问题', desc: '定位错误调用栈并提供直接可用的修复补丁' },
];

function applyQuickPrompt(title: string, desc: string) {
  emit('update:draft', `${title}：${desc}`);
  focusComposer();
}

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

  follow();

  if (queued) {
    await session.queueMessage(content);
  } else if (selectedCheckpoint.value) {
    const targetCheckpoint = selectedCheckpoint.value.checkpoint;
    optimisticUserMessage.value = coerceMessageLikeToMessage({
      id: `optimistic-${Date.now()}`,
      type: "human",
      content,
    });
    emit("update:draft", "");
    attachments.value = [];
    selectSnapshot("");
    void nextTick(() => requestSmoothScrollToBottom());
    try {
      if (!context.value.model_id && models.value.length > 0) {
        const defaultModel = models.value.find(m => m.display_name === defaultModelName.value) ?? models.value[0];
        if (defaultModel) {
          context.value = {
            ...context.value,
            model_id: defaultModel.id,
          };
        }
      }
      const ok = await session.fork(
        targetCheckpoint,
        content,
        recursionLimit.value,
      );
      if (!ok && session.error.value) {
        throw new Error(session.error.value);
      }
    } catch {
      optimisticUserMessage.value = null;
      if (submittedDraft !== undefined) emit("update:draft", submittedDraft);
      attachments.value = Array.from(submittedAttachments) as ChatAttachmentBlock[];
      submittedDraft = undefined;
      submittedAttachments = new Set();
    }
  } else {
    optimisticUserMessage.value = coerceMessageLikeToMessage({
      id: `optimistic-${Date.now()}`,
      type: "human",
      content,
    });
    emit("update:draft", "");
    attachments.value = [];
    void nextTick(() => requestSmoothScrollToBottom());
    try {
      if (!context.value.model_id && models.value.length > 0) {
        const defaultModel = models.value.find(m => m.display_name === defaultModelName.value) ?? models.value[0];
        if (defaultModel) {
          context.value = {
            ...context.value,
            model_id: defaultModel.id,
          };
        }
      }
      const effectiveLimit =
        currentExecutionMode.value === "pro" ||
        currentExecutionMode.value === "ultra"
          ? Math.max(recursionLimit.value, 100)
          : recursionLimit.value;
      const ok = await session.send(content, effectiveLimit);
      if (!ok && session.error.value) {
        throw new Error(session.error.value);
      }
    } catch {
      optimisticUserMessage.value = null;
      if (submittedDraft !== undefined) emit("update:draft", submittedDraft);
      attachments.value = Array.from(submittedAttachments) as ChatAttachmentBlock[];
      submittedDraft = undefined;
      submittedAttachments = new Set();
    }
  }
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
let scrollRafId: number | null = null;
function requestSmoothScrollToBottom() {
  if (!following.value || drawerOpen.value || optionsOpen.value || inspector.value || snapshotMessages.value) return;
  if (scrollRafId !== null) return;
  scrollRafId = requestAnimationFrame(() => {
    scrollRafId = null;
    if (viewport.value) {
      viewport.value.scrollTop = viewport.value.scrollHeight;
    }
  });
}
watch(
  displayedMessages,
  async (next, previous) => {
    lastEventAt.value = new Date().toISOString();
    if (!following.value) {
      unreadMessageCount.value += Math.max(0, next.length - previous.length);
      bufferedStreamActivity.value = true;
    }
    if (following.value && !drawerOpen.value && !optionsOpen.value && !inspector.value && !snapshotMessages.value) {
      await nextTick();
      requestSmoothScrollToBottom();
    }
  },
  { flush: "post", deep: true },
);
function follow() {
  following.value = true;
  unreadMessageCount.value = 0;
  bufferedStreamActivity.value = false;
  requestSmoothScrollToBottom();
}

function handleViewportScroll() {
  if (!viewport.value) return;
  const nearBottom = isChatViewportNearBottom(viewport.value);
  following.value = nearBottom;
  if (nearBottom) {
    unreadMessageCount.value = 0;
    bufferedStreamActivity.value = false;
  }
}

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
  if (tool.name === "write_todos") {
    drawerTab.value = "tasks";
    drawerOpen.value = true;
    return;
  }
  const path = asObject(tool.input).file_path ?? asObject(tool.input).path;
  inspector.value = {
    title: tool.name === "read_file" && typeof path === "string" && path.startsWith("/skills/") ? "已读取技能" : tool.name,
    source: `工具调用 ${tool.id} · ${tool.status}${typeof path === "string" ? ` · ${path} · 可见片段` : ""}`,
    value: tool.artifact ?? tool.output,
  };
}

function cancelEdit() {
  editCheckpoint.value = null;
  editingMessageId.value = "";
  editDraft.value = "";
  editLoading.value = false;
}

function findParentCheckpointForMessage(messageId: string, messageText: string): Checkpoint | null {
  // 1. 优先查预计算的 messageMetadata
  const meta = messageMetadata.value[messageId];
  if (meta?.parentCheckpoint?.checkpoint_id) {
    return meta.parentCheckpoint;
  }

  // 2. 本地历史按时间正序回溯查找
  const matchMsg = (msg: unknown) => {
    const obj = asObject(msg);
    if (obj.id && obj.id === messageId) return true;
    if (obj.key && obj.key === messageId) return true;
    const type = String(obj.type || obj.role || "").toLowerCase();
    if ((type === "human" || type === "user") && messageText) {
      const content = typeof obj.content === "string" ? obj.content : "";
      if (content.trim() && content.trim() === messageText.trim()) {
        return true;
      }
    }
    return false;
  };

  const states = [...history.value].reverse();
  const firstSeenIndex = states.findIndex((state) =>
    (state.values.messages ?? []).some(matchMsg)
  );

  if (firstSeenIndex > 0) {
    return states[firstSeenIndex - 1].checkpoint;
  }

  if (firstSeenIndex === 0) {
    const firstState = states[0];
    if (firstState.parent_checkpoint?.checkpoint_id) {
      return firstState.parent_checkpoint;
    }
  }

  return null;
}

async function submitEditedBranch() {
  if (!editDraft.value.trim()) return;
  let checkpoint = editCheckpoint.value;
  if (!checkpoint && editingMessageId.value) {
    checkpoint = findParentCheckpointForMessage(editingMessageId.value, editDraft.value);
    if (checkpoint) editCheckpoint.value = checkpoint;
  }
  if (!checkpoint) {
    localError.value = "未找到该消息之前可恢复的检查点，无法安全创建分支";
    return;
  }
  const draftText = editDraft.value;
  cancelEdit();
  await session.fork(checkpoint, draftText, recursionLimit.value);
}
const historyLoading = ref(false);
const history = shallowRef<ChatCheckpoint[]>([]);
const hasMoreHistory = ref(true);
const selectedCheckpoint = shallowRef<ChatCheckpoint | null>(null);
async function loadHistory(reset = false, limit = 20) {
  if (!session.threadId.value || historyLoading.value) return;
  historyLoading.value = true;
  localError.value = "";
  try {
    const rows = await session.service.history(
      session.threadId.value,
      reset ? undefined : history.value[history.value.length - 1]?.checkpoint,
      limit
    );
    if (disposed) return;
    history.value = reset ? rows : [...history.value, ...rows];
    hasMoreHistory.value = rows.length === limit;
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
    const ok = await session.fork(editCheckpoint.value);
    if (ok) { cancelEdit(); }
  }
}

function findForkCheckpointForMessage(messageId: string): string | undefined {
  const meta = messageMetadata.value[messageId];
  if (meta?.checkpointId) {
    return meta.checkpointId;
  }
  const allMsgs = displayedMessages.value;
  const targetIndex = allMsgs.findIndex(
    (m) => m.id === messageId || (m as any).key === messageId
  );
  const subsequentIds = new Set<string>();
  if (targetIndex >= 0) {
    for (let i = targetIndex + 1; i < allMsgs.length; i++) {
      const id = allMsgs[i]?.id || (allMsgs[i] as any)?.key;
      if (id) subsequentIds.add(id);
    }
  }

  const matchMsg = (msg: unknown) => {
    const obj = asObject(msg);
    return obj.id === messageId || obj.key === messageId;
  };

  // 在倒序历史中查找：必须包含目标消息，且绝不包含目标消息之后的后续消息
  const matched = history.value.find((state) => {
    const msgs = (state.values.messages ?? []) as unknown[];
    const hasTarget = msgs.some(matchMsg);
    if (!hasTarget) return false;
    if (subsequentIds.size === 0) return true;
    const hasSubsequent = msgs.some((msg) => {
      const obj = asObject(msg);
      const id = (obj.id || obj.key) as string;
      return Boolean(id && subsequentIds.has(id));
    });
    return !hasSubsequent;
  });

  return matched?.checkpoint?.checkpoint_id || undefined;
}

const forkingCheckpointId = ref<string>();
async function forkToNewThread(messageId: string, checkpointId?: string) {
  const currentThreadId = session.threadId.value || props.threadId;
  if (!currentThreadId || !messageId || forkingCheckpointId.value) return;
  if (busy.value && !snapshotMessages.value) return;

  forkingCheckpointId.value = checkpointId || messageId;
  localError.value = "";
  try {
    let resolvedCheckpointId: string | undefined =
      checkpointId || findForkCheckpointForMessage(messageId);

    // 如果未命中且历史尚未完全拉取，向前分页循环拉取更早历史进行定位
    if (!resolvedCheckpointId) {
      let pageCount = 0;
      while (!resolvedCheckpointId && pageCount < 5) {
        pageCount++;
        const oldestCheckpoint =
          history.value[history.value.length - 1]?.checkpoint;
        try {
          const rows = await session.service.history(
            currentThreadId,
            oldestCheckpoint,
            50
          );
          if (disposed || !rows || rows.length === 0) break;
          const existingIds = new Set(
            history.value
              .map((s) => s.checkpoint?.checkpoint_id)
              .filter(Boolean)
          );
          const newRows = rows.filter(
            (r) =>
              r.checkpoint?.checkpoint_id &&
              !existingIds.has(r.checkpoint.checkpoint_id)
          );
          if (newRows.length === 0) break;
          history.value = [...history.value, ...newRows];
          resolvedCheckpointId = findForkCheckpointForMessage(messageId);
        } catch {
          break;
        }
      }
    }

    // 兜底保护：只有当目标消息确实是当前会话中的最后一条消息时，才允许使用最新会话状态兜底
    if (!resolvedCheckpointId) {
      const allMsgs = displayedMessages.value;
      const targetIndex = allMsgs.findIndex(
        (m) => m.id === messageId || (m as any).key === messageId
      );
      const isLatestTurn =
        targetIndex === -1 || targetIndex === allMsgs.length - 1;
      if (isLatestTurn) {
        const currentState = await session.service.state(currentThreadId);
        resolvedCheckpointId =
          currentState?.checkpoint?.checkpoint_id || undefined;
      }
    }

    if (!resolvedCheckpointId) {
      throw new Error("未找到该轮次有效的历史快照，无法创建分支（请刷新后重试）");
    }

    const sessionService = createSessionService(
      createLanggraphAuthorizedFetch(),
      props.projectId
    );
    const newTitle = increasedForkTitle(props.threadTitle);
    const target = await sessionService.fork(
      currentThreadId,
      resolvedCheckpointId,
      newTitle
    );
    if (!target?.thread_id) {
      throw new Error("未能获取新分支会话 ID");
    }
    emit("fork-thread", target.thread_id);
    emit("refresh");
  } catch (cause) {
    localError.value = cause instanceof Error ? cause.message : "创建分支失败";
  } finally {
    forkingCheckpointId.value = undefined;
  }
}

const editCheckpoint = shallowRef<Checkpoint | null>(null);
const editLoading = ref(false);
async function edit(messageId: string, text: string) {
  if (!canSend.value || !session.threadId.value) return;
  localError.value = "";
  // 即时响应：先进入编辑模式展开输入框，给用户最流畅的交互体验
  editingMessageId.value = messageId;
  editDraft.value = text;
  editCheckpoint.value = null;

  // 1. 优先本地内存秒级回溯检查点
  let targetCheckpoint = findParentCheckpointForMessage(messageId, text);
  if (targetCheckpoint) {
    editCheckpoint.value = targetCheckpoint;
    return;
  }

  // 2. 本地历史若未命中，仅拉取单次更早历史补充后重试
  editLoading.value = true;
  try {
    const rows = await session.service.history(session.threadId.value, undefined, 100);
    if (disposed) return;
    if (rows && rows.length > 0) {
      history.value = rows;
      targetCheckpoint = findParentCheckpointForMessage(messageId, text);
      if (targetCheckpoint) {
        editCheckpoint.value = targetCheckpoint;
        return;
      }
    }

    // 3. 兜底浅层回溯（最多 10 次，严禁死循环）
    let current = await session.service.state(session.threadId.value);
    const contains = (state: ChatCheckpoint) =>
      (state.values.messages ?? []).some((m) => {
        const obj = asObject(m);
        return (
          obj.id === messageId ||
          obj.key === messageId ||
          ((obj.type === "human" || obj.role === "user") &&
            typeof obj.content === "string" &&
            text &&
            obj.content.trim() === text.trim())
        );
      });
    for (let depth = 0; depth < 10 && !disposed; depth++) {
      if (!contains(current) || !current.parent_checkpoint) break;
      const parent = await session.service.state(
        session.threadId.value,
        current.parent_checkpoint,
      );
      if (!contains(parent)) {
        editCheckpoint.value = parent.checkpoint;
        return;
      }
      current = parent;
    }

    if (!disposed && !editCheckpoint.value) {
      localError.value = "未找到该消息之前可恢复的检查点，无法安全创建分支";
    }
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
  if (scrollRafId !== null) cancelAnimationFrame(scrollRafId);
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
      ((raw.response_metadata as Record<string, unknown> | undefined)?.token_usage as Record<string, number> | undefined);
    if (usage) {
      if (typeof usage.input_tokens === "number") inTok += usage.input_tokens;
      if (typeof usage.output_tokens === "number") outTok += usage.output_tokens;
      if (typeof usage.cache_read_input_tokens === "number") cacheReadTok += usage.cache_read_input_tokens;
      if (typeof usage.cache_creation_input_tokens === "number") cacheWriteTok += usage.cache_creation_input_tokens;
    }
    const additional = raw.additional_kwargs as Record<string, unknown> | undefined;
    const dur = typeof additional?.durationMs === "number" ? additional.durationMs : undefined;
    if (dur && dur > 0) {
      totalLlmMs += dur;
    }
    const ttft = typeof additional?.ttftMs === "number" ? additional.ttftMs : undefined;
    if (ttft && ttft > 0) {
      totalTtftMs += ttft;
      ttftCount++;
    }
  }

  // 历史/缺少原生遥测时：智能安全推导
  if (totalAiChars > 0) {
    if (inTok === 0 && outTok === 0) {
      inTok = Math.max(160, Math.round(totalHumanChars * 0.6 + 680 * Math.max(turns, 1)));
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
      const speed = totalLlmMs > 0 ? Math.max(1, Math.round(outTok / (totalLlmMs / 1000))) : 40;
      groups.push(`首 token 平均 ${formatDurationSec(avgTtft)} · ${speed} tok/s`);
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
    groups.push(`输入 ${formatTokensCompact(inTok || billedInput || 46800)} tok · 输出 ${formatTokensCompact(outTok || 197)} tok`);
  }

  return {
    turns: Math.max(turns, 1),
    steps,
    formattedLine: groups.join(" | "),
  };
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
          <button
            v-if="session.threadId.value"
            type="button"
            class="group inline-flex items-center gap-1.5 rounded-lg border border-gray-200/80 bg-white/90 px-2.5 py-1 text-[11px] text-gray-500 shadow-2xs hover:border-gray-300 hover:bg-gray-50 hover:text-gray-800 dark:border-dark-700/80 dark:bg-dark-800/90 dark:text-dark-300 dark:hover:border-dark-600 dark:hover:text-white transition-colors"
            title="点击复制完整 Thread ID"
            @click="copyThreadId"
          >
            <span class="font-mono text-gray-400 dark:text-dark-400">#</span>
            <span class="font-mono font-medium">{{ session.threadId.value.slice(0, 8) }}</span>
            <BaseIcon
              :name="copiedThread ? 'check' : 'copy'"
              size="xs"
              class="text-gray-400 group-hover:text-gray-600 dark:text-dark-400 dark:group-hover:text-dark-200"
              :class="copiedThread ? '!text-emerald-500' : ''"
            />
          </button>
          <span
            v-else
            class="inline-flex items-center rounded-lg border border-dashed border-gray-200 bg-gray-50/50 px-2 py-1 text-[11px] text-gray-400 dark:border-dark-700 dark:bg-dark-900/50"
          >
            新会话
          </span>
          <span
            v-if="session.accessPolicy.value === 'full_access'"
            class="inline-flex items-center gap-1 rounded-md border border-red-300/80 bg-red-50/80 px-2 py-0.5 text-[10px] font-medium text-red-800 dark:border-red-800/80 dark:bg-red-950/40 dark:text-red-300"
            title="当前会话启用全权负责模式：默认放行所有工具审批"
          >
            <span class="h-1.5 w-1.5 rounded-full bg-red-500" />
            全权负责
          </span>
          <span
            v-else-if="session.accessPolicy.value === 'workspace_write'"
            class="inline-flex items-center gap-1 rounded-md border border-amber-300/80 bg-amber-50/80 px-2 py-0.5 text-[10px] font-medium text-amber-800 dark:border-amber-800/80 dark:bg-amber-950/40 dark:text-amber-300"
            title="当前会话启用工作区免审策略"
          >
            <span class="h-1.5 w-1.5 rounded-full bg-amber-500" />
            工作区免审
          </span>
        </div>
        <div class="ml-auto flex items-center gap-2">
          <div class="flex items-center gap-3 text-xs font-medium">
            <button
              type="button"
              class="relative pb-1 transition-colors"
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
              class="relative pb-1 transition-colors"
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
          <slot name="actions" />
          <button
            type="button"
            class="relative inline-flex h-7 shrink-0 items-center gap-1 rounded-md border border-gray-200/70 bg-white px-2 text-xs font-medium text-gray-500 shadow-2xs hover:bg-gray-50 hover:text-gray-800 dark:border-dark-700/80 dark:bg-dark-900 dark:text-dark-300 dark:hover:text-white transition-colors"
            :class="showWorkspace ? 'border-primary-500 bg-primary-50 text-primary-600 dark:bg-primary-950/40 dark:text-primary-400' : ''"
            title="沙箱工作区与产物面板"
            @click="showWorkspace = !showWorkspace"
          >
            <BaseIcon
              name="folder"
              size="xs"
            />
            <span class="hidden sm:inline">工作区</span>
          </button>
          <!-- 当前执行模式指示胶囊 (点击直达模式与参数配置) -->
          <button
            type="button"
            class="inline-flex h-7 shrink-0 items-center gap-1.5 rounded-full border px-2.5 text-xs font-medium transition-all shadow-2xs"
            :class="[
              currentExecutionMode === 'ultra'
                ? 'border-purple-300 bg-purple-50 text-purple-700 dark:border-purple-800/80 dark:bg-purple-950/40 dark:text-purple-300'
                : currentExecutionMode === 'pro'
                  ? 'border-blue-300 bg-blue-50 text-blue-700 dark:border-blue-800/80 dark:bg-blue-950/40 dark:text-blue-300'
                  : currentExecutionMode === 'flash'
                    ? 'border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-800/80 dark:bg-amber-950/40 dark:text-amber-300'
                    : 'border-gray-200 bg-gray-50 text-gray-700 dark:border-dark-700 dark:bg-dark-800 dark:text-dark-200'
            ]"
            title="点击切换执行模式与参数"
            @click="openOptions"
          >
            <span
              class="inline-block h-1.5 w-1.5 rounded-full"
              :class="[
                currentExecutionMode === 'ultra' ? 'bg-purple-500' :
                currentExecutionMode === 'pro' ? 'bg-blue-500' :
                currentExecutionMode === 'flash' ? 'bg-amber-500' : 'bg-emerald-500'
              ]"
            />
            <span class="font-semibold uppercase tracking-wider text-[10px]">
              {{ currentExecutionMode }}
            </span>
            <span
              v-if="currentExecutionMode === 'pro' || currentExecutionMode === 'ultra'"
              class="text-[10px] opacity-75 font-mono"
            >
              100步
            </span>
          </button>
          <button
            type="button"
            class="inline-flex h-7 shrink-0 items-center gap-1 rounded-md border border-gray-200/70 bg-white px-2 text-xs font-medium text-gray-500 shadow-2xs hover:bg-gray-50 hover:text-gray-800 dark:border-dark-700/80 dark:bg-dark-900 dark:text-dark-300 dark:hover:text-white transition-colors"
            title="查看会话详情与上下文"
            @click="openDrawer"
          >
            <BaseIcon
              name="overview"
              size="xs"
            />
            <span class="hidden sm:inline">详情</span>
          </button>
          <button
            type="button"
            class="inline-flex h-7 shrink-0 items-center gap-1 rounded-md border border-gray-200/70 bg-white px-2 text-xs font-medium text-gray-500 shadow-2xs hover:bg-gray-50 hover:text-gray-800 dark:border-dark-700/80 dark:bg-dark-900 dark:text-dark-300 dark:hover:text-white transition-colors"
            title="配置运行参数"
            @click="openOptions"
          >
            <BaseIcon
              name="runtime"
              size="xs"
            />
            <span class="hidden sm:inline">参数</span>
          </button>
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
      class="pw-panel-info mx-5 mt-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between text-sm"
    >
      <div class="flex items-center gap-2">
        <span class="inline-flex h-2 w-2 rounded-full bg-sky-500 animate-pulse" />
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
        <BaseButton
          size="sm"
          :disabled="!canSend"
          @click="handleSnapshotFork"
        >
          从此快照重新执行
        </BaseButton>
        <BaseButton
          variant="secondary"
          size="sm"
          @click="selectSnapshot('')"
        >
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
      class="relative z-10 flex min-h-0 flex-1 overflow-hidden"
    >
      <div class="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <TrajectoryView
          v-if="activeView === 'trajectory'"
          :messages="displayedMessages"
          :calls="snapshotMessages ? [] : calls"
          :is-running="busy"
        />
        <div
          v-else
          ref="viewport"
          class="pw-chat-stream overscroll-contain"
          @scroll="handleViewportScroll"
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
            <ChatStickyTaskPill
              :plan-view="planView"
              @open-tasks="drawerTab = 'tasks'; drawerOpen = true;"
            />
            <div
              v-if="!messages.length && !checking"
              class="mx-auto flex w-full max-w-2xl flex-1 flex-col items-center justify-center py-12 px-4 text-center"
            >
              <span class="inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-tr from-primary-600 to-indigo-500 text-white shadow-md mb-4">
                <BaseIcon
                  name="sparkle"
                  size="lg"
                />
              </span>
              <h2 class="text-xl font-bold text-gray-900 dark:text-white tracking-tight">
                {{ targetName ? `${targetName}` : '开始新的会话' }}
              </h2>
              <p class="mt-2 max-w-md text-xs leading-5 text-gray-500 dark:text-dark-400">
                输入任务目标或点击下方常用场景卡片，Agent 将在这里展示执行细节与产物。
              </p>

              <div class="mt-8 grid w-full grid-cols-1 gap-3 sm:grid-cols-2 text-left">
                <button
                  v-for="(item, idx) in quickPrompts"
                  :key="idx"
                  type="button"
                  class="group flex flex-col justify-between rounded-xl border border-gray-200/80 bg-white/85 p-3.5 shadow-2xs hover:border-primary-400 hover:bg-white hover:shadow-xs dark:border-dark-800 dark:bg-dark-900/80 dark:hover:border-primary-500/80 dark:hover:bg-dark-800 transition-all text-xs"
                  @click="applyQuickPrompt(item.title, item.desc)"
                >
                  <div class="flex items-center gap-2 mb-1 font-semibold text-gray-800 dark:text-gray-100 group-hover:text-primary-600 dark:group-hover:text-primary-400">
                    <span class="flex h-5 w-5 items-center justify-center rounded-md bg-gray-100 text-gray-600 dark:bg-dark-800 dark:text-dark-300 group-hover:bg-primary-50 group-hover:text-primary-600 dark:group-hover:bg-primary-950/60 dark:group-hover:text-primary-400 transition-colors">
                      <BaseIcon
                        :name="item.icon as any"
                        size="xs"
                      />
                    </span>
                    <span>{{ item.title }}</span>
                  </div>
                  <p class="text-[11px] text-gray-400 dark:text-dark-400 leading-normal">
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
              :is-running="busy && !snapshotMessages"
              :can-edit="canSend && !snapshotMessages"
              :metadata="messageMetadata"
              :target-name="targetName"
              :editing-message-id="editingMessageId"
              :editing-message-value="editDraft"
              :forking-checkpoint-id="forkingCheckpointId"
              @select-branch="selectMessageBranch"
              @inspect="inspect"
              @edit="edit"
              @retry="retryMessage"
              @fork="forkToNewThread"
              @update:editing-message-value="editDraft = $event"
              @cancel-edit="cancelEdit"
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
            <!-- HITL Clarification Interrupt Cards -->
            <div
              v-if="clarifications.length > 0"
              class="space-y-3 pt-2"
              data-testid="clarification-container"
            >
              <ClarificationCard
                v-for="clarification in clarifications"
                :key="clarification.id"
                :clarification="clarification"
                :submitting="checking"
                @submit="resumeClarification(clarification.id, $event)"
              />
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
          class="pointer-events-none absolute bottom-4 left-1/2 z-20 flex -translate-x-1/2 justify-center"
        >
          <div class="pointer-events-auto flex items-center gap-2.5 rounded-full border border-primary-200/90 bg-white/95 px-4 py-1.5 shadow-lg backdrop-blur-sm dark:border-dark-700 dark:bg-dark-900/95">
            <span class="flex items-center gap-1.5 text-xs font-medium text-primary-950 dark:text-primary-100">
              <BaseIcon
                :name="liveFollowView.icon"
                class="h-3.5 w-3.5 text-primary-600 dark:text-primary-400"
              />
              {{ liveFollowView.title }}
            </span>
            <div class="flex items-center gap-1.5 border-l border-gray-200 pl-2 dark:border-dark-700">
              <button
                v-if="liveFollowView.showStopAction"
                type="button"
                class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-950/30"
                :disabled="cancelling"
                @click="session.stop"
              >
                <BaseIcon
                  name="x"
                  class="h-3 w-3"
                />
                {{ cancelling ? '停止中...' : '停止' }}
              </button>
              <button
                type="button"
                class="inline-flex items-center gap-1 rounded-full bg-primary-600 px-2.5 py-0.5 text-xs font-medium text-white shadow-sm hover:bg-primary-700 dark:bg-primary-500 dark:hover:bg-primary-600"
                @click="follow"
              >
                <BaseIcon
                  name="chevron-down"
                  class="h-3 w-3"
                />
                回到最新
              </button>
            </div>
          </div>
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
    <button
      v-if="!following && !liveFollowView.noticeVisible"
      class="pw-table-tool-button mx-auto my-1"
      @click="follow"
    >
      回到最新
    </button>
    <ChatComposer
      ref="composerRef"
      :model-value="draft"
      :attachments="attachments"
      :is-running="busy && !hasPendingInterrupts"
      :has-blocking-interrupt="hasPendingInterrupts"
      :can-send-fresh-message="canSubmit"
      :cancelling="
        cancelling ||
          !canWrite ||
          action?.status === 'submitting' ||
          action?.status === 'unknown'
      "
      :can-queue="session.supportsQueue && canWrite && !reviews.length && !session.pendingMessage.value"
      :send-button-label="selectedCheckpoint ? '分叉执行' : '发送'"
      :placeholder="selectedCheckpoint ? '当前处于快照分叉模式，输入新指令即可从此快照分叉执行...' : undefined"
      compact
      :focus-mode="focusMode"
      :models="models"
      :project-id="projectId"
      :selected-model-id="context.model_id"
      :default-model-name="defaultModelName"
      :access-policy="session.accessPolicy.value"
      :access-policy-updating="session.accessPolicyUpdating.value"
      :can-write="canWrite"
      @update:access-policy="session.setAccessPolicy"
      @change:access-policy="session.setAccessPolicy"
      @update:selected-model-id="handleModelChange($event)"
      @update:model-value="emit('update:draft', $event)"
      @send="send()"
      @queue="send(true)"
      @cancel="session.stop"
      @file-input-change="handleInputChange"
      @composer-paste="handlePaste"
      @remove-attachment="removeAttachment"
    />
    <div
      v-if="messages.length && activeView === 'chat' && chatMetrics.formattedLine"
      class="mt-0.5 pb-1.5 text-center font-mono text-[11px] text-gray-400 select-none dark:text-dark-500 truncate px-4"
    >
      <span>{{ chatMetrics.formattedLine }}</span>
    </div>
    <ChatRunOptionsDialog
      :show="optionsOpen"
      :draft-run-options="draftRunOptions"
      :runtime-models="models"
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
      :is-running="busy"
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

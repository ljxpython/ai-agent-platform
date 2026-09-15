<script setup lang="ts">
import { computed, onScopeDispose, ref, shallowRef, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useWorkspaceProjectContext } from "@/composables/useWorkspaceProjectContext";
import { useAuthorization } from "@/composables/useAuthorization";
import { useAuthStore } from "@/stores/auth";
import { getAgent, listAgents } from "@/services/agents/agents.service";
import type { Agent, AgentContext } from "@/services/agents/types";
import type { ChatAttachmentBlock } from "@/utils/chat-content";
import { createLanggraphAuthorizedFetch } from "@/services/langgraph/client";
import {
  createSessionService,
  type ChatThread,
} from "@/services/threads/session.service";
import BaseDialog from "@/components/base/BaseDialog.vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import EmptyState from "@/components/platform/EmptyState.vue";
import WorkspaceProjectSwitcher from "@/components/platform/WorkspaceProjectSwitcher.vue";
import UserMenu from "@/components/layout/UserMenu.vue";
import DearAgentSession from "../components/DearAgentSession.vue";
import DearAgentThreadSidebar from "../components/DearAgentThreadSidebar.vue";
import { buildChatThreadListView, type ChatThreadStatusFilter } from "../thread-list-view-model";
import { formatThreadTime } from "@/utils/threads";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const { activeProjectId, activeProject } = useWorkspaceProjectContext();
const { can } = useAuthorization();
const canWrite = computed(() =>
  can("project.runtime.write", activeProjectId.value),
);
type ChatTarget = {
  graphId: string;
  agentId?: string;
  name: string;
  context: AgentContext;
  disabled?: boolean;
};
const target = shallowRef<ChatTarget | null>(null);
const agents = ref<Agent[]>([]);
const threads = ref<ChatThread[]>([]);
const threadQuery = ref("");
const sidebarCollapsed = ref(typeof window !== "undefined" ? window.innerWidth < 1024 : false);
const focusMode = ref(false);
const threadStatus = ref<ChatThreadStatusFilter>("all");
const statusFilters = [{ value: "all", label: "全部" }, { value: "interrupted", label: "待处理" }, { value: "busy", label: "运行中" }, { value: "idle", label: "空闲" }, { value: "error", label: "异常" }] as const;
function exitFocus(event: KeyboardEvent) { if (event.key === "Escape") focusMode.value = false; }
document.addEventListener("keydown", exitFocus);
onScopeDispose(() => document.removeEventListener("keydown", exitFocus));
const threadListView = computed(() => buildChatThreadListView({
  items: threads.value.map(thread => ({ id: thread.thread_id, title: String(thread.metadata?.title || "未命名对话"), preview: String(thread.metadata?.preview || ""), updatedAt: thread.updated_at, time: formatThreadTime(thread.updated_at), status: thread.status })),
  query: threadQuery.value, statusFilter: threadStatus.value,
}));
const loading = ref(false);
const listLoading = ref(false);
const error = ref("");
const listError = ref("");
const draft = ref("");
let draftStorageKey = "";
function storeDraft(value: string) {
  if (!draftStorageKey) return;
  try {
    if (value) sessionStorage.setItem(draftStorageKey, value);
    else sessionStorage.removeItem(draftStorageKey);
  } catch { /* A blocked browser storage must not prevent typing. */ }
}
watch(draft, storeDraft, { flush: "sync" });
function restoreDraft(projectId: string, agentId: string, threadId?: string) {
  draftStorageKey = ["pw:dear-agent:draft", auth.user?.id, projectId, agentId, threadId || "new"].join(":");
  try { draft.value = sessionStorage.getItem(draftStorageKey) || ""; }
  catch { draft.value = ""; }
}
const draftAttachments = ref<ChatAttachmentBlock[]>([]);
const runContext = ref<AgentContext>({});
const recursionLimit = ref(25);
function resetDraft() {
  draftStorageKey = "";
  draft.value = "";
  draftAttachments.value = [];
  runContext.value = { ...target.value?.context };
  recursionLimit.value = 25;
}
const selectedThread = ref<string>();
const deleting = ref(false);
const deleteOpen = ref(false);
const deleteId = ref<string>();
function requestDelete(id: string) { deleteId.value = id; deleteOpen.value = true; }
async function deleteThread() {
  if (!deleteId.value || !canWrite.value || deleting.value) return;
  const id = deleteId.value;
  const requestEpoch = epoch;
  deleting.value = true;
  try {
    await service.value.remove(id);
    if (requestEpoch !== epoch) return;
    deleteOpen.value = false;
    if (selectedThread.value === id) await router.replace({ path: chatPath.value, query: { agentId: selectedTarget.value } });
    await loadThreads();
  } catch (cause) {
    if (requestEpoch === epoch) listError.value = cause instanceof Error ? cause.message : "删除对话失败";
  } finally { deleting.value = false; }
}
const mountedThread = ref<string>();
const mountVersion = ref(0);
const offset = ref(0);
const hasMore = ref(false);
let epoch = 0;
let listEpoch = 0;
let ownThread: string | undefined;
const service = computed(() => {
  void auth.sessionEpoch;
  return createSessionService(
    createLanggraphAuthorizedFetch(),
    activeProjectId.value,
  );
});
const chatPath = computed(
  () => `/workspace/projects/${encodeURIComponent(activeProjectId.value)}/dear-agent`,
);
const textParam = (value: unknown) =>
  typeof value === "string" ? value : undefined;
const selectedTarget = computed(() => target.value?.agentId ?? "");

const pageSize = 20;
const currentPage = computed(() => Math.floor(offset.value / pageSize) + 1);

async function loadThreads(reset = true) {
  if (!activeProjectId.value) return;
  const requestEpoch = ++listEpoch;
  const nextOffset = reset ? 0 : offset.value + pageSize;
  listLoading.value = true;
  listError.value = "";
  try {
    const rows = await service.value.list({
      offset: nextOffset,
      metadata: { graph_id: "dearflow_agent" },
    });
    if (requestEpoch !== listEpoch) return;
    threads.value = rows.filter(
      (thread) =>
        !thread.metadata?.graph_id ||
        thread.metadata.graph_id === "dearflow_agent" ||
        (target.value?.agentId && thread.metadata.agent_id === target.value.agentId),
    );
    offset.value = nextOffset;
    hasMore.value = rows.length === pageSize;
  } catch (cause) {
    if (requestEpoch === listEpoch)
      listError.value =
        cause instanceof Error ? cause.message : "对话列表读取失败";
  } finally {
    if (requestEpoch === listEpoch) listLoading.value = false;
  }
}

async function handlePageChange(targetPage: number) {
  if (targetPage < 1 || !activeProjectId.value) return;
  const requestEpoch = ++listEpoch;
  const nextOffset = (targetPage - 1) * pageSize;
  listLoading.value = true;
  listError.value = "";
  try {
    const rows = await service.value.list({
      offset: nextOffset,
      metadata: { graph_id: "dearflow_agent" },
    });
    if (requestEpoch !== listEpoch) return;
    threads.value = rows.filter(
      (thread) =>
        !thread.metadata?.graph_id ||
        thread.metadata.graph_id === "dearflow_agent" ||
        (target.value?.agentId && thread.metadata.agent_id === target.value.agentId),
    );
    offset.value = nextOffset;
    hasMore.value = rows.length === pageSize;
  } catch (cause) {
    if (requestEpoch === listEpoch)
      listError.value =
        cause instanceof Error ? cause.message : "对话列表读取失败";
  } finally {
    if (requestEpoch === listEpoch) listLoading.value = false;
  }
}

watch(
  [activeProjectId, () => auth.sessionEpoch],
  async ([projectId], _old, onCleanup) => {
    agents.value = [];
    threads.value = [];
    threadQuery.value = "";
    resetDraft();
    ++listEpoch;
    if (!projectId) return;
    let cancelled = false;
    onCleanup(() => {
      cancelled = true;
    });
    const results = await Promise.allSettled([
      can("project.assistant.read", projectId)
        ? listAgents(projectId, { limit: 200 })
        : Promise.resolve({ items: [] }),
    ]);
    if (cancelled) return;
    if (results[0].status === "fulfilled")
      agents.value = results[0].value.items.filter(
        (agent) => agent.status === "active",
      );
    if (results.some((result) => result.status === "rejected"))
      listError.value = "部分目标目录读取失败，请刷新重试";
    void loadThreads();
  },
  { immediate: true },
);

watch(
  [
    activeProjectId,
    () => auth.sessionEpoch,
    () => route.query?.agentId,
    () => route.query?.graphId,
    () => route.params?.threadId,
  ],
  async ([projectId, _session, agent, graph, thread]) => {
    const threadId = textParam(thread);
    if (threadId && threadId === ownThread && target.value) {
      ownThread = undefined;
      selectedThread.value = threadId;
      mountedThread.value = threadId;
      return;
    }
    const requestEpoch = ++epoch;
    ++mountVersion.value;
    target.value = null;
    selectedThread.value = threadId;
    mountedThread.value = threadId;
    resetDraft();
    error.value = "";
    if (!projectId) {
      loading.value = false;
      return;
    }
    loading.value = true;
    try {
      let agentId = textParam(agent);
      let graphId = textParam(graph);
      if (threadId) {
        const stored = await service.value.get(threadId);
        const metadata = stored.metadata ?? {};
        const storedGraph = textParam(metadata.graph_id);
        const storedAgent = textParam(metadata.agent_id);
        if (
          !storedGraph ||
          (graphId && graphId !== storedGraph) ||
          (agentId && storedAgent !== agentId)
        )
          throw new Error("对话与所选目标不一致");
        graphId = storedGraph;
        agentId = storedAgent;
      }
      if (!agentId && !graphId) {
        const dearflowAgent = agents.value.find((a) => a.graph_id === "dearflow_agent");
        if (dearflowAgent) {
          agentId = dearflowAgent.id;
          graphId = dearflowAgent.graph_id;
        } else if (agents.value.length > 0) {
          agentId = agents.value[0]?.id;
          graphId = agents.value[0]?.graph_id;
        } else {
          graphId = "dearflow_agent";
        }
      } else if (!agentId && graphId) {
        const aligned = await listAgents(projectId, { graphId, limit: 1 });
        agentId = aligned.items[0]?.id;
      }
      let resolved: ChatTarget | null = null;
      if (agentId) {
        const item = await getAgent(projectId, agentId);
        if (item.status !== "active" && !threadId)
          throw new Error("该 Agent 已停用");
        if (graphId && item.graph_id !== graphId)
          throw new Error("Agent 与对话的执行目标不一致");
        const available = await listAgents(projectId, { graphId: item.graph_id, limit: 1 });
        const authorized = available.items.some(agent => agent.id === item.id);
        if (!authorized && !threadId) throw new Error("执行目标不可用或未授权");
        resolved = {
          graphId: item.graph_id,
          agentId: item.id,
          name: item.name || "Dear Agent",
          context: item.context,
          disabled: item.status !== "active" || !authorized,
        };
      } else if (graphId) {
        resolved = {
          graphId,
          name: "Dear Agent",
          context: {},
          disabled: false,
        };
      }
      if (requestEpoch === epoch) {
        target.value = resolved;
        runContext.value = { ...resolved?.context };
        if (resolved?.agentId) restoreDraft(projectId, resolved.agentId, threadId);
      }
    } catch (cause) {
      if (requestEpoch === epoch)
        error.value = cause instanceof Error ? cause.message : "对话读取失败";
    } finally {
      if (requestEpoch === epoch) loading.value = false;
    }
  },
  { immediate: true },
);

function choose(value: string) {
  if (typeof window !== "undefined" && window.innerWidth < 1024) sidebarCollapsed.value = true;
  void router.push({ path: chatPath.value, query: { agentId: value } });
}
function openThread(id: string) {
  if (typeof window !== "undefined" && window.innerWidth < 1024) sidebarCollapsed.value = true;
  void router.push(`${chatPath.value}/${encodeURIComponent(id)}`);
}
function newThread() {
  if (typeof window !== "undefined" && window.innerWidth < 1024) sidebarCollapsed.value = true;
  if (target.value) choose(selectedTarget.value);
  if (!selectedThread.value) {
    resetDraft();
    if (target.value?.agentId) restoreDraft(activeProjectId.value, target.value.agentId);
    ++mountVersion.value;
  }
}
function created(id: string) {
  storeDraft("");
  draftStorageKey = ["pw:chat:draft", auth.user?.id, activeProjectId.value, target.value?.agentId, id].join(":");
  storeDraft(draft.value);
  ownThread = id;
  selectedThread.value = id;
  void router.replace({
    path: `${chatPath.value}/${encodeURIComponent(id)}`,
    query: route.query,
  });
}
function reconnect() {
  mountedThread.value = selectedThread.value;
  ++mountVersion.value;
}
onScopeDispose(() => {
  ++epoch;
  ++listEpoch;
});
</script>

<template>
  <section
    class="pw-chat-page-shell"
    :class="focusMode ? 'fixed inset-0 z-[85] m-0 !h-[100dvh] overflow-hidden bg-gray-50 p-4 dark:bg-dark-950 md:p-5 lg:p-6' : ''"
  >
    <EmptyState
      v-if="!activeProject"
      icon="project"
      title="请先选择项目"
      description="选择项目后开始对话。"
    />
    <template v-else>
      <div
        v-if="focusMode"
        class="flex items-center justify-between gap-3 rounded-2xl border border-gray-200 bg-white px-3 py-2 shadow-sm dark:border-dark-800 dark:bg-dark-900"
      >
        <div class="flex min-w-0 items-center gap-2">
          <span class="text-[10px] font-semibold uppercase tracking-[0.12em] text-gray-400">专注模式</span><span>·</span><span class="truncate text-sm font-semibold">{{ target?.name }}</span>
        </div>
        <BaseButton
          variant="secondary"
          class="h-8 px-3 text-xs"
          @click="focusMode = false"
        >
          <BaseIcon
            name="x"
            size="sm"
          />退出专注模式
        </BaseButton>
      </div>
      <p
        v-if="target?.disabled"
        role="status"
        class="mb-2 px-4 py-1.5 text-xs bg-amber-50 text-amber-700 border-b border-amber-200 dark:bg-amber-950/30 dark:text-amber-400 dark:border-amber-900/50"
      >
        该智能体已停用或未授权，当前仅可查看历史消息和投递状态。
      </p>
      <div class="!mt-0 relative flex min-h-0 flex-1 gap-0 overflow-hidden">
        <!-- 移动端抽屉蒙层 -->
        <div
          v-if="!sidebarCollapsed && !focusMode"
          class="fixed inset-0 z-40 bg-black/40 backdrop-blur-xs lg:hidden"
          @click="sidebarCollapsed = true"
        />

        <DearAgentThreadSidebar
          v-if="!sidebarCollapsed && !focusMode"
          v-model:search="threadQuery"
          v-model:status-filter="threadStatus"
          class="fixed inset-y-0 left-0 z-50 shadow-2xl lg:static lg:z-auto lg:shadow-none"
          :show-context-bar="true"
          :target-text="target?.name || ''"
          target-type-text="Agent"
          :filters="statusFilters"
          :loading="listLoading"
          :thread-count="threads.length"
          :filtered-count="threadListView.filteredItems.length"
          :can-start-thread="!!target"
          :active-thread-id="selectedThread || ''"
          :deleting-thread-id="deleting ? deleteId || '' : ''"
          :groups="threadListView.groups"
          :current-page="currentPage"
          :has-more="hasMore"
          :can-delete="canWrite"
          @start-new-thread="newThread"
          @select-thread="openThread"
          @delete-thread="requestDelete"
          @collapse="sidebarCollapsed = true"
          @page-change="handlePageChange"
          @load-more="loadThreads(false)"
        />
        <EmptyState
          v-if="loading"
          icon="chat"
          title="正在读取对话"
          description="正在核实目标与访问权限。"
        />
        <EmptyState
          v-else-if="error"
          icon="chat"
          title="无法打开对话"
          :description="error"
        />
        <DearAgentSession
          v-else-if="target"
          :key="`${activeProjectId}:${auth.sessionEpoch}:${mountVersion}`"
          v-model:context="runContext"
          v-model:attachments="draftAttachments"
          v-model:recursion-limit="recursionLimit"
          :focus-mode="focusMode"
          :project-id="activeProjectId"
          :project-name="activeProject.name"
          :target-name="target.name"
          :graph-id="target.graphId"
          :agent-id="target.agentId"
          :thread-id="mountedThread"
          :can-write="canWrite && !target.disabled"
          :draft="draft"
          @update:draft="draft = $event"
          @thread="created"
          @refresh="loadThreads()"
          @reconnect="reconnect"
        >
          <template #target>
            <button
              v-if="!focusMode"
              class="inline-flex h-7 shrink-0 items-center gap-1 rounded-md border px-2 text-xs font-medium shadow-2xs transition-colors"
              :class="
                sidebarCollapsed
                  ? 'border-gray-200/80 bg-white/90 text-gray-600 hover:bg-gray-50 hover:text-gray-900 dark:border-dark-700/80 dark:bg-dark-800/90 dark:text-dark-300 dark:hover:text-white'
                  : 'border-primary-200/80 bg-primary-50/70 text-primary-700 hover:bg-primary-100/70 dark:border-primary-800/60 dark:bg-primary-950/40 dark:text-primary-300'
              "
              :title="sidebarCollapsed ? '展开历史会话' : '收起历史会话'"
              @click="sidebarCollapsed = !sidebarCollapsed"
            >
              <BaseIcon
                name="columns"
                size="xs"
              />
              <span class="hidden sm:inline">{{ sidebarCollapsed ? '历史' : '收起' }}</span>
            </button>
            <div class="inline-flex shrink-0 items-center gap-2 rounded-lg border border-purple-200/80 bg-purple-50/70 px-2.5 py-1 text-xs font-semibold text-purple-700 shadow-2xs dark:border-purple-800/60 dark:bg-purple-950/40 dark:text-purple-300">
              <span class="inline-flex h-2 w-2 rounded-full bg-purple-500 animate-pulse" />
              <span class="tracking-wide">✨ Dear Agent</span>
              <span class="hidden md:inline rounded bg-purple-200/50 px-1 py-0.5 text-[10px] font-medium text-purple-800 dark:bg-purple-900/60 dark:text-purple-200">专属工作台</span>
            </div>
          </template>
          <template #actions>
            <div class="flex shrink-0 items-center gap-1.5">
              <button
                class="inline-flex h-7 shrink-0 items-center gap-1 rounded-md border border-gray-200/70 bg-white px-2 text-xs font-medium text-gray-500 shadow-2xs hover:bg-gray-50 hover:text-gray-800 dark:border-dark-700/80 dark:bg-dark-900 dark:text-dark-300 dark:hover:text-white transition-colors"
                :title="focusMode ? '退出专注模式' : '专注模式'"
                @click="focusMode = !focusMode"
              >
                <BaseIcon
                  name="focus"
                  size="xs"
                />
                <span class="hidden sm:inline">{{ focusMode ? '退出' : '专注' }}</span>
              </button>
              <button
                class="inline-flex h-7 shrink-0 items-center gap-1 rounded-md border border-gray-200/70 bg-white px-2 text-xs font-medium text-gray-700 shadow-2xs hover:bg-gray-50 hover:text-gray-900 disabled:cursor-not-allowed disabled:opacity-50 dark:border-dark-700/80 dark:bg-dark-900 dark:text-dark-200 dark:hover:text-white transition-colors"
                :disabled="!target"
                title="新建会话"
                @click="newThread"
              >
                <BaseIcon
                  name="chat"
                  size="xs"
                />
                <span>新对话</span>
              </button>
              <button
                v-if="selectedThread && canWrite"
                class="lg:hidden inline-flex h-7 shrink-0 items-center gap-1 rounded-md border border-red-200 bg-white px-2 text-xs font-medium text-red-600 shadow-2xs hover:bg-red-50 dark:border-red-900/50 dark:bg-dark-800 dark:text-red-400 dark:hover:bg-red-950/30 transition-colors"
                title="删除此会话"
                @click="requestDelete(selectedThread)"
              >
                <BaseIcon
                  name="trash"
                  size="xs"
                />
                <span class="hidden sm:inline">删除</span>
              </button>
              <div class="h-3.5 w-px bg-gray-200 dark:bg-dark-700 mx-0.5 hidden lg:block" />
              <div class="hidden lg:flex items-center gap-1.5 shrink-0">
                <WorkspaceProjectSwitcher />
                <UserMenu />
              </div>
            </div>
          </template>
        </DearAgentSession>
        <div
          v-else
          class="flex min-w-0 flex-1 flex-col items-center justify-center p-6 text-center"
        >
          <div class="mx-auto w-full max-w-md rounded-2xl border border-gray-200/80 bg-white/95 p-8 shadow-sm dark:border-dark-800 dark:bg-dark-900/90">
            <span class="mx-auto inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-tr from-primary-600 to-indigo-500 text-white shadow-md">
              <BaseIcon
                name="assistant"
                size="md"
              />
            </span>
            <h2 class="mt-4 text-base font-semibold text-gray-900 dark:text-white">
              Dear Agent 准备就绪
            </h2>
            <p class="mt-2 text-xs text-gray-500 dark:text-dark-400">
              点击下方按钮即可立即开启 Dear Agent 专属智能会话。
            </p>
            <div class="mt-6 flex justify-center">
              <BaseButton
                variant="primary"
                @click="newThread"
              >
                <BaseIcon
                  name="chat"
                  size="sm"
                />
                开启新对话
              </BaseButton>
            </div>
          </div>
        </div>
      </div>
    </template>
    <BaseDialog
      :show="deleteOpen"
      title="删除对话"
      @close="deleteOpen = false"
    >
      <p>删除后无法恢复此对话及运行历史。确认删除？</p>
      <template #footer>
        <BaseButton
          :loading="deleting"
          @click="deleteThread"
        >
          确认删除
        </BaseButton>
      </template>
    </BaseDialog>
  </section>
</template>

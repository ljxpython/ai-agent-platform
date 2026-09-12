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
import ChatSession from "../components/ChatSession.vue";
import ChatThreadSidebar from "../components/ChatThreadSidebar.vue";
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
const sidebarCollapsed = ref(false);
const focusMode = ref(false);
const threadStatus = ref<ChatThreadStatusFilter>("all");
const statusFilters = [{ value: "all", label: "全部" }, { value: "interrupted", label: "待处理" }, { value: "busy", label: "运行中" }, { value: "idle", label: "空闲" }, { value: "error", label: "异常" }] as const;
function exitFocus(event: KeyboardEvent) { if (event.key === "Escape") focusMode.value = false; }
document.addEventListener("keydown", exitFocus);
onScopeDispose(() => document.removeEventListener("keydown", exitFocus));
const visibleThreads = computed(() => {
  const query = threadQuery.value.trim().toLocaleLowerCase();
  return threads.value.filter(thread => (threadStatus.value === "all" || thread.status === threadStatus.value) && (!query || `${thread.metadata?.title ?? ""} ${thread.thread_id}`.toLocaleLowerCase().includes(query)));
});
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
  draftStorageKey = ["pw:chat:draft", auth.user?.id, projectId, agentId, threadId || "new"].join(":");
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
  () => `/workspace/projects/${encodeURIComponent(activeProjectId.value)}/chat`,
);
const textParam = (value: unknown) =>
  typeof value === "string" ? value : undefined;
const selectedTarget = computed(() => target.value?.agentId ?? "");

async function loadThreads(reset = true) {
  if (!activeProjectId.value) return;
  const requestEpoch = ++listEpoch;
  const nextOffset = reset ? 0 : offset.value + 20;
  listLoading.value = true;
  listError.value = "";
  try {
    const rows = await service.value.list(nextOffset);
    if (requestEpoch !== listEpoch) return;
    threads.value = reset ? rows : [...threads.value, ...rows];
    offset.value = nextOffset;
    hasMore.value = rows.length === 20;
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
    () => route.query.agentId,
    () => route.query.graphId,
    () => route.params.threadId,
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
      // Graph links resolve the same project Agent; there is no second execution mode.
      if (!agentId && graphId) {
        const aligned = await listAgents(projectId, { graphId, limit: 1 });
        agentId = aligned.items[0]?.id;
        if (!agentId) throw new Error("该智能体不可用或未授权");
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
          name: item.name,
          context: item.context,
          disabled: item.status !== "active" || !authorized,
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
  void router.push({ path: chatPath.value, query: { agentId: value } });
}
function openThread(id: string) {
  void router.push(`${chatPath.value}/${encodeURIComponent(id)}`);
}
function newThread() {
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
      <input
        v-if="threads.length && !focusMode"
        v-model="threadQuery"
        aria-label="筛选已加载对话"
        placeholder="筛选已加载对话"
        class="pw-input mb-3 lg:hidden"
      >
      <div
        v-if="threads.length && !focusMode"
        class="mb-3 flex gap-2 lg:hidden"
      >
        <select
          aria-label="历史对话"
          class="pw-input min-w-0 flex-1"
          :value="selectedThread || ''"
          @change="openThread(($event.target as HTMLSelectElement).value)"
        >
          <option
            value=""
            disabled
          >
            选择历史对话
          </option>
          <option
            v-for="thread in visibleThreads"
            :key="thread.thread_id"
            :value="thread.thread_id"
          >
            {{ thread.metadata?.title || '未命名对话' }}
          </option>
        </select>
        <button
          v-if="hasMore"
          class="pw-table-tool-button"
          :disabled="listLoading"
          @click="loadThreads(false)"
        >
          加载更多
        </button>
      </div>
      <p
        v-if="listError"
        role="alert"
        class="mb-2 text-sm text-red-600 lg:hidden"
      >
        {{ listError }} <button
          class="underline"
          @click="loadThreads()"
        >
          重试
        </button>
      </p>
      <p
        v-if="target?.disabled"
        role="status"
        class="mb-3 text-sm text-gray-500"
      >
        该智能体已停用或未授权，当前仅可查看历史消息和投递状态。
      </p>
      <div class="!mt-0 flex min-h-0 flex-1 gap-4 overflow-hidden">
        <ChatThreadSidebar
          v-if="!sidebarCollapsed && !focusMode"
          v-model:search="threadQuery"
          v-model:status-filter="threadStatus"
          class="hidden lg:flex"
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
          :has-more="hasMore"
          :can-delete="canWrite"
          @start-new-thread="newThread"
          @select-thread="openThread"
          @delete-thread="requestDelete"
          @collapse="sidebarCollapsed = true"
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
        <ChatSession
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
              v-if="sidebarCollapsed && !focusMode"
              class="pw-table-tool-button h-8 px-2 text-xs"
              @click="sidebarCollapsed = false"
            >
              展开历史
            </button>
            <select
              :value="selectedTarget"
              aria-label="对话目标"
              class="pw-input h-8 max-w-[150px] py-1 text-xs"
              @change="choose(($event.target as HTMLSelectElement).value)"
            >
              <option
                value=""
                disabled
              >
                选择智能体
              </option>
              <option
                v-for="agent in agents"
                :key="agent.id"
                :value="agent.id"
              >
                {{ agent.name }}
              </option>
            </select>
          </template>
          <template #actions>
            <button
              class="pw-table-tool-button h-8 px-3 text-xs"
              @click="focusMode = !focusMode"
            >
              {{ focusMode ? '退出专注模式' : '专注模式' }}
            </button>
            <button
              class="pw-table-tool-button h-8 px-3 text-xs"
              :disabled="!target"
              @click="newThread"
            >
              新对话
            </button>
            <button
              v-if="selectedThread && canWrite"
              class="lg:hidden pw-table-tool-button h-8 px-3 text-xs"
              @click="requestDelete(selectedThread)"
            >
              删除对话
            </button>
          </template>
        </ChatSession>
        <div
          v-else
          class="flex min-w-0 flex-1 flex-col items-center justify-center gap-4"
        >
          <select
            :value="selectedTarget"
            aria-label="对话目标"
            class="pw-input h-8 max-w-[150px] py-1 text-xs"
            @change="choose(($event.target as HTMLSelectElement).value)"
          >
            <option
              value=""
              disabled
            >
              选择智能体
            </option>
            <option
              v-for="agent in agents"
              :key="agent.id"
              :value="agent.id"
            >
              {{ agent.name }}
            </option>
          </select>
          <EmptyState
            icon="chat"
            title="选择一个对话目标"
            description="选择项目已授权的智能体，开始新的对话。"
          />
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

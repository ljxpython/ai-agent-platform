import { ref, computed, watch, onMounted, getCurrentInstance } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useWorkspaceProjectContext } from "@/composables/useWorkspaceProjectContext";
import { createLanggraphAuthorizedFetch } from "@/services/langgraph/client";
import {
  createSessionService,
  type ChatThread,
} from "@/services/threads/session.service";

/**
 * Dear Agent 治理上下文：自动获取当前项目下最新 Dear 会话 ID 并绑定，
 * 无会话时提供自动降级空态与一键创建会话机制。
 */
export function useDearGovernanceContext() {
  const route = useRoute();
  const router = useRouter();
  const { activeProject, activeProjectId } = useWorkspaceProjectContext();

  const threads = ref<ChatThread[]>([]);
  const activeThreadId = ref<string>("");
  const loading = ref(false);
  const error = ref("");
  const isCreatingThread = ref(false);

  const sessionService = computed(() => {
    return createSessionService(createLanggraphAuthorizedFetch(), activeProjectId.value);
  });

  const activeThread = computed(() => {
    return threads.value.find((t) => t.thread_id === activeThreadId.value) || null;
  });

  const hasThreads = computed(() => threads.value.length > 0);

  async function loadThreads() {
    if (!activeProjectId.value) {
      threads.value = [];
      activeThreadId.value = "";
      return;
    }
    loading.value = true;
    error.value = "";
    try {
      const rows = await sessionService.value.list({
        offset: 0,
        metadata: { graph_id: "dearflow_agent" },
      });
      threads.value = rows.filter(
        (t) => !t.metadata?.graph_id || t.metadata.graph_id === "dearflow_agent",
      );

      // 优先根据 route.query.threadId 绑定；若不存在则自动选择列表第一条（最新会话）
      const queryThreadId = (route.query.threadId as string) || "";
      if (queryThreadId && threads.value.some((t) => t.thread_id === queryThreadId)) {
        activeThreadId.value = queryThreadId;
      } else if (threads.value.length > 0) {
        // 如果当前选中的 threadId 已经在列表中，保留；否则默认选中第一条
        if (!activeThreadId.value || !threads.value.some((t) => t.thread_id === activeThreadId.value)) {
          activeThreadId.value = threads.value[0].thread_id;
        }
      } else {
        activeThreadId.value = "";
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : "获取 Dear 会话列表失败";
    } finally {
      loading.value = false;
    }
  }

  function switchThread(threadId: string) {
    if (activeThreadId.value === threadId) return;
    activeThreadId.value = threadId;
    // 同步更新路由 query
    router.replace({
      query: { ...route.query, threadId },
    });
  }

  async function createInitialThread(): Promise<ChatThread | null> {
    if (!activeProjectId.value || isCreatingThread.value) return null;
    isCreatingThread.value = true;
    error.value = "";
    try {
      const newThread = await sessionService.value.create(
        "dearflow_agent",
        undefined,
        "新研究会话"
      );
      threads.value.unshift(newThread);
      activeThreadId.value = newThread.thread_id;
      router.replace({
        query: { ...route.query, threadId: newThread.thread_id },
      });
      return newThread;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "创建初始 Dear 会话失败";
      return null;
    } finally {
      isCreatingThread.value = false;
    }
  }

  watch(activeProjectId, () => {
    loadThreads();
  });

  if (getCurrentInstance()) {
    onMounted(() => {
      loadThreads();
    });
  } else {
    loadThreads();
  }

  return {
    activeProject,
    activeProjectId,
    threads,
    activeThreadId,
    activeThread,
    hasThreads,
    loading,
    error,
    isCreatingThread,
    refreshThreads: loadThreads,
    switchThread,
    createInitialThread,
  };
}

import { describe, expect, it, vi, beforeEach } from "vitest";
import { ref } from "vue";
import { useDearGovernanceContext } from "./useDearGovernanceContext";

const mockReplace = vi.fn();
const mockRoute = {
  params: { projectId: "proj-1" },
  query: {} as Record<string, string>,
};

vi.mock("vue-router", () => ({
  useRoute: () => mockRoute,
  useRouter: () => ({
    replace: mockReplace,
  }),
}));

const activeProjectIdRef = ref("proj-1");
vi.mock("@/composables/useWorkspaceProjectContext", () => ({
  useWorkspaceProjectContext: () => ({
    activeProjectId: activeProjectIdRef,
    activeProject: ref({ id: "proj-1", name: "测试项目" }),
  }),
}));

const mockList = vi.fn();
const mockCreate = vi.fn();

vi.mock("@/services/threads/session.service", () => ({
  createSessionService: () => ({
    list: mockList,
    create: mockCreate,
  }),
}));

describe("useDearGovernanceContext", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRoute.query = {};
  });

  it("自动加载并绑定第一个最新 Dear 会话", async () => {
    mockList.mockResolvedValueOnce([
      { thread_id: "th-latest", metadata: { graph_id: "dearflow_agent", title: "最新会话" } },
      { thread_id: "th-older", metadata: { graph_id: "dearflow_agent", title: "旧会话" } },
      { thread_id: "th-other", metadata: { graph_id: "other_agent" } },
    ]);

    const context = useDearGovernanceContext();
    await context.refreshThreads();

    expect(context.threads.value).toHaveLength(2);
    expect(context.activeThreadId.value).toBe("th-latest");
    expect(context.activeThread.value?.metadata?.title).toBe("最新会话");
    expect(context.hasThreads.value).toBe(true);
  });

  it("当 query.threadId 存在且合法时优先绑定该会话", async () => {
    mockRoute.query = { threadId: "th-older" };
    mockList.mockResolvedValueOnce([
      { thread_id: "th-latest", metadata: { graph_id: "dearflow_agent", title: "最新会话" } },
      { thread_id: "th-older", metadata: { graph_id: "dearflow_agent", title: "旧会话" } },
    ]);

    const context = useDearGovernanceContext();
    await context.refreshThreads();

    expect(context.activeThreadId.value).toBe("th-older");
  });

  it("支持手动调用 switchThread 切换会话并更新路由", async () => {
    mockList.mockResolvedValueOnce([
      { thread_id: "th-1", metadata: { graph_id: "dearflow_agent" } },
      { thread_id: "th-2", metadata: { graph_id: "dearflow_agent" } },
    ]);

    const context = useDearGovernanceContext();
    await context.refreshThreads();

    context.switchThread("th-2");
    expect(context.activeThreadId.value).toBe("th-2");
    expect(mockReplace).toHaveBeenCalledWith({
      query: { threadId: "th-2" },
    });
  });

  it("无会话时提供 createInitialThread 一键创建并绑定", async () => {
    mockList.mockResolvedValueOnce([]);
    mockCreate.mockResolvedValueOnce({
      thread_id: "th-created",
      metadata: { graph_id: "dearflow_agent", title: "新研究会话" },
    });

    const context = useDearGovernanceContext();
    await context.refreshThreads();

    expect(context.hasThreads.value).toBe(false);
    expect(context.activeThreadId.value).toBe("");

    const created = await context.createInitialThread();
    expect(created?.thread_id).toBe("th-created");
    expect(context.activeThreadId.value).toBe("th-created");
    expect(context.threads.value).toHaveLength(1);
    expect(context.hasThreads.value).toBe(true);
  });
});

import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { reactive, ref } from "vue";

const activeProjectIdRef = ref("proj-1");
const activeProjectRef = ref<{ id: string; name: string } | null>({
  id: "proj-1",
  name: "测试项目",
});

const routeState = reactive({
  params: { projectId: "proj-1", threadId: "" },
  query: {} as Record<string, string>,
});

vi.mock("vue-router", () => ({
  useRoute: () => routeState,
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

vi.mock("@/composables/useWorkspaceProjectContext", () => ({
  useWorkspaceProjectContext: () => ({
    activeProjectId: activeProjectIdRef,
    activeProject: activeProjectRef,
  }),
}));

vi.mock("@/composables/useAuthorization", () => ({
  useAuthorization: () => ({ can: () => true }),
}));

vi.mock("@/stores/auth", () => ({
  useAuthStore: () => ({ user: { id: "user-1", name: "老王" } }),
}));

const mockThreads = [
  {
    thread_id: "th-1",
    updated_at: "2026-09-14T08:00:00Z",
    status: "idle",
    metadata: { title: "给我画一个支付累积查询技术架构图", graph_id: "dearflow_agent" },
  },
  {
    thread_id: "th-2",
    updated_at: "2026-09-14T07:00:00Z",
    status: "idle",
    metadata: { title: "分析当前项目", graph_id: "dearflow_agent" },
  },
  {
    thread_id: "th-3",
    updated_at: "2026-09-14T06:00:00Z",
    status: "idle",
    metadata: { title: "电商支付架构设计", graph_id: "dearflow_agent" },
  },
];

const mockList = vi.fn().mockImplementation((options?: { metadata?: Record<string, unknown> }) => {
  const meta = options?.metadata;
  if (!meta) return Promise.resolve(mockThreads);
  if (meta.graph_id === "showcase_demo") return Promise.resolve([]);
  if (meta.graph_id === "dearflow_agent") return Promise.resolve(mockThreads);
  return Promise.resolve(mockThreads);
});

vi.mock("@/services/threads/session.service", async (importOriginal) => ({
  ...await importOriginal<typeof import("@/services/threads/session.service")>(),
  createSessionService: () => ({
    list: mockList,
    count: vi.fn().mockImplementation((options?: { metadata?: Record<string, unknown> }) => {
      const meta = options?.metadata;
      if (!meta) return Promise.resolve(3);
      if (meta.graph_id === "showcase_demo") return Promise.resolve(0);
      if (meta.graph_id === "dearflow_agent") return Promise.resolve(3);
      return Promise.resolve(3);
    }),
    remove: vi.fn().mockResolvedValue({}),
    get: vi.fn().mockImplementation((id: string) => {
      const match = mockThreads.find((t) => t.thread_id === id);
      return Promise.resolve(match || { thread_id: id, metadata: { graph_id: "dearflow_agent" } });
    }),
  }),
}));

vi.mock("@/services/langgraph/client", () => ({
  createLanggraphAuthorizedFetch: () => vi.fn(),
}));

vi.mock("@/services/agents/agents.service", () => ({
  listAgents: vi.fn().mockResolvedValue({
    items: [
      {
        id: "agent-dearflow",
        name: "dearflow_agent",
        graph_id: "dearflow_agent",
        status: "active",
      },
      {
        id: "agent-showcase",
        name: "showcase_demo",
        graph_id: "showcase_demo",
        status: "active",
      },
    ],
  }),
  getAgent: vi.fn().mockImplementation((_proj: string, id: string) => {
    if (id === "agent-showcase") {
      return Promise.resolve({
        id: "agent-showcase",
        name: "showcase_demo",
        graph_id: "showcase_demo",
        status: "active",
        context: {},
      });
    }
    return Promise.resolve({
      id: "agent-dearflow",
      name: "dearflow_agent",
      graph_id: "dearflow_agent",
      status: "active",
      context: {},
    });
  }),
}));

import ChatPage from "./ChatPage.vue";

describe("ChatPage.vue", () => {
  it("aligns thread list with selected agent and shows full list when empty", async () => {
    routeState.params = { projectId: "proj-1", threadId: "" };
    routeState.query = {};

    const wrapper = mount(ChatPage, {
      global: {
        stubs: {
          ChatThreadSidebar: {
            props: ["threadCount", "activeThreadId"],
            template:
              '<aside data-testid="chat-sidebar" :data-thread-count="threadCount" :data-active-thread="activeThreadId"><slot /></aside>',
          },
          ChatSession: {
            props: ["projectId", "graphId", "agentId", "threadId"],
            template:
              '<div data-testid="chat-session" :data-agent="agentId" :data-graph="graphId" :data-thread="threadId"><slot name="target" /><slot name="actions" /></div>',
          },
          ChatAgentSelector: {
            props: ["agents", "selectedAgentId"],
            template:
              '<div data-testid="agent-selector"><button data-testid="select-agent-btn" @click="$emit(\'select\', \'agent-dearflow\')">选择智能体</button></div>',
          },
          WorkspaceProjectSwitcher: true,
          UserMenu: true,
          BaseDialog: true,
          BaseButton: true,
          BaseIcon: true,
          EmptyState: true,
        },
      },
    });

    await flushPromises();

    // 1. 当选择为空（所有智能体）时：左侧侧边栏展示所有 3 条会话
    const sidebarEl = wrapper.find('[data-testid="chat-sidebar"]');
    expect(sidebarEl.exists()).toBe(true);
    expect(sidebarEl.attributes("data-thread-count")).toBe("3");
    expect(wrapper.text()).toContain("请选择一个对话智能体");

    // 2. 当选择 showcase_demo 智能体时：左侧侧边栏只显示该智能体的会话（0条），而不是全集
    routeState.query = { agentId: "agent-showcase" };
    await flushPromises();

    expect(sidebarEl.attributes("data-thread-count")).toBe("0");
    const showcaseSession = wrapper.find('[data-testid="chat-session"]');
    expect(showcaseSession.exists()).toBe(true);
    expect(showcaseSession.attributes("data-agent")).toBe("agent-showcase");
    expect(showcaseSession.attributes("data-graph")).toBe("showcase_demo");

    // 3. 当选择 dearflow_agent 智能体时：左侧侧边栏只显示 dearflow_agent 的会话（3条）
    routeState.query = { agentId: "agent-dearflow" };
    await flushPromises();

    expect(sidebarEl.attributes("data-thread-count")).toBe("3");
    const dearflowSession = wrapper.find('[data-testid="chat-session"]');
    expect(dearflowSession.exists()).toBe(true);
    expect(dearflowSession.attributes("data-agent")).toBe("agent-dearflow");
    expect(dearflowSession.attributes("data-graph")).toBe("dearflow_agent");

    // 4. 当选择为空（切回所有智能体）时：再次展示全部 3 条会话
    routeState.query = {};
    await flushPromises();

    expect(sidebarEl.attributes("data-thread-count")).toBe("3");
  });

  it("opens historical thread without stored agent_id seamlessly", async () => {
    // 模拟进入一个历史会话 th-3（电商支付架构设计，无 metadata.agent_id，graph 为 dearflow_agent）
    routeState.params = { projectId: "proj-1", threadId: "th-3" };
    routeState.query = {};

    const wrapper = mount(ChatPage, {
      global: {
        stubs: {
          ChatThreadSidebar: {
            props: ["threadCount", "activeThreadId"],
            template:
              '<aside data-testid="chat-sidebar" :data-thread-count="threadCount" :data-active-thread="activeThreadId"><slot /></aside>',
          },
          ChatSession: {
            props: ["projectId", "graphId", "agentId", "threadId"],
            template:
              '<div data-testid="chat-session" :data-agent="agentId" :data-graph="graphId" :data-thread="threadId"><slot name="target" /><slot name="actions" /></div>',
          },
          ChatAgentSelector: true,
          WorkspaceProjectSwitcher: true,
          UserMenu: true,
          BaseDialog: true,
          BaseButton: true,
          BaseIcon: true,
          EmptyState: true,
        },
      },
    });

    await flushPromises();

    const sidebarEl = wrapper.find('[data-testid="chat-sidebar"]');
    expect(sidebarEl.attributes("data-thread-count")).toBe("3");
    expect(sidebarEl.attributes("data-active-thread")).toBe("th-3");

    const sessionEl = wrapper.find('[data-testid="chat-session"]');
    expect(sessionEl.exists()).toBe(true);
    expect(sessionEl.attributes("data-thread")).toBe("th-3");
    expect(sessionEl.attributes("data-graph")).toBe("dearflow_agent");
  });
});

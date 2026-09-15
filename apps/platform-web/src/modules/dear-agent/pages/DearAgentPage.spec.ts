import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { ref } from "vue";

const activeProjectIdRef = ref("proj-1");
const activeProjectRef = ref<{ id: string; name: string } | null>({ id: "proj-1", name: "测试项目" });

vi.mock("vue-router", () => ({
  useRoute: () => ({ params: { projectId: "proj-1", threadId: "th-1" }, query: {} }),
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

vi.mock("@/services/threads/session.service", () => ({
  createSessionService: () => ({
    list: vi.fn().mockResolvedValue([
      {
        thread_id: "th-1",
        updated_at: "2026-09-14T08:00:00Z",
        status: "idle",
        metadata: { title: "测试对话 1", graph_id: "dearflow_agent" },
      },
    ]),
    remove: vi.fn().mockResolvedValue({}),
    get: vi.fn().mockResolvedValue({
      thread_id: "th-1",
      metadata: { graph_id: "dearflow_agent" },
    }),
  }),
}));

vi.mock("@/services/langgraph/client", () => ({
  createLanggraphAuthorizedFetch: () => vi.fn(),
}));

vi.mock("@/services/agents/agents.service", () => ({
  listAgents: vi.fn().mockResolvedValue({ items: [] }),
  getAgent: vi.fn().mockResolvedValue({
    id: "agent-1",
    name: "Dear Agent",
    graph_id: "dearflow_agent",
    status: "active",
    context: {},
  }),
}));

import DearAgentPage from "./DearAgentPage.vue";

describe("DearAgentPage.vue", () => {
  it("renders sidebar and active session when activeProjectId is provided", async () => {
    const wrapper = mount(DearAgentPage, {
      global: {
        stubs: {
          DearAgentThreadSidebar: {
            template: '<aside data-testid="dear-sidebar"><slot /></aside>',
          },
          DearAgentSession: {
            props: ["projectId", "graphId", "threadId"],
            template:
              '<div data-testid="dear-session" :data-graph="graphId" :data-thread="threadId"><slot name="target" /><slot name="actions" /></div>',
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

    expect(wrapper.find('[data-testid="dear-sidebar"]').exists()).toBe(true);
    const sessionEl = wrapper.find('[data-testid="dear-session"]');
    expect(sessionEl.exists()).toBe(true);
    expect(sessionEl.attributes("data-graph")).toBe("dearflow_agent");
    expect(sessionEl.attributes("data-thread")).toBe("th-1");
    expect(wrapper.text()).toContain("✨ Dear Agent");
  });

  it("shows empty state when no active project is selected", async () => {
    activeProjectIdRef.value = "";
    activeProjectRef.value = null;
    const wrapper = mount(DearAgentPage, {
      global: {
        stubs: {
          DearAgentThreadSidebar: true,
          DearAgentSession: true,
          WorkspaceProjectSwitcher: true,
          UserMenu: true,
          ChatAgentSelector: true,
          BaseDialog: true,
          BaseButton: true,
          BaseIcon: true,
          EmptyState: {
            template: '<div data-testid="empty-state">请先选择项目</div>',
          },
        },
      },
    });

    await flushPromises();

    expect(wrapper.find('[data-testid="empty-state"]').exists()).toBe(true);
    activeProjectIdRef.value = "proj-1"; // restore
    activeProjectRef.value = { id: "proj-1", name: "测试项目" };
  });
});

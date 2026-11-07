import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, expect, it, vi } from "vitest";
import { ref } from "vue";
import OverviewPage from "./OverviewPage.vue";

const activeProjectId = ref("proj-1");
const activeProject = ref({
  id: "proj-1",
  name: "工业测试项目",
  description: "用于测试工业级工作区总览",
});
const activeProjects = ref([activeProject.value]);

const mocks = vi.hoisted(() => ({
  can: vi.fn(),
  listAgents: vi.fn(),
  listThreads: vi.fn(),
  listTools: vi.fn(),
}));

vi.mock("@/composables/useWorkspaceProjectContext", () => ({
  useWorkspaceProjectContext: () => ({
    activeProjectId,
    activeProject,
    activeProjects,
  }),
}));

vi.mock("@/composables/useAuthorization", () => ({
  useAuthorization: () => ({
    can: mocks.can,
    canAnyProject: () => false,
    currentProjectCan: () => false,
  }),
}));

vi.mock("@/stores/auth", () => ({
  useAuthStore: () => ({
    sessionEpoch: 1,
  }),
}));

vi.mock("@/services/agents/agents.service", () => ({
  listAgents: mocks.listAgents,
}));

vi.mock("@/services/runtime/runtime.service", () => ({
  listRuntimeTools: mocks.listTools,
}));

vi.mock("@/services/langgraph/client", () => ({
  createLanggraphAuthorizedFetch: vi.fn(),
}));

vi.mock("@/services/threads/session.service", () => ({
  createSessionService: () => ({
    list: mocks.listThreads,
  }),
}));

function render() {
  return mount(OverviewPage, {
    global: {
      stubs: {
        RouterLink: {
          props: ["to"],
          template: '<a :href="to"><slot /></a>',
        },
        BaseIcon: {
          props: ["name"],
          template: '<i :data-icon="name" />',
        },
        PageHeader: {
          props: ["title", "description", "compact"],
          template: `
            <header data-testid="page-header" :data-compact="compact">
              <h1>{{ title }}</h1>
              <p v-if="description" data-testid="page-desc">{{ description }}</p>
              <slot name="actions" />
            </header>
          `,
        },
        MetricCard: {
          props: ["label", "value", "hint", "icon", "tone"],
          template: `
            <div data-testid="metric-card" :data-label="label">
              <span>{{ label }}</span>: <span>{{ value }}</span>
            </div>
          `,
        },
        SurfaceCard: {
          template: '<div class="surface-card"><slot /></div>',
        },
        EmptyState: {
          props: ["title"],
          template: '<div data-testid="empty-state">{{ title }}</div>',
        },
        StateBanner: {
          props: ["title", "description"],
          template: '<div data-testid="state-banner">{{ title }}</div>',
        },
      },
    },
  });
}

beforeEach(() => {
  vi.resetAllMocks();
  mocks.can.mockImplementation((perm: string) => {
    if (perm === "project.assistant.read") return true;
    if (perm === "project.runtime.read") return true;
    if (perm === "platform.config.read") return true;
    return false;
  });

  mocks.listAgents.mockResolvedValue({
    total: 2,
    items: [
      {
        id: "agent-1",
        project_id: "proj-1",
        name: "代码助手",
        status: "active",
        graph_id: "code-graph",
        description: "负责代码重构与审查",
        context: {
          model_id: "deepseek-v4.1-flash",
        },
      },
      {
        id: "agent-2",
        project_id: "proj-1",
        name: "调研专员",
        status: "disabled",
        graph_id: "research-graph",
        description: "深度行业调研",
        context: {
          model_id: "step-5-preview",
        },
      },
    ],
  });

  mocks.listThreads.mockResolvedValue([
    {
      thread_id: "thread-101",
      updated_at: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
      metadata: { title: "电商架构设计讨论" },
    },
    {
      thread_id: "thread-102",
      updated_at: new Date(Date.now() - 2 * 3600 * 1000).toISOString(),
      metadata: { title: "Loki 分布式链路排障" },
    },
  ]);

  mocks.listTools.mockResolvedValue({
    count: 8,
    tools: [],
  });
});

it("renders industrial overview with 4 metric cards and no boilerplate description", async () => {
  const wrapper = render();
  try {
    await flushPromises();

    // 1. 废话副标题彻底被清除
    expect(wrapper.find('[data-testid="page-desc"]').exists()).toBe(false);

    // 2. 4 联指标看板全部渲染并映射正确数值
    const metricCards = wrapper.findAll('[data-testid="metric-card"]');
    expect(metricCards.length).toBe(4);
    expect(wrapper.text()).toContain("项目 Agents: 2");
    expect(wrapper.text()).toContain("活跃会话: 2");
    expect(wrapper.text()).toContain("装配工具: 8");
    expect(wrapper.text()).toContain("运行时引擎: LangGraph");

    // 3. 项目名称与就绪状态
    expect(wrapper.text()).toContain("工业测试项目");
    expect(wrapper.text()).toContain("就绪");

    // 4. 平台治理按钮优雅收敛在 Header Actions 插槽中
    const header = wrapper.find('[data-testid="page-header"]');
    expect(header.text()).toContain("平台治理");
    expect(header.text()).toContain("刷新");
  } finally {
    wrapper.unmount();
  }
});

it("renders agents with model badge and quick chat action", async () => {
  const wrapper = render();
  try {
    await flushPromises();

    expect(wrapper.text()).toContain("代码助手");
    expect(wrapper.text()).toContain("deepseek-v4.1-flash");
    expect(wrapper.text()).toContain("调研专员");
    expect(wrapper.text()).toContain("step-5-preview");

    // 快捷对话按钮直达链接测试
    const quickChatLink = wrapper
      .findAll("a")
      .find((el) => el.attributes("href")?.includes("/chat?agent=agent-1"));
    expect(quickChatLink).toBeDefined();
  } finally {
    wrapper.unmount();
  }
});

it("renders recent threads with relative time and direct link", async () => {
  const wrapper = render();
  try {
    await flushPromises();

    expect(wrapper.text()).toContain("电商架构设计讨论");
    expect(wrapper.text()).toContain("5 分钟前");
    expect(wrapper.text()).toContain("Loki 分布式链路排障");
    expect(wrapper.text()).toContain("2 小时前");
  } finally {
    wrapper.unmount();
  }
});

it("hides platform governance action when user lacks permission", async () => {
  mocks.can.mockImplementation((perm: string) => {
    if (perm === "platform.config.read") return false;
    return true;
  });

  const wrapper = render();
  try {
    await flushPromises();

    const header = wrapper.find('[data-testid="page-header"]');
    expect(header.text()).not.toContain("平台治理");
  } finally {
    wrapper.unmount();
  }
});

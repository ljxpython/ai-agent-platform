import { mount, flushPromises } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  mockGetAgent,
  mockListGraphsPage,
  mockListRuntimeModels,
  mockListRuntimeTools,
  mockListToolRestrictions,
  mockListRuntimeModelPolicies,
  mockGetAgentParameterSchema,
  mockUpdateAgent,
  mockCreateAgent,
} = vi.hoisted(() => ({
  mockGetAgent: vi.fn(),
  mockListGraphsPage: vi.fn(),
  mockListRuntimeModels: vi.fn(),
  mockListRuntimeTools: vi.fn(),
  mockListToolRestrictions: vi.fn(),
  mockListRuntimeModelPolicies: vi.fn(),
  mockGetAgentParameterSchema: vi.fn(),
  mockUpdateAgent: vi.fn(),
  mockCreateAgent: vi.fn(),
}));

vi.mock("vue-router", () => ({
  useRoute: () => ({ params: { agentId: "agent-1" } }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

import { ref } from "vue";

vi.mock("@/composables/useWorkspaceProjectContext", () => ({
  useWorkspaceProjectContext: () => ({ activeProjectId: ref("proj-1") }),
}));

vi.mock("@/composables/useAuthorization", () => ({
  useAuthorization: () => ({ can: () => true }),
}));

vi.mock("@/services/agents/agents.service", () => ({
  createAgent: mockCreateAgent,
  getAgent: mockGetAgent,
  getAgentParameterSchema: mockGetAgentParameterSchema,
  updateAgent: mockUpdateAgent,
}));

vi.mock("@/services/graphs/graphs.service", () => ({
  listGraphsPage: mockListGraphsPage,
}));

vi.mock("@/services/runtime/runtime.service", () => ({
  listRuntimeModels: mockListRuntimeModels,
  listRuntimeTools: mockListRuntimeTools,
}));

vi.mock("@/services/runtime-policies/runtime-policies.service", () => ({
  listRuntimeModelPolicies: mockListRuntimeModelPolicies,
  listToolRestrictions: mockListToolRestrictions,
}));

import AgentEditorPage from "./AgentEditorPage.vue";

describe("AgentEditorPage - Tool Restrictions Display", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    mockGetAgent.mockResolvedValue({
      id: "agent-1",
      name: "测试智能体",
      description: "老王的测试Agent",
      graph_id: "graph-chat",
      status: "active",
      context: {},
    });

    mockListGraphsPage.mockResolvedValue({
      items: [
        {
          graph_id: "graph-chat",
          display_name: "Chat Graph",
        },
      ],
    });

    mockListRuntimeModels.mockResolvedValue({
      models: [],
    });

    mockListRuntimeModelPolicies.mockResolvedValue({
      items: [],
    });

    mockGetAgentParameterSchema.mockResolvedValue({
      properties: {},
    });

    mockListRuntimeTools.mockResolvedValue({
      tools: [
        {
          name: "Web搜索",
          tool_key: "web_search",
          description: "在线检索网络信息",
          graph_ids: ["graph-chat"],
          source: "builtin",
        },
        {
          name: "Bash终端",
          tool_key: "bash_exec",
          description: "执行服务器指令",
          graph_ids: ["graph-chat"],
          source: "builtin",
        },
      ],
    });

    mockListToolRestrictions.mockResolvedValue({
      items: [
        {
          id: "res-1",
          graph_id: "graph-chat",
          subject_type: "project",
          subject_id: "proj-1",
          tool_name: "bash_exec",
          reason: "安全审计策略：生产环境禁止执行任意命令",
          created_by: "admin",
          created_at: "2026-09-20T12:00:00Z",
        },
      ],
    });
  });

  it("renders both enabled and disabled tools with check/x icons and statistics", async () => {
    const wrapper = mount(AgentEditorPage, {
      global: {
        stubs: {
          BaseButton: {
            props: ["disabled"],
            template: '<button :disabled="disabled"><slot /></button>',
          },
          BaseIcon: {
            props: ["name"],
            template: '<span class="icon" :data-icon="name" />',
          },
          BaseSelect: true,
          PageHeader: { template: '<header><slot name="actions" /></header>' },
          StateBanner: true,
          StatusPill: true,
          SurfaceCard: { template: "<section><slot /></section>" },
        },
      },
    });

    await flushPromises();

    const text = wrapper.text();
    // 统计显示
    expect(text).toContain("共 2 项工具");
    expect(text).toContain("1 可用");
    expect(text).toContain("1 已禁用");

    // 工具列表渲染
    expect(text).toContain("Web搜索");
    expect(text).toContain("web_search");
    expect(text).toContain("Bash终端");
    expect(text).toContain("bash_exec");

    // 禁用工具详情
    expect(text).toContain("项目禁用");
    expect(text).toContain("原因：安全审计策略：生产环境禁止执行任意命令");

    // 验证图标：可用工具为 check，禁用工具为 x
    const checkIcons = wrapper.findAll('[data-icon="check"]');
    const xIcons = wrapper.findAll('[data-icon="x"]');
    expect(checkIcons.length).toBeGreaterThan(0);
    expect(xIcons.length).toBe(1);
  });
});

describe("AgentEditorPage - Model Resilience Settings", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    mockGetAgent.mockResolvedValue({
      id: "agent-1",
      name: "测试智能体",
      description: "老王的测试Agent",
      graph_id: "graph-chat",
      status: "active",
      context: { model_id: "model-primary" },
      model_resilience: {
        enabled: true,
        fallback_model_id: "model-fallback",
        max_attempts: 3,
        attempt_timeout_seconds: 600,
        total_timeout_seconds: 900,
      },
    });

    mockListGraphsPage.mockResolvedValue({
      items: [{ graph_id: "graph-chat", display_name: "Chat Graph" }],
    });

    mockListRuntimeModels.mockResolvedValue({
      models: [
        { id: "model-primary", display_name: "Primary Model", enabled: true },
        { id: "model-fallback", display_name: "Fallback Model", enabled: true },
        { id: "model-disabled", display_name: "Disabled Model", enabled: true },
      ],
    });

    mockListRuntimeModelPolicies.mockResolvedValue({
      items: [
        { catalog_id: "model-primary", policy: { is_enabled: true } },
        { catalog_id: "model-fallback", policy: { is_enabled: true } },
        { catalog_id: "model-disabled", policy: { is_enabled: false } },
      ],
    });

    mockListRuntimeTools.mockResolvedValue({ tools: [] });
    mockListToolRestrictions.mockResolvedValue({ items: [] });

    mockGetAgentParameterSchema.mockResolvedValue({
      sections: [
        {
          key: "model_resilience",
          type: "object",
          supported: true,
          default: {
            enabled: false,
            fallback_model_id: null,
            max_attempts: 3,
            attempt_timeout_seconds: 600,
            total_timeout_seconds: 900,
          },
        },
      ],
    });

    mockUpdateAgent.mockResolvedValue({
      id: "agent-1",
      name: "测试智能体",
      description: "老王的测试Agent",
      graph_id: "graph-chat",
      status: "active",
      context: { model_id: "model-primary" },
      model_resilience: null,
    });
  });

  it("renders resilience section and correctly reflects enabled status and inspector summary", async () => {
    const wrapper = mount(AgentEditorPage, {
      global: {
        stubs: {
          BaseButton: {
            props: ["disabled"],
            template: '<button :disabled="disabled"><slot /></button>',
          },
          BaseIcon: {
            props: ["name"],
            template: '<span class="icon" :data-icon="name" />',
          },
          BaseSelect: true,
          PageHeader: { template: '<header><slot name="actions" /></header>' },
          StateBanner: true,
          StatusPill: true,
          SurfaceCard: { template: "<section><slot /></section>" },
        },
      },
    });

    await flushPromises();

    const text = wrapper.text();
    expect(text).toContain("模型恢复策略 (Model Resilience)");
    expect(text).toContain("已启用 · 最多 3 次 (总预算 900s)");
  });

  it("submits null model_resilience when user disables an active resilience policy", async () => {
    const wrapper = mount(AgentEditorPage, {
      global: {
        stubs: {
          BaseButton: {
            props: ["disabled"],
            template: '<button :disabled="disabled"><slot /></button>',
          },
          BaseIcon: true,
          BaseSelect: true,
          PageHeader: true,
          StateBanner: true,
          StatusPill: true,
          SurfaceCard: { template: "<section><slot /></section>" },
        },
      },
    });

    await flushPromises();

    // 找到 checkbox 并关闭
    const checkbox = wrapper.find('input[type="checkbox"]');
    expect(checkbox.exists()).toBe(true);
    await checkbox.setValue(false);

    // 触发保存表单
    const form = wrapper.find("form");
    await form.trigger("submit");
    await flushPromises();

    expect(mockUpdateAgent).toHaveBeenCalledWith(
      "proj-1",
      "agent-1",
      expect.objectContaining({
        model_resilience: null,
      }),
    );
  });
});

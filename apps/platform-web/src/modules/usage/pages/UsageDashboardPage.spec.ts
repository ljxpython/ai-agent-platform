import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import UsageDashboardPage from "./UsageDashboardPage.vue";

// Mock vue-router
const mockRouterReplace = vi.fn();
vi.mock("vue-router", () => ({
  useRoute: () => ({
    params: { projectId: "test-project-123" },
    query: {},
  }),
  useRouter: () => ({
    push: vi.fn(),
    replace: mockRouterReplace,
  }),
}));

// Mock echarts
vi.mock("echarts/core", () => ({
  use: vi.fn(),
  init: vi.fn(() => ({
    setOption: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
    clear: vi.fn(),
    on: vi.fn(),
  })),
  graphic: {
    LinearGradient: vi.fn(),
  },
}));

// Mock composables
vi.mock("../composables/useUsageDashboard", () => ({
  useUsageDashboard: () => ({
    data: { value: null },
    loading: { value: false },
    isRefreshing: { value: false },
    error: { value: null },
    refresh: vi.fn(),
  }),
}));

vi.mock("../composables/useUsageRuns", () => ({
  useUsageRuns: () => ({
    runs: { value: [] },
    total: { value: 0 },
    loading: { value: false },
    error: { value: null },
    hasMore: { value: false },
    loadFirstPage: vi.fn(),
    loadNextPage: vi.fn(),
  }),
}));

vi.mock("../composables/useGatewaySeries", () => ({
  useGatewaySeries: () => ({
    series: { value: null },
    loading: { value: false },
    isRefreshing: { value: false },
    error: { value: null },
    refresh: vi.fn(),
  }),
}));

const commonStubs = {
  GatewayUsageTab: true,
  GatewayLogsTable: true,
  GatewayBudgetsTab: true,
  UsageFilterToolbar: true,
  UsageTrend: true,
  UsageBreakdown: true,
  BaseDrawer: true,
  BaseIcon: true,
  RunUsage: true,
};

describe("UsageDashboardPage Integration", () => {
  beforeEach(() => {
    const pinia = createPinia();
    setActivePinia(pinia);
    mockRouterReplace.mockClear();
  });

  it("renders default gateway tab and switches tabs correctly", async () => {
    const wrapper = mount(UsageDashboardPage, {
      global: {
        stubs: {
          ...commonStubs,
          GatewayUsageTab: {
            template:
              "<div class=\"stub-gateway-usage-tab\" @click=\"$emit('drilldown-to-logs', { from: '2026-11-17T12:00:00Z', to: '2026-11-17T12:05:00Z', point: {} })\">GatewayTab</div>",
            emits: ["drilldown-to-logs"],
          },
          GatewayLogsTable: {
            template: '<div class="stub-gateway-logs-table">LogsTable</div>',
            props: ["drilldownRange"],
          },
        },
      },
    });

    const gatewayPane = wrapper.find('[data-testid="tab-pane-gateway"]');
    const logsPane = wrapper.find('[data-testid="tab-pane-logs"]');
    const budgetsPane = wrapper.find('[data-testid="tab-pane-budgets"]');

    // 默认展示网关使用 (gateway) Tab
    expect(wrapper.vm.activeTab).toBe("gateway");
    expect(gatewayPane.attributes("style") || "").not.toContain(
      "display: none",
    );
    expect(logsPane.attributes("style")).toContain("display: none");
    expect(budgetsPane.attributes("style")).toContain("display: none");

    // 寻找 Tab 按钮并切换到 Logs
    const logsTabBtn = wrapper.find('[data-testid="tab-btn-logs"]');
    expect(logsTabBtn.exists()).toBe(true);
    await logsTabBtn.trigger("click");
    await flushPromises();

    expect(wrapper.vm.activeTab).toBe("logs");
    expect(mockRouterReplace).toHaveBeenCalledWith({
      query: { tab: "logs" },
    });

    // 此时 GatewayLogsTable 应当显示，GatewayTab 隐藏
    expect(
      wrapper.find('[data-testid="tab-pane-gateway"]').attributes("style"),
    ).toContain("display: none");
    expect(
      wrapper.find('[data-testid="tab-pane-logs"]').attributes("style") || "",
    ).not.toContain("display: none");

    // 切换到 budgets tab
    const budgetsTabBtn = wrapper.find('[data-testid="tab-btn-budgets"]');
    expect(budgetsTabBtn.exists()).toBe(true);
    await budgetsTabBtn.trigger("click");
    await flushPromises();

    expect(wrapper.vm.activeTab).toBe("budgets");
    expect(mockRouterReplace).toHaveBeenCalledWith({
      query: { tab: "budgets" },
    });
    expect(
      wrapper.find('[data-testid="tab-pane-budgets"]').attributes("style") ||
        "",
    ).not.toContain("display: none");
    expect(
      wrapper.find('[data-testid="tab-pane-logs"]').attributes("style"),
    ).toContain("display: none");
  });

  it("switches to logs tab and sets drilldown range when drilldown-to-logs is emitted", async () => {
    const wrapper = mount(UsageDashboardPage, {
      global: {
        stubs: {
          ...commonStubs,
          GatewayUsageTab: {
            template:
              "<div class=\"stub-gateway-usage-tab\" @click=\"$emit('drilldown-to-logs', { from: '2026-11-17T12:00:00Z', to: '2026-11-17T12:05:00Z', point: {} })\">GatewayTab</div>",
            emits: ["drilldown-to-logs"],
          },
          GatewayLogsTable: {
            template: '<div class="stub-gateway-logs-table"><slot /></div>',
            props: ["drilldownRange", "activeFilterRange"],
          },
        },
      },
    });

    // 点击 gateway stub 触发下钻事件
    const gatewayStub = wrapper.find(".stub-gateway-usage-tab");
    await gatewayStub.trigger("click");

    // 自动激活 logs tab
    await flushPromises();
    expect(wrapper.vm.activeTab).toBe("logs");
    expect(
      wrapper.find('[data-testid="tab-pane-gateway"]').attributes("style"),
    ).toContain("display: none");
    expect(
      wrapper.find('[data-testid="tab-pane-logs"]').attributes("style") || "",
    ).not.toContain("display: none");
  });

  it("renders scope switch and toggles between project and platform when authorized", async () => {
    const authStore = (await import("@/stores/auth")).useAuthStore();
    authStore.user = {
      id: "admin-1",
      username: "admin",
      status: "active",
      permissions: ["platform.usage.read", "project.usage.read"],
    } as any;

    const wrapper = mount(UsageDashboardPage, {
      global: {
        stubs: commonStubs,
      },
    });

    // 默认通过 projectId 进入，初始为 project 作用域
    expect(wrapper.vm.selectedScopeMode).toBe("project");

    // 切换到 platform 全局作用域
    wrapper.vm.handleSetScopeMode("platform");
    await flushPromises();

    expect(wrapper.vm.selectedScopeMode).toBe("platform");
    expect(mockRouterReplace).toHaveBeenCalledWith({
      query: { scope: "platform" },
    });
  });
});

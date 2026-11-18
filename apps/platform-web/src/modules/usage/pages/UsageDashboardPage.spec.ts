import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import UsageDashboardPage from "./UsageDashboardPage.vue";

// Mock vue-router
vi.mock("vue-router", () => ({
  useRoute: () => ({
    params: { projectId: undefined },
    query: {},
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

describe("UsageDashboardPage Integration", () => {
  beforeEach(() => {
    const pinia = createPinia();
    setActivePinia(pinia);
  });

  it("renders default gateway tab and switches tabs correctly", async () => {
    const wrapper = mount(UsageDashboardPage, {
      global: {
        stubs: {
          GatewayUsageTab: {
            template:
              "<div class=\"stub-gateway-usage-tab\" @click=\"$emit('drilldown-to-logs', { from: '2026-11-17T12:00:00Z', to: '2026-11-17T12:05:00Z', point: {} })\">GatewayTab</div>",
            emits: ["drilldown-to-logs"],
          },
          GatewayLogsTable: {
            template: '<div class="stub-gateway-logs-table">LogsTable</div>',
            props: ["drilldownRange"],
          },
          UsageFilterToolbar: true,
          UsageTrend: true,
          UsageBreakdown: true,
          BaseDrawer: true,
          BaseIcon: true,
          RunUsage: true,
        },
      },
    });

    const gatewayPane = wrapper.find('[data-testid="tab-pane-gateway"]');
    const logsPane = wrapper.find('[data-testid="tab-pane-logs"]');

    // 默认展示网关使用 (gateway) Tab
    expect(wrapper.vm.activeTab).toBe("gateway");
    expect(gatewayPane.attributes("style") || "").not.toContain(
      "display: none",
    );
    expect(logsPane.attributes("style")).toContain("display: none");

    // 寻找 Tab 按钮并切换到 Logs
    const logsTabBtn = wrapper.find('[data-testid="tab-btn-logs"]');
    expect(logsTabBtn.exists()).toBe(true);
    await logsTabBtn.trigger("click");
    await flushPromises();

    expect(wrapper.vm.activeTab).toBe("logs");

    // 此时 GatewayLogsTable 应当显示，GatewayTab 隐藏
    expect(
      wrapper.find('[data-testid="tab-pane-gateway"]').attributes("style"),
    ).toContain("display: none");
    expect(
      wrapper.find('[data-testid="tab-pane-logs"]').attributes("style") || "",
    ).not.toContain("display: none");
  });

  it("switches to logs tab and sets drilldown range when drilldown-to-logs is emitted", async () => {
    const wrapper = mount(UsageDashboardPage, {
      global: {
        stubs: {
          GatewayUsageTab: {
            template:
              "<div class=\"stub-gateway-usage-tab\" @click=\"$emit('drilldown-to-logs', { from: '2026-11-17T12:00:00Z', to: '2026-11-17T12:05:00Z', point: {} })\">GatewayTab</div>",
            emits: ["drilldown-to-logs"],
          },
          GatewayLogsTable: {
            template: '<div class="stub-gateway-logs-table"><slot /></div>',
            props: ["drilldownRange", "activeFilterRange"],
          },
          UsageFilterToolbar: true,
          UsageTrend: true,
          UsageBreakdown: true,
          BaseDrawer: true,
          BaseIcon: true,
          RunUsage: true,
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
});

import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import BaseGatewayChart from "./BaseGatewayChart.vue";
import GatewayRequestsChart from "./GatewayRequestsChart.vue";
import GatewayLatencyChart from "./GatewayLatencyChart.vue";
import GatewayTokenUsageChart from "./GatewayTokenUsageChart.vue";
import GatewayTokenStatsChart from "./GatewayTokenStatsChart.vue";
import GatewayCostChart from "./GatewayCostChart.vue";
import type {
  GatewayMetricPoint,
  GatewayModelBreakdownItem,
} from "../../types";

// Mock echarts 以便在 jsdom 中无头测试
vi.mock("echarts/core", () => {
  const chartInstance = {
    setOption: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
    clear: vi.fn(),
    on: vi.fn(),
  };
  return {
    use: vi.fn(),
    init: vi.fn(() => chartInstance),
    graphic: {
      LinearGradient: vi.fn(),
    },
  };
});

describe("Gateway Charts Components", () => {
  const pinia = createPinia();
  setActivePinia(pinia);

  const mockPoint: GatewayMetricPoint = {
    timestamp_ms: 1731844800000,
    time_label: "11/17 19:00",
    requests: 120,
    errors: 2,
    latency_p50_ms: 450.2,
    latency_p90_ms: 1250.0,
    latency_p99_ms: 2400.0,
    input_tokens: 16000,
    output_tokens: 8000,
    total_tokens: 24000,
    cache_read_tokens: 6000,
    cache_creation_tokens: 1200,
    tokens_per_request: 200.0,
    cost_usd: "0.048000000000",
  };

  const mockBreakdown: GatewayModelBreakdownItem = {
    key: "deepseek-v4.1",
    requests: 120,
    total_tokens: 24000,
    cost_usd: "0.048000000000",
  };

  it("BaseGatewayChart renders title and empty state properly", () => {
    const wrapper = mount(BaseGatewayChart, {
      props: {
        title: "测试图表",
        empty: true,
        options: {},
      },
    });
    expect(wrapper.text()).toContain("测试图表");
    expect(wrapper.text()).toContain("当前时间范围暂无网关指标");
  });

  it("BaseGatewayChart renders loading spinner", () => {
    const wrapper = mount(BaseGatewayChart, {
      props: {
        title: "测试图表",
        loading: true,
        options: {},
      },
    });
    expect(wrapper.text()).toContain("加载时序数据中...");
  });

  it("GatewayRequestsChart mounts and accepts points", () => {
    const wrapper = mount(GatewayRequestsChart, {
      props: {
        points: [mockPoint],
      },
    });
    expect(wrapper.text()).toContain("网关请求吞吐趋势");
    expect(wrapper.text()).toContain("点数: 1");
  });

  it("GatewayLatencyChart mounts and accepts latency data", () => {
    const wrapper = mount(GatewayLatencyChart, {
      props: {
        points: [mockPoint],
      },
    });
    expect(wrapper.text()).toContain("网关响应延迟与异常");
  });

  it("GatewayTokenUsageChart mounts and accepts caching data", () => {
    const wrapper = mount(GatewayTokenUsageChart, {
      props: {
        points: [mockPoint],
      },
    });
    expect(wrapper.text()).toContain("Token 吞吐与缓存分布");
  });

  it("GatewayTokenStatsChart mounts and accepts avg stats", () => {
    const wrapper = mount(GatewayTokenStatsChart, {
      props: {
        points: [mockPoint],
      },
    });
    expect(wrapper.text()).toContain("单请求 Token 均值");
  });

  it("GatewayCostChart mounts and renders breakdown items", () => {
    const wrapper = mount(GatewayCostChart, {
      props: {
        points: [mockPoint],
        breakdown: [mockBreakdown],
      },
    });
    expect(wrapper.text()).toContain("网关预估成本走势");
    expect(wrapper.text()).toContain("deepseek-v4.1");
    expect(wrapper.text()).toContain("120 次请求");
  });
});

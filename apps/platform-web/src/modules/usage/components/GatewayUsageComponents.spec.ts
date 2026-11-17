import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import GatewaySummaryCards from "./GatewaySummaryCards.vue";
import GatewayFilterToolbar from "./GatewayFilterToolbar.vue";
import type { GatewaySummary } from "../types";

// Mock echarts 以便组件挂载不报错
vi.mock("echarts/core", () => {
  return {
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
  };
});

describe("Gateway Dashboard Components", () => {
  const pinia = createPinia();
  setActivePinia(pinia);

  const mockSummary: GatewaySummary = {
    total_requests: 12450,
    total_errors: 32,
    error_rate: 0.00257,
    total_tokens: 4200000,
    total_input_tokens: 3000000,
    total_output_tokens: 1200000,
    total_cache_read_tokens: 1150000,
    total_cache_creation_tokens: 250000,
    cache_hit_ratio: 0.3833,
    avg_tokens_per_request: 337.3,
    p90_latency_ms: 1240.0,
    total_cost_usd: "14.280000000000",
  };

  it("GatewaySummaryCards renders 4 metric cards correctly", () => {
    const wrapper = mount(GatewaySummaryCards, {
      props: {
        summary: mockSummary,
        loading: false,
      },
    });
    expect(wrapper.text()).toContain("12,450");
    expect(wrapper.text()).toContain("异常率 0.26%");
    expect(wrapper.text()).toContain("1240");
    expect(wrapper.text()).toContain("4.20 M");
    expect(wrapper.text()).toContain("Prompt Caching 命中: 38.3%");
    expect(wrapper.text()).toContain("$14.2800");
  });

  it("GatewayFilterToolbar renders preset pills and responds to click", async () => {
    const wrapper = mount(GatewayFilterToolbar, {
      props: {
        preset: "24h",
        bucketSeconds: 300,
        status: "all",
        refreshInterval: 0,
      },
    });

    const buttons = wrapper.findAll("button");
    expect(buttons.length).toBeGreaterThanOrEqual(5);

    // 点击 1小时 预设按钮
    const oneHourBtn = buttons.find((b) => b.text().includes("1小时"));
    expect(oneHourBtn).toBeDefined();
    await oneHourBtn?.trigger("click");

    expect(wrapper.emitted("update:preset")).toBeTruthy();
    expect(wrapper.emitted("update:preset")?.[0]).toEqual(["1h"]);
    expect(wrapper.emitted("update:bucketSeconds")?.[0]).toEqual([60]);
  });
});

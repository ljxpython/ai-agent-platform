import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount } from "@vue/test-utils";
import RunUsage from "./RunUsage.vue";
import * as usageService from "@/services/threads/usage.service";
import usageFixtures from "../../../../../../../docs/projects/20261007-agent-usage-cost-governance/fixtures/usage-v1.json";

describe("RunUsage.vue", () => {
  const runSample = (usageFixtures as any).samples.run_complete_page1;
  const threadSample = (usageFixtures as any).samples.thread_complete;

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(usageService, "getRunUsage").mockResolvedValue(runSample);
    vi.spyOn(usageService, "getThreadUsage").mockResolvedValue(threadSample);
  });

  it("挂载后正确渲染 Run 成本与 Token 消耗明细", async () => {
    const wrapper = mount(RunUsage, {
      props: {
        threadId: runSample.thread_id,
        runId: runSample.run_id,
      },
    });

    await vi.waitFor(() => {
      expect(wrapper.text()).toContain("用量与成本分析");
      expect(wrapper.text()).toContain("总 Tokens:");
      expect(wrapper.text()).toContain("2,200"); // 1000 + 1200 or sample total
      expect(wrapper.text()).toContain("会话累计已采集汇总");
    });
  });

  it("点击刷新按钮触发刷新", async () => {
    const wrapper = mount(RunUsage, {
      props: {
        threadId: runSample.thread_id,
        runId: runSample.run_id,
      },
    });

    await vi.waitFor(() => {
      expect(wrapper.find('[data-testid="refresh-usage-btn"]').exists()).toBe(
        true,
      );
    });

    const refreshBtn = wrapper.find('[data-testid="refresh-usage-btn"]');
    await refreshBtn.trigger("click");

    expect(usageService.getRunUsage).toHaveBeenCalled();
  });

  it("点击关闭按钮触发 close emit", async () => {
    const wrapper = mount(RunUsage, {
      props: {
        threadId: runSample.thread_id,
        runId: runSample.run_id,
      },
    });

    await vi.waitFor(() => {
      expect(wrapper.find('[data-testid="close-usage-btn"]').exists()).toBe(
        true,
      );
    });

    await wrapper.find('[data-testid="close-usage-btn"]').trigger("click");
    expect(wrapper.emitted("close")).toBeTruthy();
  });

  it("当数据存在服务端截断时，展示截断警告条", async () => {
    const truncatedRun = {
      ...runSample,
      truncated: true,
    };
    vi.mocked(usageService.getRunUsage).mockResolvedValueOnce(truncatedRun);

    const wrapper = mount(RunUsage, {
      props: {
        threadId: runSample.thread_id,
        runId: runSample.run_id,
      },
    });

    await vi.waitFor(() => {
      expect(
        wrapper.find('[data-testid="usage-truncated-alert"]').exists(),
      ).toBe(true);
      expect(wrapper.text()).toContain("用量数据已受限截断");
    });
  });

  it("正确渲染 open-swe 风格的水位仪表与调用明细", async () => {
    const wrapper = mount(RunUsage, {
      props: {
        threadId: runSample.thread_id,
        runId: runSample.run_id,
      },
    });

    await vi.waitFor(() => {
      expect(wrapper.find('[data-testid="context-meter-card"]').exists()).toBe(
        true,
      );
      expect(wrapper.text()).toContain("运行水位 (Usage Meter)");
      expect(wrapper.findAll('[data-testid="usage-call-item"]').length).toBe(
        runSample.calls.items.length,
      );
    });
  });

  it("当采集处于 disabled 状态时展示'采集已关闭'，不误导为未配置价格", async () => {
    const disabledSample = (usageFixtures as any).samples.run_disabled;
    vi.mocked(usageService.getRunUsage).mockResolvedValueOnce(disabledSample);

    const wrapper = mount(RunUsage, {
      props: {
        threadId: disabledSample.thread_id,
        runId: disabledSample.run_id,
      },
    });

    await vi.waitFor(() => {
      expect(wrapper.text()).toContain("采集已关闭");
    });
  });
});

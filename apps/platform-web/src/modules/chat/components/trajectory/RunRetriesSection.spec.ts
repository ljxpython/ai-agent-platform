import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import RunRetriesSection from "./RunRetriesSection.vue";
import type { RetrySummaryItem } from "../../diagnostics/types";

describe("RunRetriesSection.vue", () => {
  const mockRetries: RetrySummaryItem[] = [
    {
      observation_id: "retry-1",
      scope: "primary",
      namespace: ["model_root"],
      unit: "model",
      role: null,
      attempts: 2,
      outcome: "success",
      code: "provider_rate_limited",
      duration_ms: 1200,
    },
    {
      observation_id: "retry-2",
      scope: "primary",
      namespace: ["task_root"],
      unit: "task",
      role: "researcher",
      attempts: 1,
      outcome: "failed",
      code: "provider_timeout",
      duration_ms: 500,
    },
  ];

  it("空数组时不渲染任何内容", () => {
    const wrapper = mount(RunRetriesSection, {
      props: {
        retries: [],
        runStatus: "success",
      },
    });

    expect(wrapper.find('[data-testid="run-retries-section"]').exists()).toBe(
      false,
    );
    expect(wrapper.html()).toBe("<!--v-if-->");
  });

  it("正常渲染标题、角色、尝试次数与错误码", () => {
    const wrapper = mount(RunRetriesSection, {
      props: {
        retries: mockRetries,
        runStatus: "success",
      },
    });

    expect(wrapper.text()).toContain("调用尝试与重试");
    expect(wrapper.text()).toContain("模型调用");
    expect(wrapper.text()).toContain("重试 1 次");
    expect(wrapper.text()).toContain("子任务 (researcher)");
    expect(wrapper.text()).toContain("单次调用");
    expect(wrapper.text()).toContain("模型服务限流");
    expect(wrapper.text()).toContain("模型调用超时");
  });

  it("核心视觉防坑：当 runStatus 为 success 时，失败调用降级为 Amber 琥珀色样式，不显示致命红框", () => {
    const wrapper = mount(RunRetriesSection, {
      props: {
        retries: mockRetries,
        runStatus: "success",
      },
    });

    expect(wrapper.text()).toContain("已通过重试或备选路径完成");
    // 不应有致命红框
    expect(wrapper.find(".border-red-200").exists()).toBe(false);
    // 应有琥珀色警示框
    expect(wrapper.find(".border-amber-200").exists()).toBe(true);
  });

  it("当 runStatus 为 error 时，失败调用以 error (红框) 呈现", () => {
    const wrapper = mount(RunRetriesSection, {
      props: {
        retries: mockRetries,
        runStatus: "error",
      },
    });

    // 此时应出现致命红框
    expect(wrapper.find(".border-red-200").exists()).toBe(true);
  });
});

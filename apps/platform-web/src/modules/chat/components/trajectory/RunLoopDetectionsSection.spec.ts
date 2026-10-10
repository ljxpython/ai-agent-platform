import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import RunLoopDetectionsSection from "./RunLoopDetectionsSection.vue";
import type { LoopDetectionItem } from "../../diagnostics/types";

describe("RunLoopDetectionsSection", () => {
  it("does not render when loopDetections is empty", () => {
    const wrapper = mount(RunLoopDetectionsSection, {
      props: {
        loopDetections: [],
      },
    });

    expect(wrapper.find("div").exists()).toBe(false);
  });

  it("renders loop detection approaching and reached items with correct styling", () => {
    const loopDetections: LoopDetectionItem[] = [
      {
        observation_id: "obs-1",
        scope: "primary",
        namespace: [],
        code: "tool_loop_approaching",
        repetitions: 3,
        threshold: 3,
      },
      {
        observation_id: "obs-2",
        scope: "subagent",
        namespace: ["researcher"],
        code: "tool_loop_reached",
        repetitions: 5,
        threshold: 5,
      },
    ];

    const wrapper = mount(RunLoopDetectionsSection, {
      props: {
        loopDetections,
      },
    });

    expect(wrapper.text()).toContain("循环保护记录");
    expect(wrapper.text()).toContain("共 2 条");
    expect(wrapper.text()).toContain("检测到重复工具调用，已提醒收尾");
    expect(wrapper.text()).toContain("达到重复工具调用上限，已停止运行");
    expect(wrapper.text()).toContain("子任务");
    expect(wrapper.text()).toContain("Namespace: researcher");
  });
});

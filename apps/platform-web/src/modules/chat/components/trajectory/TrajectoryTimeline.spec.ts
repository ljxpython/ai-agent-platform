import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import TrajectoryTimeline from "./TrajectoryTimeline.vue";
import type { TrajectoryRecord } from "../../trajectory/types";

describe("TrajectoryTimeline component", () => {
  it("空 records 时正常渲染轨道标签", () => {
    const wrapper = mount(TrajectoryTimeline, {
      props: {
        records: [],
        selectedRecordId: null,
      },
    });

    expect(wrapper.text()).toContain("Input");
    expect(wrapper.text()).toContain("Model");
    expect(wrapper.text()).toContain("Tools");
    expect(wrapper.findAll(".cursor-pointer").length).toBe(0);
  });

  it("渲染多通道色块并响应点击选中", async () => {
    const records: TrajectoryRecord[] = [
      {
        id: "rec-system",
        turnIndex: 1,
        stepIndex: 1,
        kind: "system",
        name: "系统提示",
        summary: "System prompt",
        status: "completed",
      },
      {
        id: "rec-user",
        turnIndex: 1,
        stepIndex: 2,
        kind: "user",
        name: "用户提问",
        summary: "hello",
        status: "completed",
      },
      {
        id: "rec-assistant",
        turnIndex: 1,
        stepIndex: 3,
        kind: "assistant",
        name: "AI 回复",
        summary: "world",
        status: "completed",
      },
      {
        id: "rec-tool",
        turnIndex: 1,
        stepIndex: 4,
        kind: "tool",
        name: "web_search",
        summary: "web_search()",
        status: "completed",
      },
    ];

    const wrapper = mount(TrajectoryTimeline, {
      props: {
        records,
        selectedRecordId: "rec-user",
      },
    });

    const spans = wrapper.findAll(".cursor-pointer");
    expect(spans.length).toBe(4);

    // 点击 tool 色块触发 select 事件
    const toolSpan = spans[3]!;
    await toolSpan.trigger("click");

    expect(wrapper.emitted("select")).toBeTruthy();
    expect(wrapper.emitted("select")![0]![0]).toEqual(records[3]);
  });
});

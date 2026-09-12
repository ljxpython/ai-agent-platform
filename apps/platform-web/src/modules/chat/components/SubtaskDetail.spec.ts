import { shallowRef } from "vue";
import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { AIMessage, HumanMessage } from "@langchain/core/messages";
import type { AnyStream } from "@langchain/vue";

// Mock @langchain/vue to return scoped messages and tools
vi.mock("@langchain/vue", () => ({
  useTranscriptMessages: (_stream: unknown, _namespace: unknown) => shallowRef([]),
  useToolCalls: (_stream: unknown, _target: unknown) => shallowRef([]),
}));

// Mock useTranscriptMessages composable
vi.mock("../composables/useTranscriptMessages", () => ({
  useTranscriptMessages: (_stream: { messagesMock?: unknown }, _namespace: unknown) =>
    _stream?.messagesMock ?? shallowRef([]),
}));

import SubtaskDetail from "./SubtaskDetail.vue";

describe("SubtaskDetail.vue", () => {
  it("renders delegated prompt with agent label and NEVER displays '你'", () => {
    const directiveMsg = new HumanMessage({
      id: "delegated-directive-1",
      content: "对 /workspace/report.py 做只读分析，请勿修改或执行任何代码",
    });

    const stream = {
      messagesMock: shallowRef([directiveMsg]),
      values: shallowRef({ messages: [] }),
      isLoading: shallowRef(false),
      subgraphs: shallowRef(new Map()),
      subagents: shallowRef(new Map()),
    };

    const wrapper = mount(SubtaskDetail, {
      props: {
        stream: stream as unknown as AnyStream,
        namespace: ["tools:subagent-1"],
        running: false,
      },
      global: {
        stubs: {
          BaseIcon: true,
          MessageContent: {
            props: ["blocks"],
            template: "<div class='directive-content'>{{ blocks.map(b => b.text).join('') }}</div>",
          },
          ToolResult: true,
        },
      },
    });

    // Verify it labels it as parent agent delegation
    expect(wrapper.text()).toContain("主智能体指派任务");
    expect(wrapper.text()).toContain("对 /workspace/report.py 做只读分析，请勿修改或执行任何代码");
    // Verify it NEVER displays "你"
    expect(wrapper.text()).not.toContain("你");
  });

  it("renders subagent internal tools neatly inside the subtask component", () => {
    const toolCallMsg = new AIMessage({
      id: "sub-ai-call",
      content: "",
      tool_calls: [
        { name: "ls", args: { path: "/workspace" }, id: "call-ls" },
        { name: "read_file", args: { path: "/workspace/report.py" }, id: "call-read" },
      ],
    });

    const stream = {
      messagesMock: shallowRef([toolCallMsg]),
      values: shallowRef({ messages: [] }),
      isLoading: shallowRef(false),
      subgraphs: shallowRef(new Map()),
      subagents: shallowRef(new Map()),
    };

    const wrapper = mount(SubtaskDetail, {
      props: {
        stream: stream as unknown as AnyStream,
        namespace: ["tools:subagent-1"],
        running: false,
      },
      global: {
        stubs: {
          BaseIcon: true,
          MessageContent: true,
          ToolResult: {
            props: ["tool"],
            template: "<div class='mock-sub-tool'>{{ tool.name }} {{ tool.input ? JSON.stringify(tool.input) : '' }}</div>",
          },
        },
      },
    });

    expect(wrapper.text()).toContain("执行步骤（2 项操作）");
    const renderedTools = wrapper.findAll(".mock-sub-tool");
    expect(renderedTools.length).toBe(2);
    expect(renderedTools[0].text()).toContain("ls");
    expect(renderedTools[1].text()).toContain("read_file");
  });
});

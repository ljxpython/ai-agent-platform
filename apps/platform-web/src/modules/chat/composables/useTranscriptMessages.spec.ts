import { effectScope, shallowRef } from "vue";
import { AIMessage, HumanMessage } from "@langchain/core/messages";
import type { AnyStream } from "@langchain/vue";
import { expect, it, vi } from "vitest";

type Event = { method: string; params: { namespace: string[]; data: Record<string, unknown> } };
const hooks = vi.hoisted(() => ({ onEvent: (_event: Event) => {} }));
vi.mock("@langchain/vue", () => ({
  useMessages: (stream: { messages: unknown }) => stream.messages,
  useChannelEffect: (_stream: unknown, _channels: unknown, options: { onEvent: typeof hooks.onEvent }) => { hooks.onEvent = options.onEvent; },
}));
import { useTranscriptMessages } from "./useTranscriptMessages";

it("shows child results explicitly promoted to root values, without leaking other child messages", () => {
  const human = new HumanMessage({ id: "u", content: "question" });
  const stream = {
    messages: shallowRef([human, new AIMessage({ id: "reply", content: "fin" }), new AIMessage({ id: "private", content: "PRIVATE" })]),
    values: shallowRef({ messages: [human] }), isLoading: shallowRef(false),
    subgraphs: shallowRef(new Map([["child", { namespace: ["respond:child"] }]])), subagents: shallowRef(new Map()),
  };
  const scope = effectScope();
  try {
    const messages = scope.run(() => useTranscriptMessages(stream as unknown as AnyStream))!;
    for (const id of ["reply", "private"]) hooks.onEvent({ method: "messages", params: { namespace: ["respond:child"], data: { event: "message-start", id } } });
    hooks.onEvent({ method: "values", params: { namespace: [], data: { messages: [human] } } });
    expect(messages.value.map(message => message.id)).toEqual(["u"]);
    stream.values.value = { messages: [human, new AIMessage({ id: "reply", content: "final answer" })] };
    expect(messages.value.map(message => message.id)).toEqual(["u"]);
    hooks.onEvent({ method: "values", params: { namespace: [], data: { messages: [human, { type: "ai", id: "reply", content: "final answer" }] } } });
    expect(messages.value.map(message => message.content)).toEqual(["question", "final answer"]);
  } finally { scope.stop(); }
});

it("uses exact-scope final values when late replay leaves a partial message", () => {
  const stream = {
    messages: shallowRef([new AIMessage({ id: "left", content: "LEFT" })]),
    values: shallowRef({ messages: [] }), isLoading: shallowRef(false),
    subgraphs: shallowRef(new Map()), subagents: shallowRef(new Map()),
  };
  const scope = effectScope();
  try {
    const messages = scope.run(() => useTranscriptMessages(stream as unknown as AnyStream, ["left:1"]))!;
    hooks.onEvent({ method: "values", params: { namespace: ["left:1"], data: { messages: [{ type: "ai", id: "left", content: "LEFT_PRIVATE complete" }] } } });
    hooks.onEvent({ method: "values", params: { namespace: ["left:1", "nested:2"], data: { messages: [{ type: "ai", id: "child", content: "CHILD_PRIVATE" }] } } });
    expect(messages.value.map(message => message.content)).toEqual(["LEFT_PRIVATE complete"]);
  } finally { scope.stop(); }
});

it("preserves tool calls and tool messages from execution subgraphs", () => {
  const toolCallMsg = new AIMessage({
    id: "tool-call-1",
    content: "",
    tool_calls: [{ name: "read_reference", args: { topic: "test" }, id: "call-1" }],
  });
  const stream = {
    messages: shallowRef([toolCallMsg]),
    values: shallowRef({ messages: [] }),
    isLoading: shallowRef(true),
    subgraphs: shallowRef(new Map([["child", { namespace: ["respond:child"] }]])),
    subagents: shallowRef(new Map()),
  };
  const scope = effectScope();
  try {
    const messages = scope.run(() => useTranscriptMessages(stream as unknown as AnyStream))!;
    hooks.onEvent({
      method: "messages",
      params: { namespace: ["respond:child"], data: { event: "message-start", id: "tool-call-1" } },
    });
    expect(messages.value.map((m) => m.id)).toEqual(["tool-call-1"]);
  } finally {
    scope.stop();
  }
});

it("filters out subagent delegated task description HumanMessage from root transcript", () => {
  const userMsg = new HumanMessage({ id: "user-root", content: "请委派 research 分析" });
  const taskCallMsg = new AIMessage({
    id: "ai-task-call",
    content: "",
    tool_calls: [{
      name: "task",
      args: { subagent_type: "research", description: "只读分析 /workspace/report.py" },
      id: "call-task-1",
    }],
  });
  const subagentHumanMsg = new HumanMessage({
    id: "subagent-input-human",
    content: "只读分析 /workspace/report.py",
  });
  const finalAiMsg = new AIMessage({ id: "ai-final", content: "分析完毕" });

  const stream = {
    messages: shallowRef([userMsg, taskCallMsg, subagentHumanMsg, finalAiMsg]),
    values: shallowRef({ messages: [userMsg, taskCallMsg, finalAiMsg] }),
    isLoading: shallowRef(false),
    subgraphs: shallowRef(new Map()),
    subagents: shallowRef(new Map([
      ["call-task-1", {
        id: "call-task-1",
        name: "research",
        namespace: ["tools:subagent-1"],
        taskInput: "只读分析 /workspace/report.py",
      }],
    ])),
  };

  const scope = effectScope();
  try {
    const rootMessages = scope.run(() => useTranscriptMessages(stream as unknown as AnyStream))!;
    // Even BEFORE subagent values event arrives (source is undefined), taskInput matches and blocks leakage
    expect(rootMessages.value.map(m => m.id)).toEqual(["user-root", "ai-task-call", "ai-final"]);

    // And after subagent values event arrives (source becomes child namespace), it remains filtered
    hooks.onEvent({
      method: "values",
      params: { namespace: ["tools:subagent-1"], data: { messages: [subagentHumanMsg] } },
    });
    expect(rootMessages.value.map(m => m.id)).toEqual(["user-root", "ai-task-call", "ai-final"]);
  } finally {
    scope.stop();
  }
});

it("filters out subagent internal tool calls and tool messages from root transcript", () => {
  const rootAiTaskMsg = new AIMessage({
    id: "root-task-call",
    content: "正在委派 research 进行分析",
    tool_calls: [{ name: "task", args: { subagent_type: "research" }, id: "task-call-1" }],
  });
  const subagentToolCallMsg = new AIMessage({
    id: "subagent-ls-call",
    content: "",
    tool_calls: [{ name: "ls", args: { path: "/workspace" }, id: "call-ls-1" }],
  });
  const subagentToolMsg = {
    id: "subagent-ls-result",
    type: "tool" as const,
    content: "report.py  README.md",
    tool_call_id: "call-ls-1",
  };
  const rootAiReplyMsg = new AIMessage({
    id: "root-final-reply",
    content: "只读分析结果：report.py 缺陷",
  });

  const stream = {
    messages: shallowRef([rootAiTaskMsg, subagentToolCallMsg, subagentToolMsg, rootAiReplyMsg]),
    values: shallowRef({ messages: [rootAiTaskMsg, rootAiReplyMsg] }),
    isLoading: shallowRef(false),
    subgraphs: shallowRef(new Map()),
    subagents: shallowRef(new Map([
      ["task-call-1", {
        id: "task-call-1",
        name: "research",
        namespace: ["tools:subagent-1"],
      }],
    ])),
  };

  const scope = effectScope();
  try {
    const rootMessages = scope.run(() => useTranscriptMessages(stream as unknown as AnyStream))!;
    // Dispatch event indicating subagent tool calls are from ["tools:subagent-1"]
    hooks.onEvent({
      method: "messages",
      params: { namespace: ["tools:subagent-1"], data: { id: "subagent-ls-call" } },
    });
    hooks.onEvent({
      method: "messages",
      params: { namespace: ["tools:subagent-1"], data: { id: "subagent-ls-result" } },
    });

    // Root transcript should only contain root-task-call and root-final-reply, NOT subagent-ls-call or subagent-ls-result!
    expect(rootMessages.value.map(m => m.id)).toEqual(["root-task-call", "root-final-reply"]);
  } finally {
    scope.stop();
  }
});

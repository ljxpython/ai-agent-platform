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

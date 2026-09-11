import { expect, it } from "vitest";
import { messagesProjection } from "@langchain/langgraph-sdk/stream";
import type { BaseMessage } from "@langchain/core/messages";
import { SubscriptionHandle } from "@langchain/langgraph-sdk";

it("scoped replay resumes when root terminal paused the handle before subscribe resolved", async () => {
  const namespace = ["specialist:left", "talk:nested"];
  const projection = messagesProjection(namespace);
  const handle = new SubscriptionHandle("nested", { channels: ["values"] }, async () => {});
  handle.pause();
  let snapshot: BaseMessage[] = [];
  const runtime = projection.open({
    thread: { subscribe: async () => handle },
    store: { setValue: (value: BaseMessage[]) => { snapshot = value; } },
    rootBus: { channels: [] },
  } as unknown as Parameters<typeof projection.open>[0]);
  try {
    await expect.poll(() => handle.isPaused).toBe(false);
    handle.push({ type: "event", method: "values", params: { namespace, data: {
      messages: [{ type: "ai", id: "nested", content: "NESTED_PRIVATE" }],
    } } } as Parameters<typeof handle.push>[0]);
    await expect.poll(() => snapshot.map(message => message.content)).toEqual(["NESTED_PRIVATE"]);
  } finally { await runtime.dispose(); }
});

it("scoped SDK replay keeps parent messages when child values arrive", async () => {
  const namespace = ["specialist:left"];
  const projection = messagesProjection(namespace);
  let snapshot: BaseMessage[] = [];
  const subscription = {
    resume() {},
    async *[Symbol.asyncIterator]() {
      for (const [scope, id] of [[namespace, "parent"], [[...namespace, "talk:nested"], "child"]] as const) {
        yield { method: "values", params: { namespace: scope, data: {
          messages: [{ type: "ai", id, content: id }],
        } } };
      }
    },
    unsubscribe: async () => {},
  };
  const runtime = projection.open({
    thread: { subscribe: async () => subscription },
    store: { setValue: (value: BaseMessage[]) => { snapshot = value; } },
    rootBus: { channels: [] },
  } as unknown as Parameters<typeof projection.open>[0]);
  try {
    await expect.poll(() => snapshot.map(message => message.id)).toEqual(["parent"]);
  } finally {
    await runtime.dispose();
  }
});

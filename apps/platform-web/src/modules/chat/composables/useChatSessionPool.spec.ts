// @vitest-environment jsdom
import { ref, type Slots } from "vue";
import { expect, it, vi } from "vitest";
import { createChatSessionPool } from "./useChatSessionPool";

const target = {
  graphId: "graph-1",
  agentId: "agent-1",
  name: "Agent",
  context: {},
};

it("keeps one instance per thread and rejects target collisions", () => {
  const pool = createChatSessionPool();
  const draft = pool.acquire(
    "u:e:p",
    "p",
    "chat",
    target,
    undefined,
    "draft-1",
  );
  const id = draft.instanceId;
  pool.bindThread(draft, "thread-1");
  expect(
    pool.acquire("u:e:p", "p", "dear-agent", target, "thread-1").instanceId,
  ).toBe(id);
  expect(() =>
    pool.acquire(
      "u:e:p",
      "p",
      "chat",
      { ...target, graphId: "other" },
      "thread-1",
    ),
  ).toThrow("目标不一致");
  const other = pool.acquire(
    "u:e:p",
    "p",
    "chat",
    target,
    undefined,
    "draft-2",
  );
  expect(() => pool.bindThread(other, "thread-1")).toThrow("另一实例");
  pool.clearScope();
  expect(pool.entries.size).toBe(0);
  expect(draft.disposed).toBe(true);
});

it("delivers a background thread ACK only when its own view returns", () => {
  const pool = createChatSessionPool();
  const a = pool.acquire("u:e:p", "p", "chat", target, undefined, "draft-a");
  const b = pool.acquire("u:e:p", "p", "chat", target, "thread-b");
  const onThread = vi.fn();
  const view = {
    outlet: document.createElement("div"),
    slots: {} as Slots,
    focusMode: ref(false),
    canWrite: ref(true),
    projectName: ref("P"),
    threadTitle: ref(""),
    onThread,
    onFork: vi.fn(),
    onRefresh: vi.fn(),
    onRevoked: vi.fn(),
  };
  pool.attachView(b, view);
  pool.bindThread(a, "thread-a");
  a.pendingThreadRoute = "thread-a";
  expect(onThread).not.toHaveBeenCalled();
  pool.attachView(a, view);
  expect(onThread).toHaveBeenCalledTimes(1);
  expect(onThread).toHaveBeenCalledWith("thread-a");
  expect(a.pendingThreadRoute).toBeUndefined();
});

it("keeps draft, attachments, and run options on their own Thread entry", () => {
  const pool = createChatSessionPool();
  const a = pool.acquire("u:e:p", "p", "chat", target, "thread-a");
  const b = pool.acquire("u:e:p", "p", "chat", target, "thread-b");
  const attachment = {
    type: "image_url",
    image_url: { url: "data:image/png;base64,AAAA" },
  } as (typeof a.attachments.value)[number];
  a.draft.value = "A draft";
  a.attachments.value = [attachment];
  a.context.value = { model_id: "model-a" };
  a.recursionLimit.value = 17;
  b.draft.value = "B draft";
  b.context.value = { model_id: "model-b" };
  expect(pool.acquire("u:e:p", "p", "dear-agent", target, "thread-a")).toBe(a);
  expect(a.attachments.value).toEqual([attachment]);
  expect(a.draft.value).toBe("A draft");
  expect(a.context.value.model_id).toBe("model-a");
  expect(a.recursionLimit.value).toBe(17);
  expect(b.attachments.value).toEqual([]);
  expect(b.draft.value).toBe("B draft");
  expect(b.context.value.model_id).toBe("model-b");
  expect(b.recursionLimit.value).toBe(1000);
  pool.clearScope();
  expect(pool.entries.size).toBe(0);
});

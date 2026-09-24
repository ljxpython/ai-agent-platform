// @vitest-environment node
import { expect, it, vi } from "vitest";
import { createRunActions, platformCommand } from "./run-actions";

it("aborts session streams on disposal and preserves SDK cancellation", async () => {
  const wire = vi.fn<typeof fetch>().mockResolvedValue(new Response());
  const actions = createRunActions("project-A", wire);
  const sdk = new AbortController();
  await actions.fetch("https://platform/stream/events", { signal: sdk.signal });
  await actions.fetch(new Request("https://platform/stream/events"));
  const signals = wire.mock.calls.map(([, init]) => init!.signal!);
  sdk.abort();
  expect(signals[0].aborted).toBe(true);
  expect(signals[1].aborted).toBe(false);
  actions.dispose();
  expect(signals.every(signal => signal.aborted)).toBe(true);
});

it("maps SDK multi-interrupt responses by ID and refuses configuration overrides", () => {
  const command = {
    id: 7,
    method: "input.respond",
    params: {
      responses: [
        {
          interrupt_id: "B",
          namespace: ["task:B"],
          response: { decisions: [{ type: "reject", message: "保留" }] },
        },
        {
          interrupt_id: "A",
          namespace: ["task:A"],
          response: { decisions: [{ type: "approve" }] },
        },
      ],
    },
  };
  expect(JSON.parse(platformCommand(JSON.stringify(command))).params).toEqual({
    resume: {
      B: { decisions: [{ type: "reject", message: "保留" }] },
      A: { decisions: [{ type: "approve" }] },
    },
  });
  expect(() =>
    platformCommand(
      JSON.stringify({ ...command, params: { ...command.params, config: {} } }),
    ),
  ).toThrow("不能覆盖");
});

it("keeps the same key and exact wire request after a lost ACK, isolates new actions", async () => {
  const wire = vi
    .fn<typeof fetch>()
    .mockRejectedValueOnce(new TypeError("network lost"))
    .mockResolvedValue(
      new Response(
        JSON.stringify({ type: "success", result: { run_id: "run-1" } }),
      ),
    );
  const actions = createRunActions("project-A", wire);
  actions.begin("thread-A", "send", { text: "original" });
  const body = JSON.stringify({
    id: 12,
    method: "run.start",
    params: { input: { text: "original" } },
  });
  await expect(
    actions.fetch("https://platform/api/langgraph/threads/thread-A/commands", {
      method: "POST",
      body,
    }),
  ).rejects.toThrow();
  expect(actions.current.value?.status).toBe("unknown");
  expect(() => actions.begin("thread-A", "send", {})).toThrow("核实");
  await actions.retry();
  const first = wire.mock.calls[0]?.[1];
  const retry = wire.mock.calls[1]?.[1];
  expect(retry?.body).toBe(first?.body);
  expect(new Headers(retry?.headers).get("Idempotency-Key")).toBe(
    new Headers(first?.headers).get("Idempotency-Key"),
  );
  expect(new Headers(retry?.headers).get("x-project-id")).toBe("project-A");
  expect(actions.current.value?.status).toBe("acknowledged");
  const firstKey = actions.current.value?.key;
  actions.begin("thread-A", "send", { text: "original" });
  expect(actions.current.value?.key).not.toBe(firstKey);
  actions.dispose();
  await expect(actions.retry()).rejects.toThrow();
});

it("filters replayed SSE frames belonging to previously completed runs while keeping active run frames", async () => {
  const sseBody = [
    `id: 0\nevent: stream\ndata: ${JSON.stringify({ type: "event", method: "lifecycle", params: { event: "completed", run_id: "run-1", data: { status: "completed" } } })}\n\n`,
    `id: 1\nevent: stream\ndata: ${JSON.stringify({ type: "event", method: "messages", params: { event: "message-chunk", run_id: "run-2", data: { id: "ai-2", delta: { content: "你好" } } } })}\n\n`,
  ].join("");
  const wire = vi.fn<typeof fetch>().mockImplementation(async (input) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    if (url.endsWith("/commands")) {
      return new Response(
        JSON.stringify({ type: "success", result: { run_id: "run-2" } }),
      );
    }
    return new Response(sseBody, {
      headers: { "Content-Type": "text/event-stream" },
    });
  });
  const actions = createRunActions("project-A", wire);
  actions.begin("thread-A", "send", { text: "first" });
  actions.acknowledge(undefined, "run-1");
  actions.begin("thread-A", "send", { text: "second" });
  await actions.fetch("https://platform/api/langgraph/threads/thread-A/commands", {
    method: "POST",
    body: JSON.stringify({ id: 2, method: "run.start", params: { input: { text: "second" } } }),
  });
  expect(actions.current.value?.runId).toBe("run-2");

  const streamRes = await actions.fetch(
    "https://platform/api/langgraph/threads/thread-A/stream/events",
    { method: "POST" },
  );
  const text = await streamRes.text();
  expect(text).not.toContain('"run_id":"run-1"');
  expect(text).toContain('"run_id":"run-2"');
  expect(text).toContain("message-chunk");
});


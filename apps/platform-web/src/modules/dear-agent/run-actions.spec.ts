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
          interrupt_id: "intr-clarification",
          namespace: ["task:dear"],
          response: {
            schema_version: 1,
            status: "answered",
            values: { title: "架构方案" },
          },
        },
      ],
    },
  };
  expect(JSON.parse(platformCommand(JSON.stringify(command))).params).toEqual({
    resume: {
      "intr-clarification": {
        schema_version: 1,
        status: "answered",
        values: { title: "架构方案" },
      },
    },
  });
  expect(() =>
    platformCommand(
      JSON.stringify({ ...command, params: { ...command.params, config: {} } }),
    ),
  ).toThrow("不能覆盖");
});

it("dispatches converted command body with Idempotency-Key to authorizedFetch", async () => {
  const wire = vi.fn<typeof fetch>().mockResolvedValue(
    new Response(
      JSON.stringify({ type: "success", result: { run_id: "run-resumed-1" } }),
    ),
  );
  const actions = createRunActions("project-A", wire);
  actions.begin("thread-123", "resume", { answer: "yes" });

  const rawSdkBody = JSON.stringify({
    id: 10,
    method: "input.respond",
    params: {
      responses: [
        {
          interrupt_id: "intr-1",
          response: {
            schema_version: 1,
            status: "answered",
            values: { goal: "test" },
          },
        },
      ],
    },
  });

  const res = await actions.fetch(
    "https://platform/api/langgraph/threads/thread-123/commands",
    {
      method: "POST",
      body: rawSdkBody,
    },
  );

  expect(res.ok).toBe(true);
  expect(wire).toHaveBeenCalledTimes(1);
  const [wireUrl, wireInit] = wire.mock.calls[0]!;
  expect(wireUrl).toBe("https://platform/api/langgraph/threads/thread-123/commands");

  // Verify that the transformed body (with params.resume) was sent to wire fetch, NOT the rawSdkBody!
  const sentBody = JSON.parse(wireInit?.body as string);
  expect(sentBody).toEqual({
    id: 10,
    method: "input.respond",
    params: {
      resume: {
        "intr-1": {
          schema_version: 1,
          status: "answered",
          values: { goal: "test" },
        },
      },
    },
  });
  expect(sentBody.params.responses).toBeUndefined();

  const headers = new Headers(wireInit?.headers);
  expect(headers.get("x-project-id")).toBe("project-A");
  expect(headers.get("Idempotency-Key")).toBeTruthy();
  expect(actions.current.value?.status).toBe("acknowledged");
  expect(actions.current.value?.runId).toBe("run-resumed-1");
});

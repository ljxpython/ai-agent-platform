// @vitest-environment node
import { createRequire } from "node:module";
import { afterEach, expect, it, vi } from "vitest";
import { ThreadStream } from "../../../node_modules/@langchain/langgraph-sdk/dist/client/stream/index.js";
import { ProtocolSseTransportAdapter } from "../../../node_modules/@langchain/langgraph-sdk/dist/client/stream/transport/http.js";

afterEach(() => vi.useRealTimers());

it("stops after five EOF retries and closes every physical request", async () => {
  vi.useFakeTimers();
  const wire = vi
    .fn<typeof fetch>()
    .mockImplementation(
      async () =>
        new Response("", { headers: { "content-type": "text/event-stream" } }),
    );
  const transport = new ProtocolSseTransportAdapter({
    apiUrl: "https://platform.example.com/api/langgraph",
    threadId: "t-1",
    fetch: wire,
    maxReconnectAttempts: 5,
    idleReconnect: false,
  });
  const handle = transport.openEventStream({ channels: ["values"] });
  await handle.ready;
  await vi.advanceTimersByTimeAsync(60_000);
  expect(wire).toHaveBeenCalledTimes(6);
  expect(transport.getConnectionState().state).toBe("paused");
  handle.close();
  await transport.close();
  expect(vi.getTimerCount()).toBe(0);
});

it("resets the retry budget only after a 30 second healthy connection", async () => {
  vi.useFakeTimers();
  let second!: ReadableStreamDefaultController<Uint8Array>;
  let third!: ReadableStreamDefaultController<Uint8Array>;
  const live = (
    assign: (controller: ReadableStreamDefaultController<Uint8Array>) => void,
  ) =>
    new Response(new ReadableStream<Uint8Array>({ start: assign }), {
      headers: { "content-type": "text/event-stream" },
    });
  const wire = vi
    .fn<typeof fetch>()
    .mockResolvedValueOnce(
      new Response("", { headers: { "content-type": "text/event-stream" } }),
    )
    .mockResolvedValueOnce(
      live((controller) => {
        second = controller;
      }),
    )
    .mockResolvedValueOnce(
      live((controller) => {
        third = controller;
      }),
    );
  const transport = new ProtocolSseTransportAdapter({
    apiUrl: "https://platform.example.com/api/langgraph",
    threadId: "t-1",
    fetch: wire,
    maxReconnectAttempts: 1,
    idleReconnect: false,
  });
  const handle = transport.openEventStream({ channels: ["values"] });
  await handle.ready;
  await vi.advanceTimersByTimeAsync(1500);
  expect(wire).toHaveBeenCalledTimes(2);
  await vi.advanceTimersByTimeAsync(31_000);
  second.close();
  await vi.advanceTimersByTimeAsync(1500);
  expect(wire).toHaveBeenCalledTimes(3);
  third.close();
  handle.close();
  await transport.close();
});

it("keeps a heartbeat-only connection alive and pauses after 45 seconds without bytes", async () => {
  vi.useFakeTimers();
  let controller!: ReadableStreamDefaultController<Uint8Array>;
  const wire = vi.fn<typeof fetch>().mockResolvedValue(
    new Response(
      new ReadableStream<Uint8Array>({
        start(value) {
          controller = value;
        },
      }),
      { headers: { "content-type": "text/event-stream" } },
    ),
  );
  const transport = new ProtocolSseTransportAdapter({
    apiUrl: "https://platform.example.com/api/langgraph",
    threadId: "t-1",
    fetch: wire,
    maxReconnectAttempts: 0,
    idleReconnect: 45_000,
  });
  const handle = transport.openEventStream({ channels: ["values"] });
  await handle.ready;
  await vi.advanceTimersByTimeAsync(30_000);
  controller.enqueue(new TextEncoder().encode(": heartbeat\n\n"));
  await vi.advanceTimersByTimeAsync(30_000);
  expect(transport.getConnectionState().state).toBe("connected");
  await vi.advanceTimersByTimeAsync(16_000);
  expect(transport.getConnectionState().state).toBe("paused");
  expect(wire).toHaveBeenCalledTimes(1);
  handle.close();
  await transport.close();
  expect(vi.getTimerCount()).toBe(0);
});

it("recovers only the paused physical stream when two subscriptions share a Thread", async () => {
  let healthy!: ReadableStreamDefaultController<Uint8Array>;
  let recovered!: ReadableStreamDefaultController<Uint8Array>;
  const live = (
    assign: (value: ReadableStreamDefaultController<Uint8Array>) => void,
  ) =>
    new Response(new ReadableStream<Uint8Array>({ start: assign }), {
      headers: { "content-type": "text/event-stream" },
    });
  const wire = vi
    .fn<typeof fetch>()
    .mockResolvedValueOnce(
      new Response("", { headers: { "content-type": "text/event-stream" } }),
    )
    .mockResolvedValueOnce(
      live((value) => {
        healthy = value;
      }),
    )
    .mockResolvedValueOnce(
      live((value) => {
        recovered = value;
      }),
    );
  const transport = new ProtocolSseTransportAdapter({
    apiUrl: "https://platform.example.com/api/langgraph",
    threadId: "t-1",
    fetch: wire,
    maxReconnectAttempts: 0,
    idleReconnect: false,
  });
  const content = transport.openEventStream({ channels: ["values"] });
  const lifecycle = transport.openEventStream({
    channels: ["lifecycle", "input"],
  });
  await Promise.all([content.ready, lifecycle.ready]);
  await vi.waitFor(() =>
    expect(transport.getConnectionState().state).toBe("paused"),
  );
  expect(
    transport.getConnectionState().streams.map((item) => item.state),
  ).toEqual(["paused", "connected"]);
  await transport.reconnectEvents();
  expect(wire).toHaveBeenCalledTimes(3);
  expect(transport.getConnectionState().state).toBe("connected");
  healthy.close();
  recovered.close();
  content.close();
  lifecycle.close();
  await transport.close();
});

it("keeps an installed SDK subscription after EOF and reconnects without a command", async () => {
  let secondStream!: ReadableStreamDefaultController<Uint8Array>;
  const wire = vi
    .fn<typeof fetch>()
    .mockResolvedValueOnce(
      new Response("", { headers: { "content-type": "text/event-stream" } }),
    )
    .mockResolvedValueOnce(
      new Response(
        new ReadableStream<Uint8Array>({
          start(controller) {
            secondStream = controller;
          },
        }),
        { headers: { "content-type": "text/event-stream" } },
      ),
    );
  const transport = new ProtocolSseTransportAdapter({
    apiUrl: "https://platform.example.com/api/langgraph",
    threadId: "t-1",
    fetch: wire,
    maxReconnectAttempts: 0,
    idleReconnect: false,
  });
  const handle = transport.openEventStream({ channels: ["values"] });
  await handle.ready;
  await vi.waitFor(() =>
    expect(transport.getConnectionState().state).toBe("paused"),
  );
  await transport.reconnectEvents();
  expect(transport.getConnectionState().state).toBe("connected");
  expect(wire).toHaveBeenCalledTimes(2);
  expect(wire.mock.calls.every(([, init]) => init?.method === "POST")).toBe(
    true,
  );
  secondStream.close();
  handle.close();
  await transport.close();
});

it("loads the patched CJS transport", () => {
  const require = createRequire(import.meta.url);
  const {
    ProtocolSseTransportAdapter: CjsTransport,
  } = require("../../../node_modules/@langchain/langgraph-sdk/dist/client/stream/transport/http.cjs");
  const transport = new CjsTransport({
    apiUrl: "https://platform.example.com",
    threadId: "t",
  });
  expect(transport.getConnectionState().state).toBe("connecting");
  expect(transport.reconnectEvents).toBeTypeOf("function");
});

it("keeps first ready pending through a failed handshake, then settles on manual recovery", async () => {
  let secondStream!: ReadableStreamDefaultController<Uint8Array>;
  const wire = vi
    .fn<typeof fetch>()
    .mockRejectedValueOnce(Object.assign(new Error("safe"), { status: 503 }))
    .mockResolvedValueOnce(
      new Response(
        new ReadableStream<Uint8Array>({
          start(controller) {
            secondStream = controller;
          },
        }),
        { headers: { "content-type": "text/event-stream" } },
      ),
    );
  const transport = new ProtocolSseTransportAdapter({
    apiUrl: "https://platform.example.com/api/langgraph",
    threadId: "t-1",
    fetch: wire,
    maxReconnectAttempts: 0,
    idleReconnect: false,
  });
  const handle = transport.openEventStream({ channels: ["values"], since: 9 });
  await vi.waitFor(() =>
    expect(transport.getConnectionState().state).toBe("paused"),
  );
  await transport.reconnectEvents();
  await handle.ready;
  expect(JSON.parse(String(wire.mock.calls[0]?.[1]?.body)).since).toBe(9);
  expect(
    JSON.parse(String(wire.mock.calls[1]?.[1]?.body)).since,
  ).toBeUndefined();
  secondStream.close();
  handle.close();
  await transport.close();
});

it("settles an initial ready waiter when its scope closes", async () => {
  const wire = vi
    .fn<typeof fetch>()
    .mockRejectedValue(Object.assign(new Error("safe"), { status: 403 }));
  const transport = new ProtocolSseTransportAdapter({
    apiUrl: "https://platform.example.com/api/langgraph",
    threadId: "t-1",
    fetch: wire,
    maxReconnectAttempts: 0,
  });
  const handle = transport.openEventStream({ channels: ["values"] });
  const pending = expect(handle.ready).rejects.toThrow("closed");
  await vi.waitFor(() =>
    expect(transport.getConnectionState().state).toBe("paused"),
  );
  handle.close();
  await pending;
  await transport.close();
  expect(wire).toHaveBeenCalledTimes(1);
});

it("replays history to a late shared subscriber without duplicating the first", async () => {
  const controllers: ReadableStreamDefaultController<Uint8Array>[] = [];
  const wire = vi.fn<typeof fetch>().mockImplementation(
    async () =>
      new Response(
        new ReadableStream<Uint8Array>({
          start(controller) {
            controllers.push(controller);
          },
        }),
        { headers: { "content-type": "text/event-stream" } },
      ),
  );
  const transport = new ProtocolSseTransportAdapter({
    apiUrl: "https://platform.example.com/api/langgraph",
    threadId: "t-1",
    fetch: wire,
    maxReconnectAttempts: 0,
    idleReconnect: false,
  });
  const thread = new ThreadStream(transport, {
    assistantId: "reference_agent",
  });
  const event = {
    type: "event",
    seq: 1,
    event_id: "replayed-1",
    method: "values",
    params: {
      thread_id: "t-1",
      run_id: "run-1",
      namespace: [],
      data: { messages: [{ id: "m-1", type: "ai", content: "first" }] },
    },
  };
  const frame = new TextEncoder().encode(
    `event: event\ndata: ${JSON.stringify(event)}\n\n`,
  );
  try {
    const first = await thread.subscribe("values");
    const reader = first[Symbol.asyncIterator]();
    const received = reader.next();
    controllers[0]!.enqueue(frame);
    expect((await received).value.event_id).toBe("replayed-1");
    let duplicated = false;
    void reader.next().then(({ done }) => {
      duplicated = !done;
    });
    const second = await thread.subscribe("values");
    const late = second[Symbol.asyncIterator]().next();
    controllers[1]!.enqueue(frame);
    expect((await late).value.event_id).toBe("replayed-1");
    await Promise.resolve();
    expect(duplicated).toBe(false);
    expect(wire).toHaveBeenCalledTimes(2);
    expect(
      JSON.parse(String(wire.mock.calls[1]?.[1]?.body)).since,
    ).toBeUndefined();
  } finally {
    await thread.close();
  }
});

it("keeps equal event IDs isolated across namespace subscriptions", async () => {
  let controller!: ReadableStreamDefaultController<Uint8Array>;
  const wire = vi.fn<typeof fetch>().mockResolvedValue(
    new Response(
      new ReadableStream<Uint8Array>({
        start(value) {
          controller = value;
        },
      }),
      { headers: { "content-type": "text/event-stream" } },
    ),
  );
  const transport = new ProtocolSseTransportAdapter({
    apiUrl: "https://platform.example.com/api/langgraph",
    threadId: "t-1",
    fetch: wire,
    maxReconnectAttempts: 0,
    idleReconnect: false,
  });
  const thread = new ThreadStream(transport, {
    assistantId: "reference_agent",
  });
  try {
    const [a, b] = await Promise.all([
      thread.subscribe({ channels: ["values"], namespaces: [["task:a"]] }),
      thread.subscribe({ channels: ["values"], namespaces: [["task:b"]] }),
    ]);
    const nextA = a[Symbol.asyncIterator]().next();
    const nextB = b[Symbol.asyncIterator]().next();
    for (const namespace of ["task:a", "task:b"]) {
      const event = {
        type: "event",
        seq: 1,
        event_id: "same-id",
        method: "values",
        params: {
          thread_id: "t-1",
          run_id: "run-1",
          namespace: [namespace],
          data: {
            messages: [{ id: namespace, type: "ai", content: namespace }],
          },
        },
      };
      controller.enqueue(
        new TextEncoder().encode(
          `event: event\ndata: ${JSON.stringify(event)}\n\n`,
        ),
      );
    }
    expect((await nextA).value.params.namespace).toEqual(["task:a"]);
    expect((await nextB).value.params.namespace).toEqual(["task:b"]);
  } finally {
    await thread.close();
  }
});

it("recovers a failed shared-filter rotation without recreating subscriptions", async () => {
  const controllers: ReadableStreamDefaultController<Uint8Array>[] = [];
  const live = () =>
    new Response(
      new ReadableStream<Uint8Array>({
        start(controller) {
          controllers.push(controller);
        },
      }),
      { headers: { "content-type": "text/event-stream" } },
    );
  const wire = vi
    .fn<typeof fetch>()
    .mockImplementationOnce(async () => live())
    .mockRejectedValueOnce(
      Object.assign(new Error("safe upstream failure"), { status: 503 }),
    )
    .mockImplementationOnce(async () => live());
  const transport = new ProtocolSseTransportAdapter({
    apiUrl: "https://platform.example.com/api/langgraph",
    threadId: "t-1",
    fetch: wire,
    maxReconnectAttempts: 0,
    idleReconnect: false,
  });
  const thread = new ThreadStream(transport, {
    assistantId: "reference_agent",
  });
  try {
    const first = await thread.subscribe("values");
    const secondReady = thread.subscribe("messages");
    await vi.waitFor(() =>
      expect(thread.getConnectionState().state).toBe("paused"),
    );
    await thread.reconnectEvents();
    const second = await secondReady;
    expect(first.subscriptionId).toBeTruthy();
    expect(second.subscriptionId).toBeTruthy();
    expect(thread.getConnectionState().state).toBe("connected");
    expect(wire).toHaveBeenCalledTimes(3);
    expect(wire.mock.calls.every(([, init]) => init?.method === "POST")).toBe(
      true,
    );
  } finally {
    await thread.close();
  }
});

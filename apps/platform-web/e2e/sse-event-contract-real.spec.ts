import { expect, test } from "@playwright/test";
import { createPlatformFixture } from "./support/platform";

test.skip(
  process.env.RUN_SSE_REAL_E2E !== "1",
  "Requires the local platform-api and runtime-service stack",
);

const durationMs = Number(process.env.SSE_CAPACITY_DURATION_MS ?? 1_800_000);
const threadCount = Number(process.env.SSE_CAPACITY_THREADS ?? 8);
test.setTimeout(durationMs + 120_000);

test("real browser keeps Runtime-backed SSE threads alive for thirty accesses", async ({
  page,
}) => {
  const fixture = await createPlatformFixture("workflow_demo");
  const threadIds: string[] = [];
  try {
    for (let index = 0; index < threadCount; index += 1) {
      const thread = await fixture.request<{ thread_id: string }>(
        "/api/langgraph/threads",
        "POST",
        {
          metadata: {
            graph_id: fixture.graphId,
            title: `SSE capacity ${index + 1}`,
          },
        },
      );
      threadIds.push(thread.thread_id);
    }

    await page.goto("/");
    await page.evaluate(
      async ({ accessToken, projectId, threadIds }) => {
        const { ProtocolSseTransportAdapter } =
          await import("/src/services/langgraph/transport.ts");
        const transports = threadIds.map((threadId) => {
          const transport = new ProtocolSseTransportAdapter({
            apiUrl: `${location.origin}/api/langgraph`,
            threadId,
            fetch: (input, init) => {
              const headers = new Headers(init?.headers);
              headers.set("authorization", `Bearer ${accessToken}`);
              headers.set("x-project-id", projectId);
              return fetch(input, { ...init, headers });
            },
            maxReconnectAttempts: 2,
          });
          const handle = transport.openEventStream({ channels: ["values"] });
          return { transport, handle };
        });
        const target = window as typeof window & {
          capacityReadyItems?: Promise<unknown>[];
          capacityWaitReady?: (index: number) => Promise<void>;
          capacityClose?: () => Promise<void>;
        };
        target.capacityReadyItems = transports.map(({ handle }) =>
          Promise.race([
            handle.ready,
            new Promise<never>((_, reject) =>
              setTimeout(
                () => reject(new Error("Runtime SSE handshake timeout")),
                30_000,
              ),
            ),
          ]),
        );
        target.capacityWaitReady = async (index) => {
          await target.capacityReadyItems?.[index];
        };
        target.capacityClose = async () => {
          await Promise.all(
            transports.map(async ({ handle, transport }) => {
              handle.close();
              await transport.close();
            }),
          );
        };
        return transports.length;
      },
      {
        accessToken: fixture.tokens.access_token,
        projectId: fixture.projectId,
        threadIds,
      },
    );

    const runs = [];
    for (const [index, threadId] of threadIds.entries()) {
      runs.push(
        await fixture.request<{ run_id: string }>(
          `/api/langgraph/threads/${threadId}/runs`,
          "POST",
          {
            assistant_id: fixture.graphId,
            input: {
              messages: [{ type: "human", content: "需要人工确认后再继续" }],
            },
            config: {
              configurable: { platform_runtime: { model_id: fixture.modelId } },
            },
            stream_mode: ["values", "messages", "lifecycle"],
            stream_resumable: true,
          },
        ),
      );
      await page.evaluate((streamIndex) => {
        const target = window as typeof window & {
          capacityWaitReady?: (index: number) => Promise<void>;
        };
        return target.capacityWaitReady?.(streamIndex);
      }, index);
    }

    const result = await page.evaluate(
      async ({ accessToken, projectId, threadIds, durationMs }) => {
        const target = window as typeof window & {
          capacityReadyItems?: Promise<unknown>[];
          capacityClose?: () => Promise<void>;
        };
        await Promise.all(target.capacityReadyItems ?? []);

        const startedAt = Date.now();
        let accesses = 0;
        while (accesses < 30) {
          const threadId = threadIds[accesses % threadIds.length];
          const response = await fetch(
            `${location.origin}/api/langgraph/threads/${threadId}/state`,
            {
              headers: {
                authorization: `Bearer ${accessToken}`,
                "x-project-id": projectId,
              },
            },
          );
          if (!response.ok)
            throw new Error(`state access failed: HTTP ${response.status}`);
          accesses += 1;
          if (accesses < 30) {
            await new Promise((resolve) =>
              setTimeout(resolve, Math.ceil(durationMs / 30)),
            );
          }
        }

        const streamEntries = performance
          .getEntriesByType("resource")
          .filter(
            (entry): entry is PerformanceResourceTiming =>
              entry.name.includes("/api/langgraph/threads/") &&
              entry.name.includes("/stream"),
          );
        const protocols = [
          ...new Set(
            streamEntries.map((entry) => entry.nextHopProtocol).filter(Boolean),
          ),
        ];
        const memory = (
          performance as Performance & {
            memory?: { usedJSHeapSize: number };
          }
        ).memory;
        const heap = memory
          ? { start: memory.usedJSHeapSize, end: memory.usedJSHeapSize }
          : null;
        await target.capacityClose?.();
        return {
          accesses,
          readyStreams: threadIds.length,
          protocols,
          heap,
          elapsedMs: Date.now() - startedAt,
        };
      },
      {
        accessToken: fixture.tokens.access_token,
        projectId: fixture.projectId,
        threadIds,
        durationMs,
      },
    );

    expect(result.readyStreams).toBe(threadCount);
    expect(runs).toHaveLength(threadCount);
    expect(result.accesses).toBe(30);
    expect(result.elapsedMs).toBeGreaterThanOrEqual(durationMs);
    console.log(`SSE capacity result: ${JSON.stringify(result)}`);
    test.info().attach("sse-capacity-result.json", {
      body: JSON.stringify(result, null, 2),
      contentType: "application/json",
    });
  } finally {
    await fixture.cleanup();
  }
});

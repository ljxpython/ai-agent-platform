import { defineComponent, h, ref } from "vue";
import { mount } from "@vue/test-utils";
import { useStream, type UseStreamReturn } from "@langchain/vue";
import { expect, it } from "vitest";
import { createRunActions } from "./run-actions";
import { parseReviews } from "./approvals";
import {
  createPlatformFixture,
  platformUrl,
} from "../../../e2e/support/platform";

it.runIf(process.env.PLATFORM_CHAIN_TEST === "1")(
  "real Vue SDK sends, completes and hydrates through the platform gateway",
  async () => {
    const fixture = await createPlatformFixture();
    let wrapper: ReturnType<typeof mount> | undefined;
    let actions: ReturnType<typeof createRunActions> | undefined;
    try {
      const thread = await fixture.request<{ thread_id: string }>(
        "/api/langgraph/threads",
        "POST",
        {
          metadata: { graph_id: fixture.graphId },
        },
      );
      const methods: string[] = [];
      const events: string[] = [];
      const authorized: typeof fetch = async (input, init) => {
        const headers = new Headers(init?.headers);
        headers.set("Authorization", `Bearer ${fixture.tokens.access_token}`);
        headers.set("x-project-id", fixture.projectId);
        if (
          typeof init?.body === "string" &&
          input.toString().endsWith("/commands")
        ) {
          methods.push((JSON.parse(init.body) as { method: string }).method);
        }
        const response = await fetch(input, { ...init, headers });
        if (!response.ok) {
          const payload = (await response.clone().json()) as {
            error?: { code?: string; message?: string };
          };
          const command =
            typeof init?.body === "string"
              ? (JSON.parse(init.body) as {
                  params?: { config?: Record<string, unknown> };
                })
              : {};
          throw new Error(
            `Gateway ${response.status}: ${payload.error?.code}: ${payload.error?.message}; config=${JSON.stringify(command.params?.config)}`,
          );
        }
        if (
          response.body &&
          response.headers.get("content-type")?.includes("text/event-stream")
        ) {
          const decoder = new TextDecoder();
          let pending = "";
          return new Response(
            response.body.pipeThrough(
              new TransformStream<Uint8Array, Uint8Array>({
                transform(chunk, controller) {
                  pending += decoder.decode(chunk, { stream: true });
                  const lines = pending.split("\n");
                  pending = lines.pop() ?? "";
                  for (const line of lines)
                    if (line.startsWith("data:")) {
                      try {
                        const event = JSON.parse(line.slice(5)) as {
                          method?: string;
                          params?: { data?: { event?: string } };
                        };
                        if (events.length < 50)
                          events.push(
                            `${event.method}:${event.params?.data?.event ?? ""}`,
                          );
                      } catch {
                        /* Ignore heartbeat frames. */
                      }
                    }
                  controller.enqueue(chunk);
                },
              }),
            ),
            { headers: response.headers, status: response.status },
          );
        }
        return response;
      };
      actions = createRunActions(fixture.projectId, authorized);
      const transport = actions;
      let stream!: UseStreamReturn<{ messages: unknown[] }>;
      const threadId = ref<string | null>(thread.thread_id);
      const component = defineComponent({
        setup() {
          stream = useStream<{ messages: unknown[] }>({
            assistantId: fixture.graphId,
            apiUrl: `${platformUrl}/api/langgraph`,
            threadId,
            fetch: transport.fetch,
            callerOptions: { fetch: transport.fetch, maxRetries: 0 },
            onCreated: () => undefined,
          });
          return () => h("div");
        },
      });
      wrapper = mount(component);
      await stream.hydrationPromise.value;
      expect(stream.error.value).toBeUndefined();
      expect(stream.error.value).toBeUndefined();
      const input = {
        messages: [
          {
            id: crypto.randomUUID(),
            type: "human" as const,
            content: "请只回复：前端链路正常。不要调用工具。",
          },
        ],
      };
      transport.begin(thread.thread_id, "send", input);
      const submission = stream.submit(input, {
        config: {
          configurable: { platform_runtime: { model_id: fixture.modelId } },
        },
      });
      let timer: ReturnType<typeof setTimeout> | undefined;
      try {
        await Promise.race([
          submission,
          new Promise((_, reject) => {
            timer = setTimeout(
              () =>
                reject(
                  new Error(
                    `SDK terminal timeout: ${JSON.stringify(events)}; action=${transport.current.value?.status}`,
                  ),
                ),
              45000,
            );
          }),
        ]);
      } finally {
        clearTimeout(timer);
      }
      expect(stream.error.value).toBeUndefined();
      expect(transport.current.value?.status).toBe("acknowledged");
      expect(stream.isLoading.value).toBe(false);
      expect(
        stream.messages.value.some(
          (message) => message.type === "ai" && Boolean(message.content),
        ),
      ).toBe(true);
      const ids = stream.messages.value.map((message) => message.id);
      expect(new Set(ids).size).toBe(ids.length);
      await stream.disconnect();
      wrapper.unmount();
      const restored = await fixture.request<{
        values: { messages?: Array<{ id: string }> };
      }>(`/api/langgraph/threads/${thread.thread_id}/state`);
      expect(restored.values.messages?.map((message) => message.id)).toEqual(
        ids,
      );
      wrapper = mount(component);
      await stream.hydrationPromise.value;
      expect(stream.error.value).toBeUndefined();
      await expect
        .poll(() => stream.messages.value.map((message) => message.id))
        .toEqual(ids);
      expect(methods).toEqual(["run.start"]);
      const confirmation = {
        messages: [
          {
            id: crypto.randomUUID(),
            type: "human" as const,
            content: "需要人工确认：请回复审批完成，不要调用工具。",
          },
        ],
      };
      transport.begin(thread.thread_id, "send", confirmation);
      await stream.submit(confirmation, {
        config: {
          configurable: { platform_runtime: { model_id: fixture.modelId } },
        },
      });
      expect(stream.error.value).toBeUndefined();
      await expect.poll(() => stream.interrupts.value.length).toBe(1);
      const parentRun = transport.current.value?.runId;
      const approvalState = await fixture.request<{
        interrupts: Array<{ id: string; value: unknown }>;
      }>(`/api/langgraph/threads/${thread.thread_id}/state`);
      expect(
        parseReviews(approvalState.interrupts).map((review) => [
          review.id,
          review.fingerprint,
        ]),
      ).toEqual(
        parseReviews(stream.interrupts.value).map((review) => [
          review.id,
          review.fingerprint,
        ]),
      );
      const interruptId = stream.interrupts.value[0]?.id;
      expect(interruptId).toBeTruthy();
      const decisions = {
        [interruptId!]: { decisions: [{ type: "approve" }] },
      };
      transport.begin(thread.thread_id, "resume", decisions);
      await stream.respondAll(decisions);
      expect(stream.error.value).toBeUndefined();
      expect(transport.current.value?.status).toBe("acknowledged");
      expect(transport.current.value?.runId).not.toBe(parentRun);
      await expect.poll(() => stream.interrupts.value.length).toBe(0);
      await expect
        .poll(
          async () => {
            const run = await fixture.request<{ status: string }>(
              `/api/langgraph/threads/${thread.thread_id}/runs/${transport.current.value?.runId}`,
            );
            return run.status;
          },
          { timeout: 45000 },
        )
        .toBe("success");
      expect(methods).toEqual(["run.start", "run.start", "input.respond"]);
      const history = await fixture.request<
        Array<{
          checkpoint: { checkpoint_id: string; checkpoint_ns: string };
          values: { messages?: unknown[] };
        }>
      >(`/api/langgraph/threads/${thread.thread_id}/history`, "POST", {
        limit: 30,
      });
      const initial = history.find(
        (entry) => (entry.values.messages?.length ?? 0) === 0,
      );
      expect(initial?.checkpoint.checkpoint_id).toBeTruthy();
      await stream.disconnect();
      wrapper.unmount();
      const forkResponse = await transport.fork(
        `${platformUrl}/api/langgraph`,
        thread.thread_id,
        {
          assistant_id: fixture.graphId,
          checkpoint_id: initial!.checkpoint.checkpoint_id,
          input: {
            messages: [
              {
                id: crypto.randomUUID(),
                role: "user",
                content: "请只回复分支正常，不要调用工具。",
              },
            ],
          },
          context: { model_id: fixture.modelId },
        },
      );
      expect(forkResponse.ok).toBe(true);
      expect(transport.current.value?.status).toBe("acknowledged");
      wrapper = mount(component);
      await stream.hydrationPromise.value;
      await expect
        .poll(
          () => stream.messages.value.some((message) => message.type === "ai"),
          { timeout: 45000 },
        )
        .toBe(true);
      const forkHistory = await fixture.request<
        Array<{ checkpoint: { checkpoint_id: string } }>
      >(`/api/langgraph/threads/${thread.thread_id}/history`, "POST", {
        limit: 50,
      });
      expect(
        forkHistory.some(
          (entry) =>
            entry.checkpoint.checkpoint_id ===
            initial!.checkpoint.checkpoint_id,
        ),
      ).toBe(true);
    } finally {
      wrapper?.unmount();
      actions?.dispose();
      await fixture.cleanup();
    }
  },
  90000,
);

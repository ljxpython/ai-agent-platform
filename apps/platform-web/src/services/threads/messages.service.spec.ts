import { beforeEach, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ post: vi.fn() }));
vi.mock("@/services/http/client", () => ({
  platformHttpClient: { post: mocks.post },
}));
import { enqueueThreadMessage } from "./messages.service";

beforeEach(() => mocks.post.mockReset());

it("sends only the public payload with project and idempotency scope", async () => {
  mocks.post.mockResolvedValue({ data: { message_id: "m", status: "queued" } });
  await enqueueThreadMessage(
    "p",
    "t",
    { client_message_id: "m", target_run_id: "r", content: "hello" },
    "k",
  );
  expect(mocks.post).toHaveBeenCalledWith(
    "/api/langgraph/threads/t/messages",
    { client_message_id: "m", target_run_id: "r", content: "hello" },
    { headers: { "x-project-id": "p", "Idempotency-Key": "k" } },
  );
});

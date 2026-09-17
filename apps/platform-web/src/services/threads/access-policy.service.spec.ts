import { beforeEach, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ patch: vi.fn() }));
vi.mock("@/services/http/client", () => ({
  platformHttpClient: { patch: mocks.patch },
}));
import { updateThreadAccessPolicy } from "./access-policy.service";

beforeEach(() => mocks.patch.mockReset());

it("sends access_policy update payload with project scope header", async () => {
  mocks.patch.mockResolvedValue({
    data: { thread_id: "thread-123", access_policy: "workspace_write" },
  });

  const result = await updateThreadAccessPolicy(
    "proj-456",
    "thread-123",
    "workspace_write",
  );

  expect(mocks.patch).toHaveBeenCalledWith(
    "/api/langgraph/threads/thread-123/access-policy",
    { access_policy: "workspace_write" },
    { headers: { "x-project-id": "proj-456" } },
  );
  expect(result).toEqual({
    thread_id: "thread-123",
    access_policy: "workspace_write",
  });
});

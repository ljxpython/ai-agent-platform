import { expect, it, vi } from "vitest";
import { notifyAccessDenied } from "./access-events";

it("scopes thread and project rejections and suppresses snapshot feedback loops", () => {
  const listener = vi.fn();
  window.addEventListener("platform-access-denied", listener);
  try {
    notifyAccessDenied(
      "/api/langgraph/threads/t/runs",
      "POST",
      "p",
      "thread_action_denied",
    );
    expect(listener.mock.calls[0][0].detail).toMatchObject({
      scope: "thread",
      projectId: "p",
      threadId: "t",
      method: "POST",
    });
    notifyAccessDenied(
      "/api/langgraph/threads/t/runs",
      "POST",
      "p",
      "project_role_missing",
    );
    expect(listener.mock.calls[1][0].detail.scope).toBe("project");
    notifyAccessDenied(
      "/api/projects/p/access",
      "GET",
      null,
      "project_role_missing",
    );
    expect(listener).toHaveBeenCalledTimes(2);
  } finally {
    window.removeEventListener("platform-access-denied", listener);
  }
});

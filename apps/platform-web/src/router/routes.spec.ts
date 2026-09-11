import type { RouteRecordRaw } from "vue-router";
import { describe, expect, it } from "vitest";

import { routes } from "./routes";

function getWorkspaceChildren(): RouteRecordRaw[] {
  const workspaceRoute = routes.find((route) => route.path === "/workspace");
  return (workspaceRoute?.children ?? []) as RouteRecordRaw[];
}

describe("workspace project governance routes", () => {
  it("allows project detail through platform governance or project membership", () => {
    const projectDetailRoute = getWorkspaceChildren().find(
      (route) => route.name === "workspace-project-detail",
    );

    expect(projectDetailRoute?.meta).toMatchObject({
      requiredPermissions: ["platform.project.read", "project.member.read"],
      permissionMode: "any",
      permissionProjectSource: "route",
    });
  });
});

describe("workspace account routes", () => {
  it("registers the password change route used by the first-login guard", () => {
    const securityRoute = getWorkspaceChildren().find(
      (route) => route.name === "workspace-security",
    );

    expect(securityRoute?.path).toBe("security");
  });
});

describe("workspace primary navigation routes", () => {
  it("does not register retired knowledge or testcase workspaces", () => {
    const paths = getWorkspaceChildren().map((route) => route.path);

    expect(paths).not.toContain("projects/:projectId/knowledge");
    expect(paths).not.toContain("testcase");
    expect(paths).not.toContain("testcase-v2");
  });

  it("keeps Agent, Models, and Chat as distinct pages", () => {
    const primary = [
      "workspace-agents",
      "workspace-models",
      "workspace-chat",
    ].map((name) =>
      getWorkspaceChildren().find((route) => route.name === name),
    );

    expect(primary.map((route) => route?.path)).toEqual([
      "projects/:projectId/agents",
      "projects/:projectId/models",
      "projects/:projectId/chat/:threadId?",
    ]);
    expect(
      primary.every(
        (route) => route?.meta?.permissionProjectSource === "route",
      ),
    ).toBe(true);
    expect(new Set(primary.map((route) => route?.component)).size).toBe(3);
  });
});

describe("workspace runtime debug route", () => {
  it("does not expose the legacy debug surface", () => {
    const debugRoute = getWorkspaceChildren().find(
      (route) => route.name === "workspace-chat-debug",
    );

    expect(debugRoute).toBeUndefined();
  });
});

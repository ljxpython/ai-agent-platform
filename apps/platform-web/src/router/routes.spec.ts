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
  it("registers native evaluation studio routes and sidebar group", () => {
    const expectedTitles: Record<string, string> = {
      "workspace-evaluation": "题库资产全景",
      "workspace-evaluation-cases": "考题表格与出题",
      "workspace-evaluation-runs": "打擂任务大厅",
      "workspace-evaluation-detail": "评测集详情",
    };
    for (const [name, title] of Object.entries(expectedTitles)) {
      const route = getWorkspaceChildren().find((item) => item.name === name);
      expect(route?.meta?.title).toBe(title);
      expect(route?.meta?.requiredPermissions).toEqual([
        "project.evaluation.read",
      ]);
      if (name !== "workspace-evaluation-detail") {
        expect((route?.meta?.navigation as { group?: string })?.group).toBe(
          "评测中心",
        );
      }
    }
    const compareRoute = getWorkspaceChildren().find(
      (item) => item.name === "workspace-evaluation-compare",
    );
    expect(compareRoute?.meta?.navigation).toBeUndefined();
    expect(typeof compareRoute?.redirect).toBe("function");
  });
  it("does not register retired testcase workspaces", () => {
    const paths = getWorkspaceChildren().map((route) => route.path);

    expect(paths).not.toContain("testcase");
    expect(paths).not.toContain("testcase-v2");
  });

  it("registers project knowledge page as active workspace route", () => {
    const paths = getWorkspaceChildren().map((route) => route.path);

    expect(paths).toContain("projects/:projectId/knowledge");
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

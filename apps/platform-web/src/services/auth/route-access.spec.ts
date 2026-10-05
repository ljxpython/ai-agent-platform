import { describe, expect, it } from "vitest";
import type { ProjectAccess } from "@/types/management";
import { resolveRouteAccess } from "./route-access";

const route = {
  meta: {
    requiredPermissions: ["project.assistant.write" as const],
    permissionProjectSource: "route" as const,
  },
  params: { projectId: "A" },
};
const snapshot: ProjectAccess = {
  project_id: "A",
  roles: ["project_executor"],
  permissions: ["project.runtime.read"],
};

describe("route access state", () => {
  it("never grants a page solely because the user still has a project role", () => {
    expect(
      resolveRouteAccess(route, null, {
        currentProjectId: "A",
        currentProjectAccess: snapshot,
        accessLoading: true,
      }),
    ).toBe("denied");
  });
  it("retains only previously granted permissions during refresh failure", () => {
    expect(
      resolveRouteAccess(
        {
          ...route,
          meta: {
            ...route.meta,
            requiredPermissions: ["project.runtime.read"],
          },
        },
        null,
        {
          currentProjectId: "A",
          currentProjectAccess: snapshot,
          accessStatus: "unavailable",
        },
      ),
    ).toBe("allowed");
  });
  it.each([
    [true, "unknown", "loading"],
    [false, "unavailable", "unavailable"],
    [false, "denied", "denied"],
  ])(
    "distinguishes missing snapshots",
    (accessLoading, accessStatus, expected) => {
      expect(
        resolveRouteAccess(route, null, {
          currentProjectId: "A",
          currentProjectAccess: null,
          accessLoading: Boolean(accessLoading),
          accessStatus: String(accessStatus),
        }),
      ).toBe(expected);
    },
  );
  it("does not borrow a snapshot from another project", () => {
    expect(
      resolveRouteAccess(route, null, {
        currentProjectId: "B",
        currentProjectAccess: snapshot,
        accessStatus: "unavailable",
      }),
    ).toBe("denied");
    expect(
      resolveRouteAccess({ ...route, params: { projectId: "B" } }, null, {
        currentProjectId: "B",
        currentProjectAccess: snapshot,
        accessStatus: "unavailable",
      }),
    ).toBe("unavailable");
  });
});

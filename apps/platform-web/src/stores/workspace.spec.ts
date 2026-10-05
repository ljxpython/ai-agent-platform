import { beforeEach, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import type { ProjectAccess } from "@/types/management";

const api = vi.hoisted(() => ({
  getProjectAccess: vi.fn(),
  listProjects: vi.fn(),
}));
vi.mock("@/services/projects/projects.service", () => api);
import { useWorkspaceStore } from "./workspace";

beforeEach(() => {
  setActivePinia(createPinia());
  vi.resetAllMocks();
  localStorage.clear();
});

it("clears old permissions immediately and ignores delayed project responses", async () => {
  let resolveA!: (value: ProjectAccess) => void;
  api.getProjectAccess.mockImplementation((id: string) =>
    id === "A"
      ? new Promise<ProjectAccess>((resolve) => {
          resolveA = resolve;
        })
      : Promise.resolve({ project_id: "B", permissions: [], roles: [] }),
  );
  const store = useWorkspaceStore();
  const pending = store.setProjectId("A");
  await store.setProjectId("B");
  resolveA({
    project_id: "A",
    permissions: ["project.runtime.write"],
    roles: ["project_admin"],
  });
  await pending;
  expect(store.currentProjectAccess?.project_id).toBe("B");
  expect(store.currentProjectAccess?.permissions).toEqual([]);
});

it("logout invalidates in-flight hydration", async () => {
  let resolve!: (rows: []) => void;
  api.listProjects.mockReturnValue(
    new Promise<[]>((done) => {
      resolve = done;
    }),
  );
  const store = useWorkspaceStore();
  const pending = store.hydrateContext();
  store.reset();
  resolve([]);
  await pending;
  expect(store.contextLoaded).toBe(false);
  expect(store.currentProjectAccess).toBeNull();
  expect(store.currentProjectId).toBe("");
});

it("clears revoked permissions when the periodic access refresh is rejected", async () => {
  api.getProjectAccess
    .mockResolvedValueOnce({
      project_id: "A",
      permissions: ["project.runtime.write"],
      roles: ["project_executor"],
    })
    .mockRejectedValueOnce(
      Object.assign(new Error("forbidden"), { status: 403 }),
    );
  const store = useWorkspaceStore();
  await store.setProjectId("A");

  await expect(store.refreshCurrentProjectAccess()).rejects.toThrow(
    "forbidden",
  );

  expect(store.currentProjectAccess).toBeNull();
  expect(store.error).toBe("当前账号无法访问此项目");
});

it("retains current permissions on transient network error during refresh", async () => {
  api.getProjectAccess
    .mockResolvedValueOnce({
      project_id: "A",
      permissions: ["project.runtime.write"],
      roles: ["project_executor"],
    })
    .mockRejectedValueOnce(new Error("Network Error"));
  const store = useWorkspaceStore();
  await store.setProjectId("A");

  await expect(store.refreshCurrentProjectAccess()).rejects.toThrow(
    "Network Error",
  );

  expect(store.currentProjectAccess).toEqual({
    project_id: "A",
    permissions: ["project.runtime.write"],
    roles: ["project_executor"],
  });
  expect(store.accessStatus).toBe("unavailable");
});

it("coalesces project refresh and keeps permission-specific snapshots on network failure", async () => {
  const store = useWorkspaceStore();
  let complete!: (value: ProjectAccess) => void;
  api.getProjectAccess.mockReturnValue(
    new Promise<ProjectAccess>((resolve) => {
      complete = resolve;
    }),
  );
  const first = store.setProjectId("A");
  const second = store.refreshCurrentProjectAccess();
  expect(api.getProjectAccess).toHaveBeenCalledTimes(1);
  complete({
    project_id: "A",
    roles: ["project_executor"],
    permissions: ["project.runtime.read"],
  });
  await Promise.all([first, second]);
  await store.refreshCurrentProjectAccess(false);
  expect(api.getProjectAccess).toHaveBeenCalledTimes(1);
});

it("does not erase context on a failed list refresh and retries initial failure", async () => {
  const store = useWorkspaceStore();
  api.listProjects.mockRejectedValue(new Error("offline"));
  await store.hydrateContext();
  expect(store.contextLoaded).toBe(false);
  api.listProjects.mockResolvedValue([{ id: "A" }]);
  api.getProjectAccess.mockResolvedValue({
    project_id: "A",
    roles: [],
    permissions: ["project.runtime.read"],
  });
  await store.hydrateContext();
  const access = store.currentProjectAccess;
  api.listProjects.mockRejectedValue(new Error("offline"));
  await store.hydrateContext();
  expect(store.currentProjectId).toBe("A");
  expect(store.projects).toEqual([{ id: "A" }]);
  expect(store.currentProjectAccess).toEqual(access);
});

it.each([
  [{ status: 404, code: "route_not_found" }, "unavailable", true],
  [
    {
      response: { status: 404, data: { error: { code: "project_not_found" } } },
    },
    "denied",
    false,
  ],
])(
  "distinguishes resource deletion from missing API routes",
  async (error, status, retain) => {
    const store = useWorkspaceStore();
    api.getProjectAccess
      .mockResolvedValueOnce({
        project_id: "A",
        roles: [],
        permissions: ["project.runtime.read"],
      })
      .mockRejectedValueOnce(error);
    await store.setProjectId("A");
    await expect(store.refreshCurrentProjectAccess()).rejects.toBe(error);
    expect(store.accessStatus).toBe(status);
    expect(Boolean(store.currentProjectAccess)).toBe(retain);
  },
);

it("accepts successful empty permissions as authoritative revocation", async () => {
  const store = useWorkspaceStore();
  api.getProjectAccess
    .mockResolvedValueOnce({
      project_id: "A",
      roles: ["project_executor"],
      permissions: ["project.runtime.read"],
    })
    .mockResolvedValueOnce({ project_id: "A", roles: [], permissions: [] });
  await store.setProjectId("A");
  await store.refreshCurrentProjectAccess();
  expect(store.accessStatus).toBe("denied");
  expect(store.currentProjectAccess?.permissions).toEqual([]);
});

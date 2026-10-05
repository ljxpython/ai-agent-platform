import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, getActivePinia, setActivePinia } from "pinia";
import { nextTick } from "vue";
import { beforeEach, expect, it, vi } from "vitest";
import { useWorkspaceStore } from "@/stores/workspace";

const api = vi.hoisted(() => ({ access: vi.fn() }));
vi.mock("@/services/projects/projects.service", () => ({
  getProjectAccess: api.access,
  listProjects: vi.fn(),
}));
vi.mock("vue-router", () => ({
  useRoute: () => ({
    name: "editor",
    fullPath: "/workspace/projects/p/agents/new",
    params: { projectId: "p" },
    meta: {
      requiredPermissions: ["project.assistant.write"],
      permissionProjectSource: "route",
    },
  }),
}));
vi.mock("@/stores/auth", () => ({
  useAuthStore: () => ({
    user: { id: "u" },
    sessionEpoch: 1,
    isAuthenticated: true,
    fetchCurrentUser: vi.fn(),
  }),
}));
vi.mock("@/components/layout/AppSidebar.vue", () => ({
  default: { template: "<aside />" },
}));
vi.mock("@/components/layout/TopContextBar.vue", () => ({
  default: { template: "<header />" },
}));
vi.mock("@/modules/chat/components/ChatSessionPool.vue", () => ({
  default: { template: "<div />" },
}));
import WorkspaceLayout from "./WorkspaceLayout.vue";

beforeEach(() => {
  setActivePinia(createPinia());
  api.access.mockReset();
  localStorage.clear();
});

it("keeps the rendered page and draft on background failure, but removes it on a real downgrade", async () => {
  const store = useWorkspaceStore();
  api.access.mockResolvedValue({
    project_id: "p",
    roles: ["project_editor"],
    permissions: ["project.assistant.write"],
  });
  await store.setProjectId("p");
  const wrapper = mount(WorkspaceLayout, {
    global: {
      plugins: [getActivePinia()!],
      stubs: {
        "router-view": { template: '<input aria-label="draft" />' },
        RouterLink: true,
      },
    },
  });
  try {
    await wrapper.get("input").setValue("keep my work");
    api.access.mockRejectedValueOnce(new Error("offline"));
    await expect(store.refreshCurrentProjectAccess()).rejects.toThrow(
      "offline",
    );
    await nextTick();
    expect((wrapper.get("input").element as HTMLInputElement).value).toBe(
      "keep my work",
    );
    expect(wrapper.text()).not.toContain("当前页面权限已失效");
    api.access.mockResolvedValue({
      project_id: "p",
      roles: ["project_executor"],
      permissions: ["project.runtime.read"],
    });
    await store.refreshCurrentProjectAccess();
    await nextTick();
    expect(wrapper.find("input").exists()).toBe(false);
    expect(wrapper.text()).toContain("当前页面权限已失效");
  } finally {
    wrapper.unmount();
  }
});

it("shows a recoverable connection state for an unknown snapshot and recovers on retry", async () => {
  const store = useWorkspaceStore();
  api.access.mockRejectedValue(new Error("offline"));
  await expect(store.setProjectId("p")).rejects.toThrow();
  const wrapper = mount(WorkspaceLayout, {
    global: {
      plugins: [getActivePinia()!],
      stubs: { "router-view": { template: "<input />" }, RouterLink: true },
    },
  });
  try {
    expect(wrapper.text()).toContain("暂时无法确认访问权限");
    expect(wrapper.text()).not.toContain("当前页面权限已失效");
    api.access.mockResolvedValue({
      project_id: "p",
      roles: ["project_editor"],
      permissions: ["project.assistant.write"],
    });
    await wrapper.get("button").trigger("click");
    await flushPromises();
    expect(wrapper.find("input").exists()).toBe(true);
  } finally {
    wrapper.unmount();
  }
});

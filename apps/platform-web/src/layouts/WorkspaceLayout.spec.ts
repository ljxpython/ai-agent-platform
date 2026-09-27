import { mount, flushPromises } from "@vue/test-utils";
import { createPinia } from "pinia";
import { nextTick } from "vue";
import { useRoute } from "vue-router";
import { afterEach, expect, it, vi } from "vitest";
import ChatSessionPool from "@/modules/chat/components/ChatSessionPool.vue";

const { refreshProject, refreshUser, routeState } = vi.hoisted(() => ({
  refreshProject: vi.fn(),
  refreshUser: vi.fn(),
  routeState: {
    name: "workspace-chat",
    params: { projectId: "p1" },
    meta: { immersive: true },
  },
}));
vi.mock("vue-router", async () => {
  const { reactive } = await import("vue");
  return { useRoute: () => reactive(routeState) };
});
vi.mock("@/stores/auth", () => ({
  useAuthStore: () => ({ sessionEpoch: 1, fetchCurrentUser: refreshUser }),
}));
vi.mock("@/stores/workspace", () => ({
  useWorkspaceStore: () => ({ refreshCurrentProjectAccess: refreshProject }),
}));
vi.mock("@/composables/useAuthorization", () => ({
  useAuthorization: () => ({ can: () => true }),
}));
vi.mock("@/components/layout/AppSidebar.vue", () => ({
  default: { template: "<aside />" },
}));
vi.mock("@/components/layout/TopContextBar.vue", () => ({
  default: { template: "<header />" },
}));
import WorkspaceLayout from "./WorkspaceLayout.vue";

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

it("clears the session pool when the project scope changes", async () => {
  const wrapper = mount(WorkspaceLayout, {
    global: {
      plugins: [createPinia()],
      stubs: {
        AppSidebar: true,
        TopContextBar: true,
        "router-view": true,
        RouterLink: true,
        StateBanner: true,
      },
    },
  });
  try {
    const pool = wrapper.findComponent(ChatSessionPool).props("pool");
    const clear = vi.spyOn(pool, "clearScope");
    useRoute().params.projectId = "p2";
    await nextTick();
    expect(clear).toHaveBeenCalledTimes(1);
  } finally {
    wrapper.unmount();
    useRoute().params.projectId = "p1";
  }
});

it("refreshes immersive pages every 60 seconds, on activation and rejection, and removes listeners", async () => {
  vi.useFakeTimers();
  refreshProject.mockResolvedValue(undefined);
  refreshUser.mockResolvedValue(undefined);
  const visibility = vi
    .spyOn(document, "visibilityState", "get")
    .mockReturnValue("visible");
  const wrapper = mount(WorkspaceLayout, {
    global: {
      plugins: [createPinia()],
      stubs: {
        AppSidebar: true,
        TopContextBar: true,
        "router-view": true,
        RouterLink: true,
        StateBanner: true,
      },
    },
  });
  await vi.advanceTimersByTimeAsync(60_000);
  expect(refreshProject).toHaveBeenCalledTimes(1);
  expect(refreshUser).toHaveBeenCalledTimes(1);
  visibility.mockReturnValue("hidden");
  await vi.advanceTimersByTimeAsync(60_000);
  expect(refreshProject).toHaveBeenCalledTimes(1);
  visibility.mockReturnValue("visible");
  document.dispatchEvent(new Event("visibilitychange"));
  await flushPromises();
  window.dispatchEvent(new Event("platform-access-denied"));
  await flushPromises();
  window.dispatchEvent(new Event("focus"));
  await flushPromises();
  expect(refreshProject).toHaveBeenCalledTimes(4);
  wrapper.unmount();
  await vi.advanceTimersByTimeAsync(60_000);
  window.dispatchEvent(new Event("platform-access-denied"));
  window.dispatchEvent(new Event("focus"));
  expect(refreshProject).toHaveBeenCalledTimes(4);
});

import { beforeEach, describe, expect, it, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";
import RunNotificationCenter from "./RunNotificationCenter.vue";
import { useRunNotificationsStore } from "@/stores/run-notifications";
import { useChatSessionStore } from "@/modules/chat/stores/useChatSessionStore";

import * as notificationService from "@/services/run-notifications/run-notifications.service";

vi.mock("@/services/run-notifications/run-notifications.service", () => ({
  getRunNotifications: vi.fn(),
  readRunNotification: vi.fn(),
}));

const mockPush = vi.fn();
vi.mock("vue-router", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

vi.mock("@/composables/useWorkspaceProjectContext", () => ({
  useWorkspaceProjectContext: () => ({
    activeProjectId: { value: "project-123" },
  }),
}));

describe("RunNotificationCenter.vue", () => {
  let pinia: ReturnType<typeof createPinia>;

  const mockItem = {
    event_id: "fbdd4f98-6a68-42ec-b1a4-af04d5ee0688",
    graph_id: "demo_agent",
    status: "error" as const,
    reason: "business_error" as const,
    reason_code: "runtime.model.retry_exhausted" as const,
    model_error_code: "provider_overloaded" as const,
    notification_code: "run_failed_provider_overloaded" as const,
    occurred_at: "2026-10-09T04:55:16.057288Z",
    can_mark_read: true,
    read_at: null,
    thread_id: "58060265-5ef7-42b4-9acf-e316a867f3ab",
    run_id: "16c7d922-084d-4d85-91a1-8df5c8b0b129",
    received_at: "2026-10-09T04:55:16.233518Z",
  };

  beforeEach(() => {
    pinia = createPinia();
    setActivePinia(pinia);
    vi.clearAllMocks();

    vi.mocked(notificationService.getRunNotifications).mockResolvedValue({
      version: 1,
      availability: "available",
      items: [mockItem],
      next_cursor: null,
      scan_limit_reached: false,
      request_id: "req_feed",
    });
  });

  it("当有未读通知时，正确展示未读红点角标", async () => {
    const wrapper = mount(RunNotificationCenter, {
      global: {
        plugins: [pinia],
        stubs: {
          BaseIcon: true,
          BaseButton: true,
          BaseDialog: true,
          Teleport: true,
        },
      },
    });

    await vi.waitFor(() => {
      const badge = wrapper.find("[data-testid='notification-unread-badge']");
      expect(badge.exists()).toBe(true);
      expect(badge.text()).toBe("1");
    });
  });

  it("点击打开下拉面板，展示细粒度原因并支持点击查看会话", async () => {
    const store = useRunNotificationsStore();
    store.items = [mockItem];
    store.unreadCount = 1;

    const chatStore = useChatSessionStore();
    chatStore.isRunning = false;

    const wrapper = mount(RunNotificationCenter, {
      global: {
        plugins: [pinia],
        stubs: {
          BaseIcon: true,
          BaseButton: {
            template: "<button><slot /></button>",
          },
          BaseDialog: true,
          Teleport: {
            template: "<div><slot /></div>",
          },
        },
      },
    });

    // 点击铃铛按钮打开下拉
    const trigger = wrapper.find("button.pw-topbar-action");
    await trigger.trigger("click");

    expect(wrapper.text()).toContain("模型服务繁忙");

    // 点击查看会话
    const viewBtn = wrapper.find("[data-testid='view-thread-button']");
    expect(viewBtn.exists()).toBe(true);
    await viewBtn.trigger("click");

    expect(mockPush).toHaveBeenCalledWith({
      name: "chat",
      query: {
        thread_id: mockItem.thread_id,
        run_id: mockItem.run_id,
      },
    });
  });

  it("当会话正在运行中 (isChatExecuting === true) 时，点击查看会话弹出二次确认", async () => {
    const store = useRunNotificationsStore();
    store.items = [mockItem];
    store.unreadCount = 1;
    store.isChatExecuting = true; // 正在运行中！

    const wrapper = mount(RunNotificationCenter, {
      global: {
        plugins: [pinia],
        stubs: {
          BaseIcon: true,
          BaseButton: {
            template: "<button><slot /></button>",
          },
          BaseDialog: {
            props: ["show"],
            template:
              '<div v-if="show" data-testid="dialog-leave"><slot /></div>',
          },
          Teleport: {
            template: "<div><slot /></div>",
          },
        },
      },
    });

    // 打开下拉
    await wrapper.find("button.pw-topbar-action").trigger("click");

    // 点击查看会话
    const viewBtn = wrapper.find("[data-testid='view-thread-button']");
    await viewBtn.trigger("click");

    // 严禁立即直接路由跳转！
    expect(mockPush).not.toHaveBeenCalled();

    // 弹出确认对话框！
    const dialog = wrapper.find("[data-testid='dialog-leave']");
    expect(dialog.exists()).toBe(true);
    expect(dialog.text()).toContain("当前会话正在执行 Agent 任务中");
  });
});

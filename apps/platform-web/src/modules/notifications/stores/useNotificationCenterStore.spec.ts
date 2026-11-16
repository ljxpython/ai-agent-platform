import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { useNotificationCenterStore } from "./useNotificationCenterStore";
import * as api from "../api";
import type { NotificationItem, NotificationPage } from "../types";

vi.mock("../api", () => ({
  fetchNotifications: vi.fn(),
  fetchUnreadCount: vi.fn(),
  markNotificationRead: vi.fn(),
  markAllNotificationsRead: vi.fn(),
  fetchChannels: vi.fn(),
  createChannel: vi.fn(),
  updateChannel: vi.fn(),
  deleteChannel: vi.fn(),
  testChannel: vi.fn(),
}));

describe("useNotificationCenterStore", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it("初始化状态正常", () => {
    const store = useNotificationCenterStore();
    expect(store.items).toEqual([]);
    expect(store.unreadCount).toBe(0);
    expect(store.channels).toEqual([]);
  });

  it("fetchFeed 能正确拉取消息列表与未读数", async () => {
    const mockPage: NotificationPage = {
      items: [
        {
          id: "notif-1",
          recipient_user_id: null,
          project_id: null,
          title: "DeepSeek 429 告警",
          content: "调用触发限流",
          level: "critical",
          category: "system",
          status: "unread",
          action_url: "/workspace",
          extra_metadata: {},
          created_at: new Date().toISOString(),
          read_at: null,
        },
      ],
      total: 1,
      unread_count: 1,
      limit: 30,
      offset: 0,
    };
    vi.mocked(api.fetchNotifications).mockResolvedValueOnce(mockPage);

    const store = useNotificationCenterStore();
    await store.fetchFeed();

    expect(store.items).toHaveLength(1);
    expect(store.items[0].title).toBe("DeepSeek 429 告警");
    expect(store.unreadCount).toBe(1);
  });

  it("markRead 能乐观将未读标记为已读并扣减计数", async () => {
    const store = useNotificationCenterStore();
    store.items = [
      {
        id: "notif-1",
        recipient_user_id: null,
        project_id: null,
        title: "测试",
        content: "内容",
        level: "warning",
        category: "system",
        status: "unread",
        action_url: null,
        extra_metadata: {},
        created_at: new Date().toISOString(),
        read_at: null,
      },
    ];
    store.unreadCount = 1;

    vi.mocked(api.markNotificationRead).mockResolvedValueOnce(undefined);
    await store.markRead("notif-1");

    expect(store.items[0].status).toBe("read");
    expect(store.unreadCount).toBe(0);
    expect(api.markNotificationRead).toHaveBeenCalledWith("notif-1");
  });

  it("markAllRead 能批量将所有项变更为已读", async () => {
    const store = useNotificationCenterStore();
    store.items = [
      {
        id: "1",
        recipient_user_id: null,
        project_id: null,
        title: "A",
        content: "",
        level: "info",
        category: "system",
        status: "unread",
        action_url: null,
        extra_metadata: {},
        created_at: "",
        read_at: null,
      },
      {
        id: "2",
        recipient_user_id: null,
        project_id: null,
        title: "B",
        content: "",
        level: "info",
        category: "system",
        status: "unread",
        action_url: null,
        extra_metadata: {},
        created_at: "",
        read_at: null,
      },
    ];
    store.unreadCount = 2;

    vi.mocked(api.markAllNotificationsRead).mockResolvedValueOnce(2);
    await store.markAllRead();

    expect(store.items.every((i) => i.status === "read")).toBe(true);
    expect(store.unreadCount).toBe(0);
  });

  it("runTestChannel 能调用 API 并返回结果", async () => {
    const store = useNotificationCenterStore();
    vi.mocked(api.testChannel).mockResolvedValueOnce({
      success: true,
      channel_id: "ch-1",
      channel_name: "飞书测试群",
      message: "发送成功",
    });

    const res = await store.runTestChannel("ch-1");
    expect(res.success).toBe(true);
    expect(res.channel_name).toBe("飞书测试群");
    expect(api.testChannel).toHaveBeenCalledWith("ch-1");
  });
});

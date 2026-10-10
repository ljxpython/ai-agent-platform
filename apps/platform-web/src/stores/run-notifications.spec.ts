import { beforeEach, describe, expect, it, vi } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useRunNotificationsStore } from "./run-notifications";
import * as notificationService from "@/services/run-notifications/run-notifications.service";

vi.mock("@/services/run-notifications/run-notifications.service", () => ({
  getRunNotifications: vi.fn(),
  readRunNotification: vi.fn(),
}));

describe("run-notifications store", () => {
  const projectId = "project-123";
  const eventId = "fbdd4f98-6a68-42ec-b1a4-af04d5ee0688";
  const threadId = "58060265-5ef7-42b4-9acf-e316a867f3ab";
  const runId = "16c7d922-084d-4d85-91a1-8df5c8b0b129";

  const mockNotificationItem = {
    event_id: eventId,
    graph_id: "agent_a",
    status: "error" as const,
    reason: "business_error" as const,
    reason_code: "runtime_execution_failed" as const,
    model_error_code: null,
    notification_code: "run_failed" as const,
    occurred_at: "2026-10-09T04:55:16.057288Z",
    can_mark_read: true,
    read_at: null,
    thread_id: threadId,
    run_id: runId,
    received_at: "2026-10-09T04:55:16.233518Z",
  };

  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it("初始状态正确", () => {
    const store = useRunNotificationsStore();
    expect(store.items).toEqual([]);
    expect(store.unreadCount).toBe(0);
    expect(store.isPolling).toBe(false);
    expect(store.availability).toBe("available");
  });

  it("启动轮询并成功拉取第一页数据，正确计算未读数", async () => {
    vi.mocked(notificationService.getRunNotifications).mockResolvedValueOnce({
      version: 1,
      availability: "available",
      items: [mockNotificationItem],
      next_cursor: "cursor_1",
      scan_limit_reached: false,
      request_id: "req_1",
    });

    const store = useRunNotificationsStore();
    store.startPolling(projectId);

    expect(store.isPolling).toBe(true);
    // 等待异步拉取完成
    await vi.waitFor(() => {
      expect(store.items).toHaveLength(1);
    });

    expect(store.unreadCount).toBe(1);
    expect(store.items[0].event_id).toBe(eventId);
    expect(store.nextCursor).toBe("cursor_1");
    store.stopPolling();
  });

  it("当 availability 为 disabled 时清空数据并终止轮询", async () => {
    vi.mocked(notificationService.getRunNotifications).mockResolvedValueOnce({
      version: 1,
      availability: "disabled",
      items: [],
      next_cursor: null,
      scan_limit_reached: false,
      request_id: "req_disabled",
    });

    const store = useRunNotificationsStore();
    store.startPolling(projectId);

    await vi.waitFor(() => {
      expect(store.availability).toBe("disabled");
    });

    expect(store.items).toEqual([]);
    expect(store.unreadCount).toBe(0);
    expect(store.isPolling).toBe(false);
  });

  it("乐观标记已读成功", async () => {
    const store = useRunNotificationsStore();
    store.items = [{ ...mockNotificationItem }];
    store.unreadCount = 1;
    store.activeProjectId = projectId;

    vi.mocked(notificationService.readRunNotification).mockResolvedValueOnce({
      version: 1,
      event_id: eventId,
      read_at: "2026-10-09T05:00:00.000000Z",
      request_id: "req_read",
    });

    const ok = await store.markAsRead(eventId);
    expect(ok).toBe(true);
    expect(store.unreadCount).toBe(0);
    expect(store.items[0].read_at).toBeTruthy();
  });

  it("乐观标记已读失败时回滚状态与未读计数", async () => {
    const store = useRunNotificationsStore();
    store.items = [{ ...mockNotificationItem }];
    store.unreadCount = 1;
    store.activeProjectId = projectId;

    vi.mocked(notificationService.readRunNotification).mockRejectedValueOnce(
      new Error("网络中断 503"),
    );

    await expect(store.markAsRead(eventId)).rejects.toThrow("网络中断 503");

    // 状态必须回滚！
    expect(store.items[0].read_at).toBeNull();
    expect(store.unreadCount).toBe(1);
  });

  it("加载更多历史时追加数据并去重", async () => {
    const store = useRunNotificationsStore();
    store.items = [{ ...mockNotificationItem }];
    store.nextCursor = "cursor_1";
    store.activeProjectId = projectId;

    const secondItem = {
      ...mockNotificationItem,
      event_id: "aaaaaaaa-2222-3333-4444-555555555555",
      run_id: "bbbbbbbb-2222-3333-4444-555555555555",
    };

    vi.mocked(notificationService.getRunNotifications).mockResolvedValueOnce({
      version: 1,
      availability: "available",
      items: [secondItem],
      next_cursor: null,
      scan_limit_reached: false,
      request_id: "req_more",
    });

    await store.loadMore();

    expect(store.items).toHaveLength(2);
    expect(store.nextCursor).toBeNull();
  });

  describe("在线去重与提示抑制判定 (借鉴 open-swe)", () => {
    it("页面在前台且正在查看当前活跃失败会话且SDK已报错时抑制Toast", () => {
      const store = useRunNotificationsStore();

      // 前台 visible
      Object.defineProperty(document, "visibilityState", {
        configurable: true,
        get: () => "visible",
      });

      const shouldSuppress = store.shouldSuppressToast(
        threadId,
        runId,
        threadId, // activeThreadId 等于 threadId
        true, // SDK 已经报错
      );
      expect(shouldSuppress).toBe(true);
    });

    it("页面在后台 hidden 时即使停留在此会话也不抑制提示（防止静音漏报）", () => {
      const store = useRunNotificationsStore();

      // 后台 hidden
      Object.defineProperty(document, "visibilityState", {
        configurable: true,
        get: () => "hidden",
      });

      const shouldSuppress = store.shouldSuppressToast(
        threadId,
        runId,
        threadId,
        true,
      );
      expect(shouldSuppress).toBe(false);
    });

    it("同一 Run 已经被记录通告后予以抑制", () => {
      const store = useRunNotificationsStore();
      store.recordRunNotified(runId);

      expect(
        store.hasRunNotified?.(runId) ?? store.notifiedRunIds.has(runId),
      ).toBe(true);
      expect(
        store.shouldSuppressToast(threadId, runId, "different_thread", false),
      ).toBe(true);
    });
  });
});

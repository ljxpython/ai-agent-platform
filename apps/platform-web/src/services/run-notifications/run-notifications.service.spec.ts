import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  getRunNotifications,
  readRunNotification,
} from "./run-notifications.service";
import { platformHttpClient } from "@/services/http/client";

vi.mock("@/services/http/client", () => ({
  platformHttpClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

describe("run-notifications.service", () => {
  const projectId = "project-test-123";
  const eventId = "fbdd4f98-6a68-42ec-b1a4-af04d5ee0688";

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("getRunNotifications", () => {
    it("正确传递分页与未读筛选参数并解析响应", async () => {
      const mockFeed = {
        version: 1,
        availability: "available",
        items: [
          {
            event_id: eventId,
            graph_id: "test_graph",
            status: "error",
            reason: "business_error",
            reason_code: "runtime_execution_failed",
            model_error_code: null,
            notification_code: "run_failed",
            occurred_at: "2026-10-09T04:55:16.057288Z",
            can_mark_read: true,
            read_at: null,
            thread_id: "58060265-5ef7-42b4-9acf-e316a867f3ab",
            run_id: "16c7d922-084d-4d85-91a1-8df5c8b0b129",
            received_at: "2026-10-09T04:55:16.233518Z",
          },
        ],
        next_cursor: "cursor_abc",
        scan_limit_reached: false,
        request_id: "req_feed",
      };

      vi.mocked(platformHttpClient.get).mockResolvedValueOnce({
        data: mockFeed,
        status: 200,
      });

      const res = await getRunNotifications({
        projectId,
        limit: 10,
        unreadOnly: true,
      });

      expect(platformHttpClient.get).toHaveBeenCalledWith(
        "/api/runtime/run-notifications",
        {
          headers: { "x-project-id": projectId },
          params: { limit: 10, unread_only: true },
          signal: undefined,
        },
      );
      expect(res.items).toHaveLength(1);
      expect(res.next_cursor).toBe("cursor_abc");
    });
  });

  describe("readRunNotification", () => {
    it("成功发送已读回执并验证返回的 event_id", async () => {
      const mockReceipt = {
        version: 1,
        event_id: eventId,
        read_at: "2026-10-09T04:55:20.000000Z",
        request_id: "req_receipt",
      };

      vi.mocked(platformHttpClient.post).mockResolvedValueOnce({
        data: mockReceipt,
        status: 200,
      });

      const res = await readRunNotification(eventId, { projectId });

      expect(platformHttpClient.post).toHaveBeenCalledWith(
        `/api/runtime/run-notifications/${encodeURIComponent(eventId)}/read`,
        {},
        {
          headers: { "x-project-id": projectId },
          signal: undefined,
        },
      );
      expect(res.event_id).toBe(eventId);
    });

    it("空 eventId 拦截", async () => {
      await expect(readRunNotification("")).rejects.toThrow("不能为空");
    });

    it("返回 event_id 不匹配时报错", async () => {
      vi.mocked(platformHttpClient.post).mockResolvedValueOnce({
        data: {
          version: 1,
          event_id: "11111111-2222-3333-4444-555555555555",
          read_at: "2026-10-09T04:55:20.000000Z",
          request_id: "req_receipt",
        },
        status: 200,
      });

      await expect(readRunNotification(eventId)).rejects.toThrow(
        "已读回执事件编号与请求不匹配",
      );
    });
  });
});

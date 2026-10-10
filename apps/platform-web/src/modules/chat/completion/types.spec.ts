import { describe, it, expect } from "vitest";
import {
  safeParseCompletionResponse,
  safeParseNotificationFeedResponse,
  safeParseReadReceiptResponse,
} from "./types";

describe("Completion & Notification DTO Schemas", () => {
  it("成功解析合法 available completion 响应", () => {
    const raw = {
      version: 1,
      thread_id: "5752312c-5893-4ba9-914e-d4b7748f42b8",
      run_id: "cf4d5956-c579-459d-a106-1c3fb05a639a",
      availability: "available",
      completion: {
        event_id: "354bd564-c2b7-4d38-b538-f53f53a8d37a",
        graph_id: "reference_agent",
        status: "success",
        reason: "completed",
        reason_code: null,
        model_error_code: null,
        notification_code: null,
        occurred_at: "2026-10-09T04:52:44.707165Z",
        can_mark_read: false,
        read_at: null,
      },
      request_id: "req_123456",
    };

    const parsed = safeParseCompletionResponse(raw);
    expect(parsed.success).toBe(true);
    if (parsed.success) {
      expect(parsed.data.availability).toBe("available");
      expect(parsed.data.completion.status).toBe("success");
    }
  });

  it("当 version 字段缺失时自动补充默认值 1", () => {
    const raw = {
      thread_id: "5752312c-5893-4ba9-914e-d4b7748f42b8",
      run_id: "cf4d5956-c579-459d-a106-1c3fb05a639a",
      availability: "pending",
      completion: null,
      request_id: "req_def_ver",
    };

    const parsed = safeParseCompletionResponse(raw);
    expect(parsed.success).toBe(true);
    if (parsed.success) {
      expect(parsed.data.version).toBe(1);
      expect(parsed.data.availability).toBe("pending");
      expect(parsed.data.completion).toBeNull();
    }
  });

  it("当 availability 为 available 但 completion 为 null 时校验失败", () => {
    const raw = {
      version: 1,
      thread_id: "5752312c-5893-4ba9-914e-d4b7748f42b8",
      run_id: "cf4d5956-c579-459d-a106-1c3fb05a639a",
      availability: "available",
      completion: null,
      request_id: "req_err",
    };

    const parsed = safeParseCompletionResponse(raw);
    expect(parsed.success).toBe(false);
  });

  it("成功解析带有细粒度错误码的 NotificationFeedResponse", () => {
    const raw = {
      version: 1,
      availability: "available",
      items: [
        {
          event_id: "fbdd4f98-6a68-42ec-b1a4-af04d5ee0688",
          graph_id: "reference_agent",
          status: "error",
          reason: "business_error",
          reason_code: "runtime.model.retry_exhausted",
          model_error_code: "provider_overloaded",
          notification_code: "run_failed_provider_overloaded",
          occurred_at: "2026-10-09T04:55:16.057288Z",
          can_mark_read: true,
          read_at: null,
          thread_id: "58060265-5ef7-42b4-9acf-e316a867f3ab",
          run_id: "16c7d922-084d-4d85-91a1-8df5c8b0b129",
          received_at: "2026-10-09T04:55:16.233518Z",
        },
      ],
      next_cursor: null,
      scan_limit_reached: false,
      request_id: "req_feed_1",
    };

    const parsed = safeParseNotificationFeedResponse(raw);
    expect(parsed.success).toBe(true);
    if (parsed.success) {
      expect(parsed.data.items).toHaveLength(1);
      expect(parsed.data.items[0].model_error_code).toBe("provider_overloaded");
    }
  });

  it("成功解析 ReadReceiptResponse", () => {
    const raw = {
      version: 1,
      event_id: "fbdd4f98-6a68-42ec-b1a4-af04d5ee0688",
      read_at: "2026-10-09T04:55:16.690383Z",
      request_id: "req_read_1",
    };

    const parsed = safeParseReadReceiptResponse(raw);
    expect(parsed.success).toBe(true);
    if (parsed.success) {
      expect(parsed.data.event_id).toBe("fbdd4f98-6a68-42ec-b1a4-af04d5ee0688");
    }
  });

  it("未知 extra 字段或非法 UUID 时拒绝解析", () => {
    const raw = {
      version: 1,
      event_id: "not-a-valid-uuid",
      read_at: "2026-10-09T04:55:16.690383Z",
      request_id: "req_bad",
    };

    const parsed = safeParseReadReceiptResponse(raw);
    expect(parsed.success).toBe(false);
  });
});

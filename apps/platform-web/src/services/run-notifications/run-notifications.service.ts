import { platformHttpClient } from "@/services/http/client";
import {
  safeParseNotificationFeedResponse,
  safeParseReadReceiptResponse,
  type NotificationFeedResponse,
  type ReadReceiptResponse,
} from "@/modules/chat/completion/types";
import { extractPlatformHttpError } from "@/utils/http-error";

export interface GetRunNotificationsOptions {
  projectId?: string;
  limit?: number;
  cursor?: string | null;
  unreadOnly?: boolean;
  signal?: AbortSignal;
}

export interface ReadRunNotificationOptions {
  projectId?: string;
  signal?: AbortSignal;
}

/**
 * 获取当前用户在当前项目下的运行通知 Feed
 * 接口：GET /api/runtime/run-notifications
 */
export async function getRunNotifications(
  options: GetRunNotificationsOptions = {},
): Promise<NotificationFeedResponse> {
  const headers: Record<string, string> = {};
  if (options.projectId) {
    headers["x-project-id"] = options.projectId;
  }

  const params: Record<string, string | number | boolean> = {};
  if (typeof options.limit === "number") {
    params.limit = options.limit;
  }
  if (options.cursor) {
    params.cursor = options.cursor;
  }
  if (typeof options.unreadOnly === "boolean") {
    params.unread_only = options.unreadOnly;
  }

  try {
    const response = await platformHttpClient.get<unknown>(
      "/api/runtime/run-notifications",
      {
        headers,
        params,
        signal: options.signal,
      },
    );

    const parsed = safeParseNotificationFeedResponse(response.data);
    if (!parsed.success) {
      throw Object.assign(
        new Error(
          `运行通知列表格式校验失败: ${parsed.errorMessage || "未知格式"}`,
        ),
        { code: "invalid_run_notifications_dto" },
      );
    }

    return parsed.data;
  } catch (error) {
    if (options.signal?.aborted) {
      throw error;
    }
    const fields = extractPlatformHttpError(error, "获取运行通知失败");
    const enhancedError = new Error(fields.message || "获取运行通知失败");
    Object.assign(enhancedError, {
      status: fields.status,
      code: fields.code,
      requestId: fields.requestId,
      details: fields.details,
      cancelled: fields.cancelled,
    });
    throw enhancedError;
  }
}

/**
 * 将指定通知标记为已读（幂等）
 * 接口：POST /api/runtime/run-notifications/{event_id}/read
 */
export async function readRunNotification(
  eventId: string,
  options: ReadRunNotificationOptions = {},
): Promise<ReadReceiptResponse> {
  const trimmedEventId = (eventId || "").trim();
  if (!trimmedEventId) {
    throw new Error("eventId 不能为空");
  }

  const headers: Record<string, string> = {};
  if (options.projectId) {
    headers["x-project-id"] = options.projectId;
  }

  try {
    const url = `/api/runtime/run-notifications/${encodeURIComponent(trimmedEventId)}/read`;
    const response = await platformHttpClient.post<unknown>(
      url,
      {},
      {
        headers,
        signal: options.signal,
      },
    );

    const parsed = safeParseReadReceiptResponse(response.data);
    if (!parsed.success) {
      throw Object.assign(
        new Error(`已读回执格式校验失败: ${parsed.errorMessage || "未知格式"}`),
        { code: "invalid_read_receipt_dto" },
      );
    }

    if (parsed.data.event_id !== trimmedEventId) {
      throw Object.assign(new Error("已读回执事件编号与请求不匹配"), {
        code: "mismatched_read_receipt_target",
      });
    }

    return parsed.data;
  } catch (error) {
    if (options.signal?.aborted) {
      throw error;
    }
    const fields = extractPlatformHttpError(error, "标记通知已读失败");
    const enhancedError = new Error(fields.message || "标记通知已读失败");
    Object.assign(enhancedError, {
      status: fields.status,
      code: fields.code,
      requestId: fields.requestId,
      details: fields.details,
      cancelled: fields.cancelled,
    });
    throw enhancedError;
  }
}

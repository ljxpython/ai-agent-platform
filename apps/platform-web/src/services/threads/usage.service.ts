import { platformHttpClient } from "@/services/http/client";
import {
  safeParseRunUsage,
  safeParseThreadUsage,
  type RunUsageV1,
  type ThreadUsageV1,
} from "@/modules/chat/usage/types";
import { extractPlatformHttpError } from "@/utils/http-error";

export interface GetRunUsageOptions {
  projectId?: string;
  limit?: number;
  cursor?: string | null;
  signal?: AbortSignal;
}

export interface GetThreadUsageOptions {
  projectId?: string;
  createdFrom?: string | null;
  createdTo?: string | null;
  signal?: AbortSignal;
}

/**
 * 查询指定 Run 的用量与估算成本（包含分页调用明细）
 * 接口：GET /api/langgraph/threads/{thread_id}/runs/{run_id}/usage
 */
export async function getRunUsage(
  threadId: string,
  runId: string,
  options: GetRunUsageOptions = {},
): Promise<RunUsageV1> {
  const trimmedThreadId = (threadId || "").trim();
  const trimmedRunId = (runId || "").trim();

  if (!trimmedThreadId || !trimmedRunId) {
    throw new Error("threadId 和 runId 不能为空");
  }

  const headers: Record<string, string> = {};
  if (options.projectId?.trim()) {
    headers["x-project-id"] = options.projectId.trim();
  }

  const params: Record<string, string | number> = {};
  if (typeof options.limit === "number" && options.limit > 0) {
    params.limit = Math.min(Math.max(options.limit, 1), 200);
  }
  if (options.cursor && options.cursor.trim()) {
    params.cursor = options.cursor.trim();
  }

  try {
    const url = `/api/langgraph/threads/${encodeURIComponent(trimmedThreadId)}/runs/${encodeURIComponent(trimmedRunId)}/usage`;
    const response = await platformHttpClient.get<unknown>(url, {
      headers,
      params,
      signal: options.signal,
    });

    const parsed = safeParseRunUsage(response.data);
    if (!parsed.success || !parsed.data) {
      throw Object.assign(
        new Error(`用量格式校验失败: ${parsed.errorMessage || "未知格式"}`),
        { code: "invalid_usage_dto" },
      );
    }

    // 目标编号一致性核验
    if (
      parsed.data.thread_id !== trimmedThreadId ||
      parsed.data.run_id !== trimmedRunId
    ) {
      throw Object.assign(new Error("用量响应编号与当前目标不匹配"), {
        code: "mismatched_usage_target",
      });
    }

    return parsed.data;
  } catch (error) {
    if (options.signal?.aborted) {
      throw error;
    }
    const fields = extractPlatformHttpError(error, "查询 Run 用量失败");
    const enhancedError = new Error(fields.message || "查询 Run 用量失败");
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
 * 查询指定 Thread 的累计用量与估算成本（全部已采集原生 Run 聚合）
 * 接口：GET /api/langgraph/threads/{thread_id}/usage
 */
export async function getThreadUsage(
  threadId: string,
  options: GetThreadUsageOptions = {},
): Promise<ThreadUsageV1> {
  const trimmedThreadId = (threadId || "").trim();

  if (!trimmedThreadId) {
    throw new Error("threadId 不能为空");
  }

  const headers: Record<string, string> = {};
  if (options.projectId?.trim()) {
    headers["x-project-id"] = options.projectId.trim();
  }

  const params: Record<string, string> = {};
  // 严格契约：created_from 与 created_to 必须两者同时有效才传递，严禁传空字符串 query
  if (options.createdFrom?.trim() && options.createdTo?.trim()) {
    params.created_from = options.createdFrom.trim();
    params.created_to = options.createdTo.trim();
  }

  try {
    const url = `/api/langgraph/threads/${encodeURIComponent(trimmedThreadId)}/usage`;
    const response = await platformHttpClient.get<unknown>(url, {
      headers,
      params,
      signal: options.signal,
    });

    const parsed = safeParseThreadUsage(response.data);
    if (!parsed.success || !parsed.data) {
      throw Object.assign(
        new Error(
          `Thread 用量格式校验失败: ${parsed.errorMessage || "未知格式"}`,
        ),
        { code: "invalid_thread_usage_dto" },
      );
    }

    if (parsed.data.thread_id !== trimmedThreadId) {
      throw Object.assign(new Error("Thread 用量响应编号与当前目标不匹配"), {
        code: "mismatched_thread_usage_target",
      });
    }

    return parsed.data;
  } catch (error) {
    if (options.signal?.aborted) {
      throw error;
    }
    const fields = extractPlatformHttpError(error, "查询 Thread 用量失败");
    const enhancedError = new Error(fields.message || "查询 Thread 用量失败");
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

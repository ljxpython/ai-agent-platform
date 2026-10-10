import { platformHttpClient } from "@/services/http/client";
import {
  safeParseCompletionResponse,
  type CompletionResponse,
} from "@/modules/chat/completion/types";
import { extractPlatformHttpError } from "@/utils/http-error";

export interface GetRunCompletionOptions {
  projectId?: string;
  signal?: AbortSignal;
}

/**
 * 查询指定 Run 的安全终态摘要（completion）
 * 接口：GET /api/langgraph/threads/{thread_id}/runs/{run_id}/completion
 */
export async function getRunCompletion(
  threadId: string,
  runId: string,
  options: GetRunCompletionOptions = {},
): Promise<CompletionResponse> {
  const trimmedThreadId = (threadId || "").trim();
  const trimmedRunId = (runId || "").trim();

  if (!trimmedThreadId || !trimmedRunId) {
    throw new Error("threadId 和 runId 不能为空");
  }

  const headers: Record<string, string> = {};
  if (options.projectId) {
    headers["x-project-id"] = options.projectId;
  }

  try {
    const url = `/api/langgraph/threads/${encodeURIComponent(trimmedThreadId)}/runs/${encodeURIComponent(trimmedRunId)}/completion`;
    const response = await platformHttpClient.get<unknown>(url, {
      headers,
      signal: options.signal,
    });

    const parsed = safeParseCompletionResponse(response.data);
    if (!parsed.success) {
      throw Object.assign(
        new Error(`终态摘要格式校验失败: ${parsed.errorMessage || "未知格式"}`),
        { code: "invalid_completion_dto" },
      );
    }

    // 核验返回的 thread_id 和 run_id 是否与请求一致
    if (
      parsed.data.thread_id !== trimmedThreadId ||
      parsed.data.run_id !== trimmedRunId
    ) {
      throw Object.assign(new Error("终态摘要响应目标与请求不匹配"), {
        code: "mismatched_completion_target",
      });
    }

    return parsed.data;
  } catch (error) {
    if (options.signal?.aborted) {
      throw error;
    }
    const fields = extractPlatformHttpError(error, "查询运行终态摘要失败");
    const enhancedError = new Error(fields.message || "查询运行终态摘要失败");
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

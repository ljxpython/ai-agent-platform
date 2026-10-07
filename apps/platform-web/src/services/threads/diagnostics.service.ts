import { platformHttpClient } from "@/services/http/client";
import {
  safeParseRunDiagnostics,
  type RunDiagnosticsV1,
} from "@/modules/chat/diagnostics/types";
import { extractPlatformHttpError } from "@/utils/http-error";

export interface GetRunDiagnosticsOptions {
  projectId?: string;
  signal?: AbortSignal;
}

/**
 * 查询指定 Run 的安全诊断摘要
 * 接口：GET /api/langgraph/threads/{thread_id}/runs/{run_id}/diagnostics
 */
export async function getRunDiagnostics(
  threadId: string,
  runId: string,
  options: GetRunDiagnosticsOptions = {},
): Promise<RunDiagnosticsV1> {
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
    const url = `/api/langgraph/threads/${encodeURIComponent(trimmedThreadId)}/runs/${encodeURIComponent(trimmedRunId)}/diagnostics`;
    const response = await platformHttpClient.get<unknown>(url, {
      headers,
      signal: options.signal,
    });

    const parsed = safeParseRunDiagnostics(response.data);
    if (!parsed.success || !parsed.data) {
      throw Object.assign(
        new Error(`诊断格式校验失败: ${parsed.errorMessage || "未知格式"}`),
        {
          code: "invalid_diagnostics_dto",
        },
      );
    }

    // 核验返回的 thread_id 和 run_id 是否与请求一致
    if (
      parsed.data.thread_id !== trimmedThreadId ||
      parsed.data.run_id !== trimmedRunId
    ) {
      throw Object.assign(new Error("诊断响应编号与当前目标不匹配"), {
        code: "mismatched_diagnostics_target",
      });
    }

    return parsed.data;
  } catch (error) {
    // 若已被 signal 取消，直接透传原异常
    if (options.signal?.aborted) {
      throw error;
    }
    const fields = extractPlatformHttpError(error, "查询运行诊断失败");
    const enhancedError = new Error(fields.message || "查询运行诊断失败");
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

/**
 * 后台非阻塞长任务服务层调用
 * 路由：/api/langgraph/threads/{thread_id}/background-tasks
 */

import { platformHttpClient } from "@/services/http/client";
import {
  unwrapPlatformHttpError,
  type PlatformUnwrappedHttpError,
} from "@/utils/http-error";
import {
  safeParseOutputV1,
  safeParseTaskListV1,
  safeParseTaskV1,
  type OutputV1,
  type TaskListV1,
  type TaskV1,
} from "@/modules/chat/background-tasks/types";

export type BackgroundTaskServiceError = PlatformUnwrappedHttpError;

export async function unwrapBackgroundTaskError(
  err: unknown,
  fallbackMessage = "后台任务请求失败",
): Promise<BackgroundTaskServiceError> {
  return unwrapPlatformHttpError(err, fallbackMessage);
}

/**
 * 查询指定 Thread 授权范围内的后台任务列表
 */
export async function listBackgroundTasks(
  projectId: string,
  threadId: string,
  params: { limit?: number; before?: string } = {},
  signal?: AbortSignal,
): Promise<TaskListV1> {
  try {
    const res = await platformHttpClient.get(
      `/api/langgraph/threads/${encodeURIComponent(threadId)}/background-tasks`,
      {
        params: {
          ...(params.limit ? { limit: params.limit } : {}),
          ...(params.before ? { before: params.before } : {}),
        },
        headers: { "x-project-id": projectId },
        signal,
      },
    );
    const parsed = safeParseTaskListV1(res.data);
    if (!parsed.success || !parsed.data) {
      throw new Error(`后台任务列表数据格式校验失败: ${parsed.errorMessage}`);
    }
    return parsed.data;
  } catch (err) {
    throw await unwrapBackgroundTaskError(err, "获取后台任务列表失败");
  }
}

/**
 * 查询单个后台任务的状态快照
 */
export async function getBackgroundTask(
  projectId: string,
  threadId: string,
  taskId: string,
  signal?: AbortSignal,
): Promise<TaskV1> {
  try {
    const res = await platformHttpClient.get(
      `/api/langgraph/threads/${encodeURIComponent(threadId)}/background-tasks/${encodeURIComponent(taskId)}`,
      {
        headers: { "x-project-id": projectId },
        signal,
      },
    );
    const parsed = safeParseTaskV1(res.data);
    if (!parsed.success || !parsed.data) {
      throw new Error(`后台任务详情数据格式校验失败: ${parsed.errorMessage}`);
    }
    return parsed.data;
  } catch (err) {
    throw await unwrapBackgroundTaskError(err, "获取后台任务详情失败");
  }
}

/**
 * 查询单个后台任务的有界纯文本日志快照（单次最多 64KiB）
 */
export async function getBackgroundTaskOutput(
  projectId: string,
  threadId: string,
  taskId: string,
  signal?: AbortSignal,
): Promise<OutputV1> {
  try {
    const res = await platformHttpClient.get(
      `/api/langgraph/threads/${encodeURIComponent(threadId)}/background-tasks/${encodeURIComponent(taskId)}/output`,
      {
        headers: { "x-project-id": projectId },
        signal,
      },
    );
    const parsed = safeParseOutputV1(res.data);
    if (!parsed.success || !parsed.data) {
      throw new Error(`后台任务日志数据格式校验失败: ${parsed.errorMessage}`);
    }
    return parsed.data;
  } catch (err) {
    throw await unwrapBackgroundTaskError(err, "获取后台任务日志失败");
  }
}

/**
 * 提交取消后台任务意图
 * 返回 202 Accepted 及当前 TaskV1 快照（状态通常为 cancel_requested）
 */
export async function cancelBackgroundTask(
  projectId: string,
  threadId: string,
  taskId: string,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<TaskV1> {
  try {
    const res = await platformHttpClient.post(
      `/api/langgraph/threads/${encodeURIComponent(threadId)}/background-tasks/${encodeURIComponent(taskId)}/cancel`,
      {},
      {
        headers: {
          "x-project-id": projectId,
          "Idempotency-Key": idempotencyKey,
        },
        signal,
      },
    );
    const parsed = safeParseTaskV1(res.data);
    if (!parsed.success || !parsed.data) {
      throw new Error(
        `取消后台任务响应数据格式校验失败: ${parsed.errorMessage}`,
      );
    }
    return parsed.data;
  } catch (err) {
    throw await unwrapBackgroundTaskError(err, "取消后台任务失败");
  }
}

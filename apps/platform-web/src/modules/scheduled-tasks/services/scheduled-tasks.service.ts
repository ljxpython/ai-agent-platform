import { platformHttpClient } from "@/services/http/client";
import type {
  PaginatedResult,
  SchedulePreviewPayload,
  SchedulePreviewResult,
  ScheduledTask,
  ScheduledTaskRun,
  TaskCreatePayload,
  TaskUpdatePayload,
  TriggerTaskResult,
} from "../types";

function scoped(projectId: string, extraHeaders?: Record<string, string>) {
  if (!projectId.trim()) throw new Error("请选择项目");
  return {
    headers: {
      "x-project-id": projectId,
      ...(extraHeaders || {}),
    },
  };
}

/**
 * 获取定时任务列表
 */
export async function listScheduledTasks(
  projectId: string,
  options: { limit?: number; offset?: number; enabled?: boolean } = {},
): Promise<PaginatedResult<ScheduledTask>> {
  const { data } = await platformHttpClient.get<PaginatedResult<ScheduledTask>>(
    "/api/scheduled-tasks",
    {
      ...scoped(projectId),
      params: {
        limit: options.limit ?? 20,
        offset: options.offset ?? 0,
        enabled: options.enabled,
      },
    },
  );
  return data;
}

/**
 * 预览调度时间
 */
export async function previewSchedule(
  projectId: string,
  payload: SchedulePreviewPayload,
  count = 5,
): Promise<SchedulePreviewResult> {
  const { data } = await platformHttpClient.post<SchedulePreviewResult>(
    "/api/scheduled-tasks/preview",
    payload,
    {
      ...scoped(projectId),
      params: { count },
    },
  );
  return data;
}

/**
 * 获取指定定时任务详情
 */
export async function getScheduledTask(
  projectId: string,
  taskId: string,
): Promise<ScheduledTask> {
  const { data } = await platformHttpClient.get<ScheduledTask>(
    `/api/scheduled-tasks/${encodeURIComponent(taskId)}`,
    scoped(projectId),
  );
  return data;
}

/**
 * 创建定时任务
 */
export async function createScheduledTask(
  projectId: string,
  payload: TaskCreatePayload,
): Promise<ScheduledTask> {
  const { data } = await platformHttpClient.post<ScheduledTask>(
    "/api/scheduled-tasks",
    payload,
    scoped(projectId),
  );
  return data;
}

/**
 * 增量更新定时任务
 */
export async function updateScheduledTask(
  projectId: string,
  taskId: string,
  payload: TaskUpdatePayload,
): Promise<ScheduledTask> {
  const { data } = await platformHttpClient.patch<ScheduledTask>(
    `/api/scheduled-tasks/${encodeURIComponent(taskId)}`,
    payload,
    scoped(projectId),
  );
  return data;
}

/**
 * 暂停定时任务
 */
export async function pauseScheduledTask(
  projectId: string,
  taskId: string,
): Promise<ScheduledTask> {
  const { data } = await platformHttpClient.post<ScheduledTask>(
    `/api/scheduled-tasks/${encodeURIComponent(taskId)}/pause`,
    {},
    scoped(projectId),
  );
  return data;
}

/**
 * 恢复定时任务
 */
export async function resumeScheduledTask(
  projectId: string,
  taskId: string,
): Promise<ScheduledTask> {
  const { data } = await platformHttpClient.post<ScheduledTask>(
    `/api/scheduled-tasks/${encodeURIComponent(taskId)}/resume`,
    {},
    scoped(projectId),
  );
  return data;
}

/**
 * 删除定时任务
 */
export async function deleteScheduledTask(
  projectId: string,
  taskId: string,
): Promise<void> {
  await platformHttpClient.delete(
    `/api/scheduled-tasks/${encodeURIComponent(taskId)}`,
    scoped(projectId),
  );
}

/**
 * 手动立即触发任务
 */
export async function triggerScheduledTask(
  projectId: string,
  taskId: string,
  idempotencyKey?: string,
): Promise<TriggerTaskResult> {
  const key =
    idempotencyKey ||
    (typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : String(Date.now()));
  const { data } = await platformHttpClient.post<TriggerTaskResult>(
    `/api/scheduled-tasks/${encodeURIComponent(taskId)}/trigger`,
    {},
    scoped(projectId, { "Idempotency-Key": key }),
  );
  return data;
}

/**
 * 分页获取任务执行历史
 */
export async function listScheduledTaskRuns(
  projectId: string,
  taskId: string,
  options: { limit?: number; offset?: number } = {},
): Promise<PaginatedResult<ScheduledTaskRun>> {
  const { data } = await platformHttpClient.get<
    PaginatedResult<ScheduledTaskRun>
  >(`/api/scheduled-tasks/${encodeURIComponent(taskId)}/runs`, {
    ...scoped(projectId),
    params: {
      limit: options.limit ?? 20,
      offset: options.offset ?? 0,
    },
  });
  return data;
}

/**
 * 后台非阻塞长任务前端领域模型与 Zod 契约定义
 * 严格对齐后端 platform_api / runtime_service DTO 契约
 */

import { z } from "zod";

// 1. 安全数值与边界
export const safeCountSchema = z
  .number()
  .int()
  .nonnegative()
  .max(Number.MAX_SAFE_INTEGER);

// exit_code 必须兼容进程被信号终止时的负值（-255 ~ 255）及 null
export const exitCodeSchema = z.number().int().min(-255).max(255).nullable();

// 2. Reason Code 白名单枚举（与后端 Pydantic 严格对齐）
export const BACKGROUND_TASK_REASONS = [
  "background_task_control_unavailable",
  "background_task_resource_missing",
  "background_task_start_unconfirmed",
  "background_task_deadline_exceeded",
  "background_task_oom",
  "background_task_command_failed",
  "background_task_disabled",
  "background_task_delivery_expired",
  "background_task_delivery_unavailable",
  "background_task_denied",
  "background_task_thread_busy",
  "background_task_approval_pending",
] as const;
export type BackgroundTaskReason = (typeof BACKGROUND_TASK_REASONS)[number];

// 3. 任务核心枚举
export const TASK_STATUSES = [
  "starting",
  "running",
  "succeeded",
  "failed",
  "timed_out",
  "cancel_requested",
  "cancelled",
  "unknown",
] as const;
export type TaskStatus = (typeof TASK_STATUSES)[number];

export const CLEANUP_STATES = [
  "not_required",
  "pending",
  "confirmed",
  "unconfirmed",
] as const;
export type CleanupState = (typeof CLEANUP_STATES)[number];

export const DELIVERY_STATES = [
  "not_ready",
  "pending",
  "dispatching",
  "accepted",
  "blocked",
  "suppressed",
  "expired",
  "unknown",
] as const;
export type DeliveryState = (typeof DELIVERY_STATES)[number];

export const ALLOWED_ACTIONS = ["read", "logs", "cancel"] as const;
export type AllowedAction = (typeof ALLOWED_ACTIONS)[number];

// 4. 子结构 Schema
export const taskOutputMetaSchema = z
  .object({
    available: z.boolean(),
    retained_bytes: z.number().int().nonnegative().max(1048576), // 最大 1MiB
    omitted_bytes: safeCountSchema,
    truncated: z.boolean(),
    updated_at: z.string().datetime({ offset: true }).nullable(),
  })
  .strip();
export type TaskOutputMeta = z.infer<typeof taskOutputMetaSchema>;

export const taskDeliverySchema = z
  .object({
    state: z.enum(DELIVERY_STATES),
    event_id: z.string().uuid().nullable(),
    run_id: z.string().uuid().nullable(),
    reason_code: z.enum(BACKGROUND_TASK_REASONS).nullable(),
  })
  .strip();
export type TaskDelivery = z.infer<typeof taskDeliverySchema>;

// 5. 单任务 TaskV1 Schema
export const taskV1Schema = z
  .object({
    version: z.literal(1),
    task_id: z.string().uuid(),
    thread_id: z.string().uuid(),
    graph_id: z.string().min(1).max(128),
    origin_run_id: z.string().uuid(),
    status: z.enum(TASK_STATUSES),
    reason_code: z.enum(BACKGROUND_TASK_REASONS).nullable(),
    exit_code: exitCodeSchema,
    created_at: z.string().datetime({ offset: true }),
    started_at: z.string().datetime({ offset: true }).nullable(),
    finished_at: z.string().datetime({ offset: true }).nullable(),
    deadline_at: z.string().datetime({ offset: true }),
    updated_at: z.string().datetime({ offset: true }),
    cleanup_state: z.enum(CLEANUP_STATES),
    output: taskOutputMetaSchema,
    delivery: taskDeliverySchema,
    allowed_actions: z.array(z.enum(ALLOWED_ACTIONS)).max(3),
  })
  .strip();
export type TaskV1 = z.infer<typeof taskV1Schema>;

// 6. 任务列表 TaskListV1 Schema
export const taskListV1Schema = z
  .object({
    version: z.literal(1),
    thread_id: z.string().uuid(),
    items: z.array(taskV1Schema).max(100),
    next_cursor: z.string().max(256).nullable(),
    has_unresolved: z.boolean(),
    latest_delivery_run_id: z.string().uuid().nullable(),
  })
  .strip();
export type TaskListV1 = z.infer<typeof taskListV1Schema>;

// 7. 有界日志 OutputV1 Schema
export const outputV1Schema = z.preprocess(
  (val) => {
    if (typeof val === "object" && val !== null) {
      const obj = val as Record<string, unknown>;
      if (typeof obj.text !== "string" && typeof obj.output === "string") {
        return { ...obj, text: obj.output };
      }
    }
    return val;
  },
  z
    .object({
      version: z.literal(1),
      task_id: z.string().uuid(),
      thread_id: z.string().uuid(),
      available: z.boolean(),
      text: z.string().max(65536), // 最多 64KiB
      retained_bytes: z.number().int().nonnegative().max(1048576),
      omitted_bytes: safeCountSchema,
      truncated: z.boolean(),
      updated_at: z.string().datetime({ offset: true }).nullable(),
    })
    .strip(),
);
export type OutputV1 = z.infer<typeof outputV1Schema>;

// 8. 取消响应（与 TaskV1 同形，202 状态）
export const cancelResponseV1Schema = taskV1Schema;
export type CancelResponseV1 = TaskV1;

// 9. 安全解析辅助工具
export function safeParseTaskV1(raw: unknown): {
  success: boolean;
  data: TaskV1 | null;
  errorMessage?: string;
} {
  const parsed = taskV1Schema.safeParse(raw);
  if (parsed.success) return { success: true, data: parsed.data };
  return {
    success: false,
    data: null,
    errorMessage: parsed.error.errors
      .map((e) => `${e.path.join(".")}: ${e.message}`)
      .join("; "),
  };
}

export function safeParseTaskListV1(raw: unknown): {
  success: boolean;
  data: TaskListV1 | null;
  errorMessage?: string;
} {
  const parsed = taskListV1Schema.safeParse(raw);
  if (parsed.success) return { success: true, data: parsed.data };
  return {
    success: false,
    data: null,
    errorMessage: parsed.error.errors
      .map((e) => `${e.path.join(".")}: ${e.message}`)
      .join("; "),
  };
}

export function safeParseOutputV1(raw: unknown): {
  success: boolean;
  data: OutputV1 | null;
  errorMessage?: string;
} {
  const parsed = outputV1Schema.safeParse(raw);
  if (parsed.success) return { success: true, data: parsed.data };
  return {
    success: false,
    data: null,
    errorMessage: parsed.error.errors
      .map((e) => `${e.path.join(".")}: ${e.message}`)
      .join("; "),
  };
}

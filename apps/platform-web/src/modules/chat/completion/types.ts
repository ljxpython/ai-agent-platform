import { z } from "zod";

/**
 * 终态状态枚举（与后端契约保持一致）
 */
export const TERMINAL_STATUSES = [
  "success",
  "error",
  "timeout",
  "interrupted",
] as const;
export type TerminalStatus = (typeof TERMINAL_STATUSES)[number];
export const TerminalStatusSchema = z.enum(TERMINAL_STATUSES);

/**
 * 终态业务原因枚举
 */
export const TERMINAL_REASONS = [
  "completed",
  "business_error",
  "infrastructure_error",
  "timeout",
  "hitl_interrupt",
  "cancel_requested",
  "rollback",
  "lease_expired",
] as const;
export type TerminalReason = (typeof TERMINAL_REASONS)[number];
export const TerminalReasonSchema = z.enum(TERMINAL_REASONS);

/**
 * 已冻结的 reason_code 白名单
 */
export const REASON_CODES = [
  "runtime_execution_failed",
  "runtime_run_timeout",
  "runtime_graph_step_limit_reached",
  "runtime_model_call_limit_reached",
  "runtime_tool_call_limit_reached",
  "runtime.model.retry_exhausted",
  "runtime.model.retry_budget_exceeded",
  "runtime.model.stream_interrupted",
  "runtime.model.provider_rejected",
  "runtime.model.fallback_incompatible",
  "runtime.workspace.unavailable",
  "runtime.workspace.execution_unavailable",
  "runtime.workspace.backend_invalid",
  "runtime.workspace.image_invalid",
  "runtime.workspace.execution_outcome_unknown",
] as const;
export type ReasonCode = (typeof REASON_CODES)[number];
export const ReasonCodeSchema = z.enum(REASON_CODES).nullable();

/**
 * 已冻结的 model_error_code 白名单
 */
export const MODEL_ERROR_CODES = [
  "provider_rate_limited",
  "provider_overloaded",
  "context_too_long",
  "model_unavailable",
  "provider_auth_failed",
  "provider_access_denied",
  "provider_timeout",
  "provider_unavailable",
  "model_call_failed",
] as const;
export type ModelErrorCode = (typeof MODEL_ERROR_CODES)[number];
export const ModelErrorCodeSchema = z.enum(MODEL_ERROR_CODES).nullable();

/**
 * 已冻结的 notification_code 白名单（13 个）
 */
export const NOTIFICATION_CODES = [
  "run_timed_out",
  "run_failed",
  "run_failed_step_limit",
  "run_failed_workspace",
  "run_failed_provider_rate_limited",
  "run_failed_provider_overloaded",
  "run_failed_provider_timeout",
  "run_failed_provider_unavailable",
  "run_failed_provider_auth_failed",
  "run_failed_provider_access_denied",
  "run_failed_context_too_long",
  "run_failed_model_unavailable",
  "run_failed_model_call_failed",
] as const;
export type NotificationCode = (typeof NOTIFICATION_CODES)[number];
export const NotificationCodeSchema = z.enum(NOTIFICATION_CODES).nullable();

/**
 * 安全 completion 摘要对象
 */
export const SafeCompletionSchema = z
  .object({
    event_id: z.string().uuid(),
    graph_id: z.string().min(1).max(128),
    status: TerminalStatusSchema,
    reason: TerminalReasonSchema,
    reason_code: ReasonCodeSchema,
    model_error_code: ModelErrorCodeSchema,
    notification_code: NotificationCodeSchema,
    occurred_at: z.string().datetime({ offset: true }),
    can_mark_read: z.boolean(),
    read_at: z.string().datetime({ offset: true }).nullable(),
  })
  .strict();
export type SafeCompletion = z.infer<typeof SafeCompletionSchema>;

/**
 * Completion 查询响应模式
 */
export const CompletionResponseSchema = z.discriminatedUnion("availability", [
  z
    .object({
      version: z.literal(1).default(1),
      thread_id: z.string().uuid(),
      run_id: z.string().uuid(),
      availability: z.literal("available"),
      completion: SafeCompletionSchema,
      request_id: z.string().min(1),
    })
    .strict(),
  z
    .object({
      version: z.literal(1).default(1),
      thread_id: z.string().uuid(),
      run_id: z.string().uuid(),
      availability: z.enum(["pending", "unsupported", "expired"]),
      completion: z.null(),
      request_id: z.string().min(1),
    })
    .strict(),
]);
export type CompletionResponse = z.infer<typeof CompletionResponseSchema>;

/**
 * 运行通知项 Schema
 */
export const RunNotificationSchema = SafeCompletionSchema.extend({
  thread_id: z.string().uuid(),
  run_id: z.string().uuid(),
  received_at: z.string().datetime({ offset: true }),
}).strict();
export type RunNotification = z.infer<typeof RunNotificationSchema>;

/**
 * 运行通知列表 Feed 响应
 */
export const NotificationFeedResponseSchema = z
  .object({
    version: z.literal(1).default(1),
    availability: z.enum(["available", "disabled"]),
    items: z.array(RunNotificationSchema),
    next_cursor: z.string().max(1024).nullable(),
    scan_limit_reached: z.boolean(),
    request_id: z.string().min(1),
  })
  .strict();
export type NotificationFeedResponse = z.infer<
  typeof NotificationFeedResponseSchema
>;

/**
 * 已读回执响应
 */
export const ReadReceiptResponseSchema = z
  .object({
    version: z.literal(1).default(1),
    event_id: z.string().uuid(),
    read_at: z.string().datetime({ offset: true }),
    request_id: z.string().min(1),
  })
  .strict();
export type ReadReceiptResponse = z.infer<typeof ReadReceiptResponseSchema>;

/**
 * 严格 DTO 解析结果类型
 */
export type SafeParseResult<T> =
  | { success: true; data: T }
  | { success: false; error: z.ZodError; errorMessage: string };

function formatZodError(error: z.ZodError): string {
  return error.issues
    .map((issue) => `${issue.path.join(".") || "root"}: ${issue.message}`)
    .join("; ");
}

export function safeParseCompletionResponse(
  raw: unknown,
): SafeParseResult<CompletionResponse> {
  const result = CompletionResponseSchema.safeParse(raw);
  if (result.success) {
    return { success: true, data: result.data };
  }
  return {
    success: false,
    error: result.error,
    errorMessage: formatZodError(result.error),
  };
}

export function safeParseNotificationFeedResponse(
  raw: unknown,
): SafeParseResult<NotificationFeedResponse> {
  const result = NotificationFeedResponseSchema.safeParse(raw);
  if (result.success) {
    return { success: true, data: result.data };
  }
  return {
    success: false,
    error: result.error,
    errorMessage: formatZodError(result.error),
  };
}

export function safeParseReadReceiptResponse(
  raw: unknown,
): SafeParseResult<ReadReceiptResponse> {
  const result = ReadReceiptResponseSchema.safeParse(raw);
  if (result.success) {
    return { success: true, data: result.data };
  }
  return {
    success: false,
    error: result.error,
    errorMessage: formatZodError(result.error),
  };
}

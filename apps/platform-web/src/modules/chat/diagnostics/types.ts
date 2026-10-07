import { z } from "zod";

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

export const GRAPH_OUTCOMES = [
  "success",
  "failed",
  "timeout",
  "cancelled",
  "interrupted",
] as const;

export type GraphOutcome = (typeof GRAPH_OUTCOMES)[number];

export const PHASE_OUTCOMES = [
  "completed",
  "failed",
  "cancelled",
  "incomplete",
] as const;

export type PhaseOutcome = (typeof PHASE_OUTCOMES)[number];

export const AVAILABILITY_STATUSES = [
  "available",
  "partial",
  "disabled",
  "unavailable",
] as const;

export type AvailabilityStatus = (typeof AVAILABILITY_STATUSES)[number];

export const UNAVAILABLE_REASONS = [
  "not_configured",
  "not_recorded",
  "backend_unavailable",
] as const;

export type UnavailableReason = (typeof UNAVAILABLE_REASONS)[number];

// 安全数值校验：只接受有限非负数值，拦截 NaN / Infinity / 负数，null 保持有效
const safeDurationSchema = z.number().finite().nonnegative().nullable();

export const modelErrorSchema = z.object({
  observation_id: z.string().max(128),
  scope: z.enum(["primary", "subagent"]),
  namespace: z.array(z.string().max(128)).max(8),
  code: z.string().max(64),
  error_type: z.string().max(128).nullable(),
  provider_status: z.number().int().finite().nullable(),
  duration_ms: safeDurationSchema,
});

export type ModelErrorItem = z.infer<typeof modelErrorSchema>;

export const graphExecutionSchema = z.object({
  observation_id: z.string().max(128),
  outcome: z.enum(GRAPH_OUTCOMES),
  error_code: z.string().max(64).nullable(),
  duration_ms: safeDurationSchema,
});

export type GraphExecutionItem = z.infer<typeof graphExecutionSchema>;

export const startupPhaseSchema = z.object({
  name: z.string().max(128),
  ordinal: z.number().int().finite().nonnegative(),
  outcome: z.enum(PHASE_OUTCOMES),
  started_at: z.string().max(64).nullable(),
  ended_at: z.string().max(64).nullable(),
  duration_ms: safeDurationSchema,
  error_code: z.string().max(64).nullable(),
});

export type StartupPhaseItem = z.infer<typeof startupPhaseSchema>;

export const startupDiagnosticsSchema = z.object({
  duration_ms: safeDurationSchema,
  phases: z.array(startupPhaseSchema).max(16),
});

export type StartupDiagnostics = z.infer<typeof startupDiagnosticsSchema>;

export const correlationSchema = z.object({
  execution_request_id: z.string().max(128).nullable(),
  platform_trace_id: z.string().max(128).nullable(),
});

export type CorrelationInfo = z.infer<typeof correlationSchema>;

export const traceInfoSchema = z.object({
  provider: z.literal("langfuse"),
  trace_id: z.string().max(128),
  url: z.null(),
});

export type TraceInfo = z.infer<typeof traceInfoSchema>;

// v1 根 DTO 校验器：strip 模式会自动剥离未在 schema 中显式声明的未知字段
export const runDiagnosticsV1Schema = z
  .object({
    version: z.literal(1),
    thread_id: z.string().max(128),
    run_id: z.string().max(128),
    run_status: z.string().max(64),
    request_id: z.string().max(128),
    availability: z.enum(AVAILABILITY_STATUSES),
    unavailable_reason: z.enum(UNAVAILABLE_REASONS).nullable(),
    correlation: correlationSchema,
    trace: traceInfoSchema.nullable(),
    graph_executions: z.array(graphExecutionSchema).max(10),
    model_errors: z.array(modelErrorSchema).max(20),
    startup: startupDiagnosticsSchema.nullable(),
    truncated: z.boolean(),
  })
  .strip();

export type RunDiagnosticsV1 = z.infer<typeof runDiagnosticsV1Schema>;

/**
 * 安全解析诊断 DTO：剔除未知字段，若校验失败返回 null 并保留错误信息
 */
export function safeParseRunDiagnostics(raw: unknown): {
  success: boolean;
  data: RunDiagnosticsV1 | null;
  errorMessage?: string;
} {
  const result = runDiagnosticsV1Schema.safeParse(raw);
  if (result.success) {
    return { success: true, data: result.data };
  }
  return {
    success: false,
    data: null,
    errorMessage: result.error.errors
      .map((e) => `${e.path.join(".")}: ${e.message}`)
      .join("; "),
  };
}

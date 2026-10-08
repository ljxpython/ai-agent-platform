import { z } from "zod";

export const STOP_PHASES = [
  "accepted",
  "stopping",
  "stopped",
  "no_active_run",
  "confirmation_unavailable",
  "rejected",
] as const;

export type StopPhase = (typeof STOP_PHASES)[number];

export const RESOURCE_CLEANUP_STATUSES = [
  "pending",
  "confirmed",
  "unconfirmed",
  "not_required",
] as const;

export type ResourceCleanupStatus = (typeof RESOURCE_CLEANUP_STATUSES)[number];

export const REASON_CODES = [
  "stop_denied",
  "stop_confirmation_unavailable",
  "resource_cleanup_unconfirmed",
] as const;

export type ReasonCode = (typeof REASON_CODES)[number];

export const UNCERTAINTIES = [
  "checkpoint_unavailable",
  "progress_unavailable",
  "external_effect_unknown",
  "resource_cleanup_unconfirmed",
] as const;

export type Uncertainty = (typeof UNCERTAINTIES)[number];

export const PROGRESS_KINDS = ["saved_plan", "tool_receipt"] as const;
export type ProgressKind = (typeof PROGRESS_KINDS)[number];

export const PROGRESS_OBSERVED_STATUSES = [
  "pending",
  "in_progress",
  "completed",
  "recorded",
] as const;
export type ProgressObservedStatus =
  (typeof PROGRESS_OBSERVED_STATUSES)[number];

const safeCountSchema = z.number().int().nonnegative().nullable();

export const queueCountsSchema = z
  .object({
    pending_cancelled_count: safeCountSchema,
    inbox_consumed_count: safeCountSchema,
    inbox_not_consumed_count: safeCountSchema,
  })
  .strip();

export type QueueCounts = z.infer<typeof queueCountsSchema>;

export const checkpointSchema = z
  .object({
    run_id: z.string().uuid(),
    checkpoint_id: z.string().max(256),
    checkpoint_at: z.string().nullable().optional(),
  })
  .strip();

export type StopCheckpoint = z.infer<typeof checkpointSchema>;

export const progressSchema = z
  .object({
    kind: z.enum(PROGRESS_KINDS),
    label: z.string().max(256),
    observed_status: z.enum(PROGRESS_OBSERVED_STATUSES),
    source_run_id: z.string().uuid(),
    source_message_id: z.string().max(256).nullable().optional(),
  })
  .strip();

export type StopProgress = z.infer<typeof progressSchema>;

export const artifactSchema = z
  .object({
    artifact_id: z.string().regex(/^[0-9a-f]{64}$/),
    path: z
      .string()
      .regex(/^\/workspace\/outputs\/[0-9a-f]{64}\.[a-z0-9]{1,8}$/),
    source_run_id: z.string().uuid(),
    source_message_id: z.string().max(256).nullable().optional(),
  })
  .strip();

export type StopArtifact = z.infer<typeof artifactSchema>;

export const stopReportSchema = z
  .object({
    version: z.literal(1),
    source: z.literal("checkpoint_and_receipts"),
    checkpoint_id: z.string().max(256).nullable(),
    checkpoint_at: z.string().nullable().optional(),
    checkpoints: z.array(checkpointSchema).max(20),
    progress: z.array(progressSchema).max(30),
    artifacts: z.array(artifactSchema).max(20),
    uncertainties: z.array(z.enum(UNCERTAINTIES)).max(10),
    truncated: z.boolean(),
  })
  .strip();

export type StopReport = z.infer<typeof stopReportSchema>;

export const stopRequestSchema = z
  .object({
    version: z.literal(1),
    stop_id: z.string().uuid(),
    thread_id: z.string().uuid(),
    phase: z.enum(STOP_PHASES),
    requested_at: z.string(),
    accepted_at: z.string().nullable().optional(),
    confirmed_at: z.string().nullable().optional(),
    target_count: safeCountSchema,
    execution_stopped: z.boolean().nullable(),
    resource_cleanup: z.enum(RESOURCE_CLEANUP_STATUSES),
    has_pending_interrupts: z.boolean().nullable(),
    queue: queueCountsSchema,
    report: stopReportSchema.nullable(),
    reason_code: z.enum(REASON_CODES).nullable().optional(),
    request_id: z.string().max(256).default(""),
  })
  .strip();

export type StopRequest = z.infer<typeof stopRequestSchema>;

export const stopRequestListSchema = z
  .object({
    items: z.array(stopRequestSchema).max(100),
    next_cursor: z.string().max(256).nullable(),
  })
  .strip();

export type StopRequestList = z.infer<typeof stopRequestListSchema>;

/**
 * 安全解析单个 StopRequest DTO
 */
export function safeParseStopRequest(raw: unknown): {
  success: boolean;
  data: StopRequest | null;
  errorMessage?: string;
} {
  const result = stopRequestSchema.safeParse(raw);
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

/**
 * 安全解析 StopRequestList DTO
 */
export function safeParseStopRequestList(raw: unknown): {
  success: boolean;
  data: StopRequestList | null;
  errorMessage?: string;
} {
  const result = stopRequestListSchema.safeParse(raw);
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

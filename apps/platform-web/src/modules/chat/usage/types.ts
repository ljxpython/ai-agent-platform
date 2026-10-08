import { z } from "zod";

export interface TokenCounts {
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
  cache_read_tokens: number | null;
  cache_creation_tokens: number | null;
  cache_creation_5m_tokens: number | null;
  cache_creation_1h_tokens: number | null;
  reasoning_tokens: number | null;
}

export interface UsageCost {
  status: "estimated" | "partial" | "unknown" | "not_applicable";
  estimated_cost_usd: string | null;
  known_cost_usd: string | null;
  currency: "USD";
  source: "configured_catalog" | null;
  unpriced_call_count: number;
  pricing_versions: string[];
}

export interface UsageCoverage {
  observed_call_count: number;
  reported_call_count: number;
  missing_usage_call_count: number;
  incomplete_call_count: number;
  collection_degraded: boolean;
  excluded_operations: string[];
}

export interface UsageCallV1 {
  model_call_id: string;
  model_id: string | null;
  provider: string | null;
  model_name: string | null;
  scope: "primary" | "subagent" | "auxiliary";
  purpose: "agent" | "summarization" | "memory_extraction" | "vision" | "other";
  namespace: string[];
  outcome: "started" | "completed" | "failed" | "cancelled";
  quality:
    | "reported"
    | "derived_from_reported"
    | "partial"
    | "missing"
    | "invalid";
  tokens: TokenCounts;
  cost: UsageCost;
  started_at: string;
  ended_at: string | null;
}

export interface CallPageV1 {
  items: UsageCallV1[];
  next_cursor: string | null;
}

export interface RunUsageV1 {
  version: 1;
  thread_id: string;
  run_id: string;
  run_status: string;
  request_id: string;
  availability: "available" | "partial" | "disabled" | "unavailable";
  unavailable_reason: "not_recorded" | "backend_unavailable" | null;
  finalized: boolean;
  tokens: TokenCounts;
  known_tokens: TokenCounts;
  cost: UsageCost;
  coverage: UsageCoverage;
  calls: CallPageV1;
  truncated: boolean;
}

export interface ThreadUsageV1 {
  version: 1;
  thread_id: string;
  request_id: string;
  availability: "available" | "partial" | "disabled" | "unavailable";
  unavailable_reason: "not_recorded" | "backend_unavailable" | null;
  coverage_basis: "recorded_native_runs";
  created_from: string | null;
  created_to: string | null;
  recorded_run_count: number;
  first_recorded_at: string | null;
  last_recorded_at: string | null;
  tokens: TokenCounts;
  known_tokens: TokenCounts;
  cost: UsageCost;
  coverage: UsageCoverage;
  truncated: boolean;
}

// ======================= Zod Schemas =======================

const safeIntegerToken = z
  .number()
  .int()
  .min(0)
  .max(Number.MAX_SAFE_INTEGER)
  .nullable();

const decimalAmount = z
  .string()
  .regex(/^\d+(\.\d+)?$/, "金额必须为合法的非负十进制字符串")
  .nullable();

export const tokenCountsSchema = z
  .object({
    input_tokens: safeIntegerToken,
    output_tokens: safeIntegerToken,
    total_tokens: safeIntegerToken,
    cache_read_tokens: safeIntegerToken,
    cache_creation_tokens: safeIntegerToken,
    cache_creation_5m_tokens: safeIntegerToken,
    cache_creation_1h_tokens: safeIntegerToken,
    reasoning_tokens: safeIntegerToken,
  })
  .strip();

export const usageCostSchema = z
  .object({
    status: z.enum(["estimated", "partial", "unknown", "not_applicable"]),
    estimated_cost_usd: decimalAmount,
    known_cost_usd: decimalAmount,
    currency: z.literal("USD"),
    source: z.literal("configured_catalog").nullable(),
    unpriced_call_count: z.number().int().min(0),
    pricing_versions: z.array(z.string()),
  })
  .strip();

export const usageCoverageSchema = z
  .object({
    observed_call_count: z.number().int().min(0),
    reported_call_count: z.number().int().min(0),
    missing_usage_call_count: z.number().int().min(0),
    incomplete_call_count: z.number().int().min(0),
    collection_degraded: z.boolean(),
    excluded_operations: z.array(z.string()),
  })
  .strip();

export const usageCallSchema = z
  .object({
    model_call_id: z.string().min(1),
    model_id: z.string().nullable(),
    provider: z.string().nullable(),
    model_name: z.string().nullable(),
    scope: z.enum(["primary", "subagent", "auxiliary"]),
    purpose: z.enum([
      "agent",
      "summarization",
      "memory_extraction",
      "vision",
      "other",
    ]),
    namespace: z.array(z.string()),
    outcome: z.enum(["started", "completed", "failed", "cancelled"]),
    quality: z.enum([
      "reported",
      "derived_from_reported",
      "partial",
      "missing",
      "invalid",
    ]),
    tokens: tokenCountsSchema,
    cost: usageCostSchema,
    started_at: z.string(),
    ended_at: z.string().nullable(),
  })
  .strip();

export const callPageSchema = z
  .object({
    items: z.array(usageCallSchema).max(200),
    next_cursor: z.string().nullable(),
  })
  .strip();

export const runUsageSchema = z
  .object({
    version: z.literal(1),
    thread_id: z.string().min(1),
    run_id: z.string().min(1),
    run_status: z.string(),
    request_id: z.string(),
    availability: z.enum(["available", "partial", "disabled", "unavailable"]),
    unavailable_reason: z
      .enum(["not_recorded", "backend_unavailable"])
      .nullable(),
    finalized: z.boolean(),
    tokens: tokenCountsSchema,
    known_tokens: tokenCountsSchema,
    cost: usageCostSchema,
    coverage: usageCoverageSchema,
    calls: callPageSchema,
    truncated: z.boolean(),
  })
  .strip();

export const threadUsageSchema = z
  .object({
    version: z.literal(1),
    thread_id: z.string().min(1),
    request_id: z.string(),
    availability: z.enum(["available", "partial", "disabled", "unavailable"]),
    unavailable_reason: z
      .enum(["not_recorded", "backend_unavailable"])
      .nullable(),
    coverage_basis: z.literal("recorded_native_runs"),
    created_from: z.string().nullable(),
    created_to: z.string().nullable(),
    recorded_run_count: z.number().int().min(0),
    first_recorded_at: z.string().nullable(),
    last_recorded_at: z.string().nullable(),
    tokens: tokenCountsSchema,
    known_tokens: tokenCountsSchema,
    cost: usageCostSchema,
    coverage: usageCoverageSchema,
    truncated: z.boolean(),
  })
  .strip();

export interface ParseResult<T> {
  success: boolean;
  data?: T;
  errorMessage?: string;
}

export function safeParseRunUsage(data: unknown): ParseResult<RunUsageV1> {
  const result = runUsageSchema.safeParse(data);
  if (result.success) {
    return { success: true, data: result.data as RunUsageV1 };
  }
  const msg = result.error.errors
    .map((e) => `${e.path.join(".")}: ${e.message}`)
    .join("; ");
  return { success: false, errorMessage: msg };
}

export function safeParseThreadUsage(
  data: unknown,
): ParseResult<ThreadUsageV1> {
  const result = threadUsageSchema.safeParse(data);
  if (result.success) {
    return { success: true, data: result.data as ThreadUsageV1 };
  }
  const msg = result.error.errors
    .map((e) => `${e.path.join(".")}: ${e.message}`)
    .join("; ");
  return { success: false, errorMessage: msg };
}

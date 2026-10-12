import { z } from "zod";

// --- 基础子结构 ---

export const TokenCountsSchema = z.object({
  input_tokens: z.number().nullable(),
  output_tokens: z.number().nullable(),
  total_tokens: z.number().nullable(),
  cache_read_tokens: z.number().nullable(),
  cache_creation_tokens: z.number().nullable(),
  cache_creation_5m_tokens: z.number().nullable(),
  cache_creation_1h_tokens: z.number().nullable(),
  reasoning_tokens: z.number().nullable(),
});
export type TokenCounts = z.infer<typeof TokenCountsSchema>;

export const UsageCostSchema = z.object({
  status: z.enum(["estimated", "partial", "unknown", "not_applicable"]),
  estimated_cost_usd: z.string().nullable(),
  known_cost_usd: z.string().nullable(),
  currency: z.literal("USD"),
  source: z.literal("configured_catalog").nullable(),
  unpriced_call_count: z.number(),
  pricing_versions: z.array(z.string()),
});
export type UsageCost = z.infer<typeof UsageCostSchema>;

export const CoverageSchema = z.object({
  observed_call_count: z.number(),
  reported_call_count: z.number(),
  missing_usage_call_count: z.number(),
  incomplete_call_count: z.number(),
  collection_degraded: z.boolean(),
  excluded_operations: z.array(z.string()),
  priced_call_count: z.number(),
  field_call_counts: TokenCountsSchema,
});
export type Coverage = z.infer<typeof CoverageSchema>;

export const UsageMetricsSchema = z.object({
  tokens: TokenCountsSchema,
  known_tokens: TokenCountsSchema,
  cost: UsageCostSchema,
  coverage: CoverageSchema,
  recorded_run_count: z.number(),
  open_collection_run_count: z.number(),
  zero_call_manifest_count: z.number().nullable(),
  cache_read_ratio: z.number().nullable(),
  ratio_sample_call_count: z.number(),
  average_tokens_per_recorded_run: z.number().nullable(),
  pricing_versions_truncated: z.boolean(),
});
export type UsageMetrics = z.infer<typeof UsageMetricsSchema>;

export const WindowSchema = z.object({
  from: z.string(),
  to: z.string(),
  timezone: z.enum(["UTC", "Asia/Shanghai"]),
  granularity: z.enum(["day", "hour"]),
  time_basis: z.literal("model_call_started_at"),
});
export type UsageWindow = z.infer<typeof WindowSchema>;

export const DashboardScopeSchema = z.object({
  kind: z.enum(["platform", "project"]),
  project_ids: z.array(z.string()),
  covered_project_count: z.number(),
});
export type DashboardScope = z.infer<typeof DashboardScopeSchema>;

export const PreviousWindowSchema = z.object({
  window: WindowSchema,
  summary: UsageMetricsSchema,
  total_token_change_ratio: z.number().nullable(),
});
export type PreviousWindow = z.infer<typeof PreviousWindowSchema>;

export const SeriesPointSchema = UsageMetricsSchema.extend({
  from: z.string(),
  to: z.string(),
});
export type SeriesPoint = z.infer<typeof SeriesPointSchema>;

export const GroupSchema = UsageMetricsSchema.extend({
  key: z.string(),
  label: z.string(),
  project_id: z.string().nullable().optional(),
  agent_id: z.string().nullable().optional(),
});
export type UsageGroup = z.infer<typeof GroupSchema>;

export const BreakdownSchema = z.object({
  group_by: z.enum(["project", "model", "agent", "purpose", "scope"]),
  rank_by: z.enum([
    "known_total_tokens",
    "known_cost_usd",
    "observed_call_count",
  ]),
  items: z.array(GroupSchema),
  other: UsageMetricsSchema.nullable(),
});
export type Breakdown = z.infer<typeof BreakdownSchema>;

export const ProjectOptionSchema = z.object({
  id: z.string(),
  label: z.string(),
});
export type ProjectOption = z.infer<typeof ProjectOptionSchema>;

export const ModelOptionSchema = z.object({
  id: z.union([z.string(), z.literal("unmapped")]),
  label: z.string(),
});
export type ModelOption = z.infer<typeof ModelOptionSchema>;

export const AgentOptionSchema = z.object({
  project_id: z.string(),
  graph_id: z.string(),
  agent_id: z.string().nullable(),
  label: z.string(),
});
export type AgentOption = z.infer<typeof AgentOptionSchema>;

export const FacetsSchema = z.object({
  projects: z.object({
    items: z.array(ProjectOptionSchema),
    truncated: z.boolean(),
  }),
  models: z.object({
    items: z.array(ModelOptionSchema),
    truncated: z.boolean(),
  }),
  agents: z.object({
    items: z.array(AgentOptionSchema),
    truncated: z.boolean(),
  }),
});
export type Facets = z.infer<typeof FacetsSchema>;

export const CollectionSchema = z.object({
  enabled_now: z.boolean().nullable(),
  first_recorded_at: z.string().nullable(),
  last_recorded_at: z.string().nullable(),
  excluded_operations: z.array(z.string()),
});
export type Collection = z.infer<typeof CollectionSchema>;

// --- 主 DTO: UsageDashboardV1 ---

export const UsageDashboardV1Schema = z.object({
  version: z.literal(1),
  scope: DashboardScopeSchema,
  window: WindowSchema,
  as_of: z.string(),
  availability: z.enum(["available", "partial", "disabled", "unavailable"]),
  unavailable_reason: z
    .enum(["not_recorded", "backend_unavailable"])
    .nullable(),
  coverage_basis: z.literal("recorded_native_runs"),
  summary: UsageMetricsSchema,
  previous_window: PreviousWindowSchema,
  series: z.array(SeriesPointSchema),
  breakdown: BreakdownSchema,
  facets: FacetsSchema,
  collection: CollectionSchema,
  request_id: z.string(),
});
export type UsageDashboardV1 = z.infer<typeof UsageDashboardV1Schema>;

// --- 主 DTO: UsageRunPageV1 ---

export const UsageRunSchema = UsageMetricsSchema.extend({
  project_id: z.string(),
  thread_id: z.string(),
  run_id: z.string(),
  graph_id: z.string(),
  agent_id: z.string().nullable().optional(),
  agent_name: z.string(),
  first_matching_call_at: z.string(),
  last_matching_call_at: z.string(),
});
export type UsageRun = z.infer<typeof UsageRunSchema>;

export const UsageRunPageV1Schema = z.object({
  version: z.literal(1),
  items: z.array(UsageRunSchema),
  next_cursor: z.string().nullable(),
  as_of: z.string(),
  request_id: z.string(),
});
export type UsageRunPageV1 = z.infer<typeof UsageRunPageV1Schema>;

// --- 查询参数类型 ---

export type Granularity = "day" | "hour";
export type Timezone = "UTC" | "Asia/Shanghai";
export type GroupBy = "project" | "model" | "agent" | "purpose" | "scope";
export type RankBy =
  | "known_total_tokens"
  | "known_cost_usd"
  | "observed_call_count";
export type CallPurpose =
  | "agent"
  | "summarization"
  | "memory_extraction"
  | "vision"
  | "other";
export type CallScope = "primary" | "subagent" | "auxiliary";

export interface DashboardQueryParams {
  from: string;
  to: string;
  timezone?: Timezone;
  granularity?: Granularity;
  project_ids?: string[]; // 仅平台看板可用
  model_id?: string;
  model_mapping?: "unmapped";
  agent_id?: string;
  purpose?: CallPurpose;
  scope?: CallScope;
  group_by?: GroupBy;
  rank_by?: RankBy;
  top_n?: number;
}

export interface RunsQueryParams {
  from: string;
  to: string;
  model_id?: string;
  model_mapping?: "unmapped";
  agent_id?: string;
  purpose?: CallPurpose;
  scope?: CallScope;
  limit?: number;
  cursor?: string | null;
}

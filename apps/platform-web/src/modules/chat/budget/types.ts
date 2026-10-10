import { z } from "zod";

export const BUDGET_CODES = [
  "model_call_limit_approaching",
  "model_call_limit_reached",
  "graph_step_limit_approaching",
  "wrapup_started",
  "token_budget_approaching",
  "token_budget_exhausted",
  "token_budget_unverifiable",
] as const;

export type BudgetCode = (typeof BUDGET_CODES)[number];

export const BUDGET_SCOPES = ["run", "thread", "graph"] as const;
export type BudgetScope = (typeof BUDGET_SCOPES)[number];

export const BUDGET_UNITS = [
  "model_calls",
  "graph_supersteps",
  "seconds",
  "tokens_total",
] as const;
export type BudgetUnit = (typeof BUDGET_UNITS)[number];

export const BUDGET_SAFETY_ERROR_CODES = [
  "runtime_graph_step_limit_reached",
  "runtime_model_call_limit_reached",
  "runtime_tool_call_limit_reached",
  "runtime_run_timeout",
  "runtime_token_budget_exhausted",
  "runtime_token_budget_unverifiable",
] as const;
export type BudgetSafetyErrorCode = (typeof BUDGET_SAFETY_ERROR_CODES)[number];

// Schema for discrete call/step counts (integers)
const StepOrCallBudgetNoticeSchema = z
  .object({
    version: z.literal(1),
    type: z.literal("runtime_budget_notice"),
    notice_id: z.string().min(1).max(256),
    run_id: z.string().min(1).max(128),
    scope: z.enum(["primary", "subagent"]),
    budget_scope: z.enum(["run", "thread", "graph"]),
    code: z.enum([
      "model_call_limit_approaching",
      "model_call_limit_reached",
      "graph_step_limit_approaching",
    ]),
    limit: z.number().int().nonnegative().nullable(),
    used: z.number().int().nonnegative().nullable(),
    remaining: z.number().int().nonnegative().nullable(),
    unit: z.enum(["model_calls", "graph_supersteps"]),
  })
  .strip();

// Schema for time wrapup (seconds can be floating-point numbers, remaining is null)
const SecondsBudgetNoticeSchema = z
  .object({
    version: z.literal(1),
    type: z.literal("runtime_budget_notice"),
    notice_id: z.string().min(1).max(256),
    run_id: z.string().min(1).max(128),
    scope: z.enum(["primary", "subagent"]),
    budget_scope: z.enum(["run", "thread", "graph"]),
    code: z.literal("wrapup_started"),
    limit: z.number().nonnegative().finite().nullable(),
    used: z.number().nonnegative().finite().nullable(),
    remaining: z.null(),
    unit: z.literal("seconds"),
  })
  .strip();

// Schemas for Token Budgets (tokens_total)
const TokensApproachingNoticeSchema = z
  .object({
    version: z.literal(1),
    type: z.literal("runtime_budget_notice"),
    notice_id: z.string().min(1).max(256),
    run_id: z.string().min(1).max(128),
    scope: z.literal("primary"),
    budget_scope: z.literal("run"),
    code: z.literal("token_budget_approaching"),
    limit: z.number().int().min(1).max(Number.MAX_SAFE_INTEGER),
    used: z.number().int().min(0).max(Number.MAX_SAFE_INTEGER),
    remaining: z.number().int().min(0).max(Number.MAX_SAFE_INTEGER),
    unit: z.literal("tokens_total"),
  })
  .strip();

const TokensExhaustedNoticeSchema = z
  .object({
    version: z.literal(1),
    type: z.literal("runtime_budget_notice"),
    notice_id: z.string().min(1).max(256),
    run_id: z.string().min(1).max(128),
    scope: z.literal("primary"),
    budget_scope: z.literal("run"),
    code: z.literal("token_budget_exhausted"),
    limit: z.number().int().min(1).max(Number.MAX_SAFE_INTEGER),
    used: z.number().int().min(0).max(Number.MAX_SAFE_INTEGER),
    remaining: z.literal(0),
    unit: z.literal("tokens_total"),
  })
  .strip();

const TokensUnverifiableNoticeSchema = z
  .object({
    version: z.literal(1),
    type: z.literal("runtime_budget_notice"),
    notice_id: z.string().min(1).max(256),
    run_id: z.string().min(1).max(128),
    scope: z.literal("primary"),
    budget_scope: z.literal("run"),
    code: z.literal("token_budget_unverifiable"),
    limit: z.number().int().min(1).max(Number.MAX_SAFE_INTEGER),
    used: z.number().int().min(0).max(Number.MAX_SAFE_INTEGER).nullable(),
    remaining: z.null(),
    unit: z.literal("tokens_total"),
  })
  .strip();

export const BudgetNoticeSchema = z.union([
  StepOrCallBudgetNoticeSchema,
  SecondsBudgetNoticeSchema,
  TokensApproachingNoticeSchema,
  TokensExhaustedNoticeSchema,
  TokensUnverifiableNoticeSchema,
]);

export type BudgetNotice = z.infer<typeof BudgetNoticeSchema>;

export const BudgetSafetyErrorSchema = z
  .object({
    type: z.string().optional(),
    code: z.enum(BUDGET_SAFETY_ERROR_CODES),
    message: z.string().optional(),
  })
  .strip();

export type BudgetSafetyError = z.infer<typeof BudgetSafetyErrorSchema>;

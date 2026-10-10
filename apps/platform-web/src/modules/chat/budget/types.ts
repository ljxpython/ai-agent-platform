import { z } from "zod";

export const BUDGET_CODES = [
  "model_call_limit_approaching",
  "model_call_limit_reached",
  "graph_step_limit_approaching",
  "wrapup_started",
  "tool_loop_approaching",
  "tool_loop_reached",
] as const;

export type BudgetCode = (typeof BUDGET_CODES)[number];

export const BUDGET_SCOPES = ["run", "thread", "graph"] as const;
export type BudgetScope = (typeof BUDGET_SCOPES)[number];

export const BUDGET_UNITS = [
  "model_calls",
  "graph_supersteps",
  "seconds",
  "tool_rounds",
] as const;
export type BudgetUnit = (typeof BUDGET_UNITS)[number];

export const BUDGET_SAFETY_ERROR_CODES = [
  "runtime_graph_step_limit_reached",
  "runtime_model_call_limit_reached",
  "runtime_tool_call_limit_reached",
  "runtime_run_timeout",
  "runtime.loop.detected",
] as const;
export type BudgetSafetyErrorCode = (typeof BUDGET_SAFETY_ERROR_CODES)[number];

// Schema for discrete call/step counts (integers)
const StepOrCallBudgetNoticeSchema = z.object({
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
});

// Schema for time wrapup (seconds can be floating-point numbers, remaining is null)
const SecondsBudgetNoticeSchema = z.object({
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
});

// Schema for tool loop detection rounds (integers, strictly bound to run budget_scope)
const ToolLoopBudgetNoticeSchema = z.object({
  version: z.literal(1),
  type: z.literal("runtime_budget_notice"),
  notice_id: z.string().min(1).max(256),
  run_id: z.string().min(1).max(128),
  scope: z.enum(["primary", "subagent"]),
  budget_scope: z.literal("run"),
  code: z.enum(["tool_loop_approaching", "tool_loop_reached"]),
  limit: z.number().int().positive(),
  used: z.number().int().nonnegative(),
  remaining: z.number().int().nonnegative(),
  unit: z.literal("tool_rounds"),
});

export const BudgetNoticeSchema = z.discriminatedUnion("unit", [
  StepOrCallBudgetNoticeSchema,
  SecondsBudgetNoticeSchema,
  ToolLoopBudgetNoticeSchema,
]);

export type BudgetNotice = z.infer<typeof BudgetNoticeSchema>;

export const BudgetSafetyErrorSchema = z.object({
  type: z.string().optional(),
  code: z.enum(BUDGET_SAFETY_ERROR_CODES),
  message: z.string().optional(),
});

export type BudgetSafetyError = z.infer<typeof BudgetSafetyErrorSchema>;

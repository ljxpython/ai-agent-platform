import { platformHttpClient as http } from "@/services/http/client";

export type EvaluationCase = {
  case_id: string;
  schema_version: string;
  turns: { content: string; approval?: string; approval_mode?: string }[];
  fixture: Record<string, string>;
  business_rules?: string[];
  rubric_version?: string;
  turn_expectations?: {
    index: number;
    answer_equals?: string | null;
    answer_contains: string[];
    answer_excludes: string[];
    artifacts: Record<string, unknown>;
  }[];
  expectations: { answer_contains?: string[]; [key: string]: unknown };
  metrics: { name: string; hard_gate?: boolean }[];
  [key: string]: unknown;
};
export type Proposal = {
  summary: string;
  facts: string[];
  hypotheses: string[];
  changes: string[];
  missing_information: string[];
  case_missing_information?: Record<string, string[]>;
  cases: EvaluationCase[];
  excluded: string[];
};
export type Version = {
  revision: number;
  content_hash: string;
  source: string;
  created_at: number;
  proposal: Proposal;
};
export type Job = {
  id: string;
  status: string;
  intent: string;
  created_by: string;
  created_at: number;
  task_id?: string;
  feedback: string;
};
export type Operation = {
  id: string;
  stage: string;
  revision: number;
  selected_case_ids: string[];
  excluded_case_ids?: string[];
  source_task_id?: string | null;
  content_hash: string;
  created_by: string;
  created_at: number;
  dataset_id?: string;
  dataset_version?: number;
  task_id?: string;
};
export type Metric = {
  name: string;
  status: string;
  score?: number;
  reason: string;
};
export type CaseResult = {
  case_id: string;
  evidence_ref: string;
  status: string;
  inputs: string[];
  outputs: string[];
  artifacts?: Record<string, { content: string | null; truncated: boolean }>;
  errors: string[];
  results: Metric[];
};
export type PendingAction = {
  id: string;
  case_id: string;
  revision: number;
  parameters_hash: string;
  assignee: string;
  status: string;
  expires_at: number;
  interrupts: {
    id: string;
    value: {
      action_requests?: { name: string; args: Record<string, unknown> }[];
    };
  }[];
};
export type Result = {
  task_id: string;
  name: string;
  status: string;
  completed: number;
  total: number;
  created_at: number;
  error?: string;
  cases: CaseResult[];
  pending_actions: PendingAction[];
  gate?: { status: string };
  evidence?: {
    approved_standard?: {
      dataset_name: string;
      version: number;
      review_note: string;
      cases: EvaluationCase[];
    };
  };
};
export type Judgment = {
  revision: number;
  task_id: string;
  kind: string;
  source: string;
  reason?: string;
  actor_id: string;
  at: number;
  explanation?: {
    summary: string;
    findings: string[];
    limitations: string[];
    evidence_refs: string[];
  };
};
export type WorkItem = {
  id: string;
  project_id: string;
  title: string;
  description?: string;
  agent_id: string;
  created_by: string;
  status: string;
  revision: number;
  next_action?: string;
  source_changed?: boolean;
  updated_at: number;
  assignee?: string;
  grants: Record<string, string>;
  versions?: Version[];
  assistant_jobs?: Job[];
  operations?: Operation[];
  results?: Result[];
  judgments?: Judgment[];
  regression_set?: boolean;
  history?: {
    request_id?: string;
    action: string;
    actor_id: string;
    source: string;
    at: number;
    reason?: string;
  }[];
  comparison?: {
    compatible: boolean;
    reason?: string;
    cases?: { case_id: string; before: Metric[]; after: Metric[] }[];
  };
};
export type Summary = {
  work_items: number;
  runs: number;
  completed_runs: number;
  statuses: Record<string, number>;
  failure_metrics: Record<string, number>;
  notes: string[];
  inspection: {
    enabled: boolean;
    reason: string;
    notes?: string;
    results?: {
      id: string;
      agent_id: string;
      score: number;
      policy_version: string;
      created_at: number;
    }[];
  };
};
export type Command = { request_id: string; data: Record<string, unknown> };
const base = "/api/evaluation";
const scope = (project: string) => ({ headers: { "x-project-id": project } });
export async function listWorkItems(
  project: string,
  params: Record<string, string | number>,
) {
  return (
    await http.get<{ items: WorkItem[]; total: number }>(`${base}/work-items`, {
      ...scope(project),
      params,
    })
  ).data;
}
export async function readWorkItem(project: string, id: string) {
  return (
    await http.get<WorkItem>(
      `${base}/work-items/${encodeURIComponent(id)}`,
      scope(project),
    )
  ).data;
}
export async function commandWorkItem(
  project: string,
  id: string | null,
  action: string,
  command: Command,
) {
  const path = id
    ? `${base}/work-items/${encodeURIComponent(id)}/${encodeURIComponent(action)}`
    : `${base}/work-items`;
  return (await http.post<WorkItem>(path, command, scope(project))).data;
}
export async function readSummary(project: string) {
  return (await http.get<Summary>(`${base}/workbench-summary`, scope(project)))
    .data;
}
export async function workbenchCapabilities(project: string) {
  return (
    await http.get<{ workbench: boolean; assistant_model?: string }>(
      `${base}/capabilities`,
      scope(project),
    )
  ).data;
}
export const statusLabel = (value: string) =>
  ({
    awaiting_authorization: "待授权",
    ready_to_draft: "待生成方案",
    drafting: "AI整理中",
    awaiting_review: "待评审",
    needs_information: "待补充口径",
    preparing: "准备验证",
    approved: "方案已批准",
    publishing: "固定题库中",
    starting: "启动中",
    running: "验证中",
    waiting_for_approval: "等待工具审批",
    completed: "验证已结束",
    cancelling: "正在取消",
    cancelled: "已取消",
    error: "执行异常",
    failed: "有未通过项",
    passed: "通过",
    pass: "通过",
    fail: "未通过",
    withdrawn: "已撤回问题",
    deferred: "暂不处理",
    materials_unavailable: "资料已失效",
    pending: "待处理",
    decided: "已决定",
    resumed: "已续跑",
    expired: "已过期",
    reserved: "待启动",
    superseded: "已被新版替代",
    timed_out: "已超时",
  })[value] || value;

export const evaluationCheckLabels: Record<string, string> = {
  BusinessFacts: "事实与因果",
  EvidenceBoundary: "资料边界",
  RecommendationGrounding: "建议依据",
  turn_expectations: "逐轮答案",
  completion: "运行完成",
  artifact_correct: "文件内容",
  protected_unchanged: "源文件保持不变",
  approval: "审批要求",
  tool_constraints: "工具与参数",
  tool_budget: "工具次数",
  TaskCompletion: "任务完成质量",
  KnowledgeRetention: "多轮记忆",
  equals: "内容完全等于",
  contains: "内容必须包含",
  json_equals: "JSON内容等于",
  absent: "文件不得存在",
  unchanged: "保持原内容",
  kind: "检查方法",
};

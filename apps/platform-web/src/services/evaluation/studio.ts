import { platformApiBaseUrl, platformHttpClient } from "@/services/http/client";
import { createLanggraphAuthorizedFetch } from "@/services/langgraph/client";
import type { RuntimeModelItem } from "@/types/management";

export interface EvalSuiteVersionSummary {
  id: string;
  suite_id: string;
  version_num: number;
  content_hash: string;
  case_count: number;
  published_by: string;
  published_at: string | null;
}

export interface EvalSampleCasePreview {
  id: string;
  case_key: string;
  split: "dev" | "holdout";
  mode: "fixed" | "simulation";
  question: string;
  ground_truth: string;
  metrics_count: number;
}

export interface EvalSuiteItem {
  id: string;
  name: string;
  description: string;
  suite_type: "golden" | "regression" | "curated" | "benchmark";
  owner_project_id: string;
  owner_project_name?: string | null;
  source_project_id: string | null;
  source_project_name?: string | null;
  default_graph_id:
    | "dearflow_agent"
    | "showcase_demo"
    | "reference_agent"
    | "workflow_demo";
  created_by: string;
  archived_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  case_count?: number;
  runs_count?: number;
  best_score?: number | null;
  latest_score?: number | null;
  sample_cases?: EvalSampleCasePreview[];
  latest_version?: EvalSuiteVersionSummary | null;
}

export interface EvalCaseItem {
  id: string;
  suite_id: string;
  case_key: string;
  split: "dev" | "holdout";
  schema_version: string;
  required_capabilities: string[];
  turns: Array<Record<string, unknown>>;
  simulation: Record<string, unknown> | null;
  expectations: Record<string, unknown>;
  metrics: Array<Record<string, unknown> | string>;
  metadata: Record<string, unknown>;
  updated_at: string | null;
}

export interface EvalRunProgress {
  total: number;
  active_total?: number;
  done: number;
  completed: number;
  failed: number;
  error: number;
  running: number;
  pending: number;
  paused: number;
  cancelled: number;
  skipped_incompatible: number;
  percent: number;
}

export interface EvalRunLogEntry {
  seq: number;
  level: "INFO" | "WARN" | "ERROR" | string;
  case_key: string | null;
  message: string;
  created_at: string | null;
}

export interface EvalRunLogsResponse {
  run_id: string;
  status: string;
  progress: EvalRunProgress;
  logs: EvalRunLogEntry[];
  last_seq: number;
}

export interface EvalRunItem {
  id: string;
  suite_id: string;
  suite_name?: string | null;
  version_id: string;
  version_num?: number | null;
  owner_project_id: string;
  target_project_id: string;
  target_project_name?: string | null;
  target_graph_id: string;
  target_agent_id: string;
  target_model_id: string;
  target_model_name?: string | null;
  judge_model_id: string | null;
  judge_model_name?: string | null;
  embedding_model_id: string | null;
  matrix_group_id: string | null;
  trigger_type?: string;
  patrol_schedule_id?: string | null;
  patrol_name?: string | null;
  mode: string;
  concurrency: number;
  repeat_k: number;
  status: string;
  gate_exit_code: number | null;
  summary_metrics: Record<string, unknown>;
  created_by: string;
  created_at: string | null;
  finished_at: string | null;
}

export interface EvalRunCaseItem {
  id: string;
  run_id: string;
  case_key: string;
  attempt_idx: number;
  status: string;
  thread_id: string | null;
  trace_ids: string[];
  rule_passed: boolean | null;
  overall_score: number | null;
  duration_ms: number | null;
  ttft_ms: number | null;
  token_usage: Record<string, unknown>;
  cost_usd: number | null;
  error_category: string | null;
  evidence_path: string | null;
  results: Record<string, unknown>;
}

export interface ReadinessResult {
  ready: boolean;
  target_project_id: string;
  graph_id: string;
  graph_features: Record<string, boolean>;
  is_sandbox: boolean;
  sandbox_warning: string | null;
  missing_models: string[];
  incompatible_cases: Array<{
    case_key: string;
    missing_capabilities: string[];
  }>;
}

export interface CompareSidePayload {
  status: string;
  rule_passed: boolean | null;
  overall_score: number | null;
  ttft_ms: number | null;
  duration_ms: number | null;
  cost_usd: number | null;
  token_usage?: Record<string, unknown>;
  error_category?: string | null;
  final_answer?: string | null;
  metrics?: Array<Record<string, unknown>>;
  timing_breakdown?: Record<string, number | null>;
  transcript?: Array<Record<string, unknown>>;
  thread_id?: string | null;
  trace_ids?: string[];
}

export interface CompareDiffCaseItem {
  case_key: string;
  attempt_idx: number;
  mode?: string;
  question?: string;
  expected_answer?: string;
  baseline_score: number | null;
  candidate_score: number | null;
  baseline_status?: string | null;
  candidate_status?: string | null;
  baseline_ttft_ms?: number | null;
  candidate_ttft_ms?: number | null;
  baseline_duration_ms?: number | null;
  candidate_duration_ms?: number | null;
  baseline?: CompareSidePayload | null;
  candidate?: CompareSidePayload | null;
}

export interface CompareRunsResult {
  compatible: boolean;
  baseline: EvalRunItem;
  candidate: EvalRunItem;
  counts: { regressed: number; improved: number; unchanged: number };
  regressed: CompareDiffCaseItem[];
  improved: CompareDiffCaseItem[];
  unchanged: CompareDiffCaseItem[];
}

export interface PatrolGateConfigPayload {
  min_tsr: number;
  min_l1_pass_rate: number;
  max_loop_rate: number;
  max_p95_ttft_ms: number | null;
  regression_drop_threshold: number;
  ttft_spike_ratio: number;
  consecutive_alert_threshold: number;
}

export interface PatrolScheduleItem {
  id: string;
  name: string;
  suite_id: string;
  suite_name?: string | null;
  version_id: string | null;
  version_policy: "latest_published" | "pinned";
  owner_project_id: string;
  target_project_id: string;
  target_project_name?: string | null;
  target_graph_id: string;
  target_agent_id: string | null;
  target_agent_name?: string | null;
  target_model_id: string | null;
  target_model_name?: string | null;
  judge_model_id: string | null;
  judge_model_name?: string | null;
  embedding_model_id: string | null;
  case_keys: string[];
  concurrency: number;
  repeat_k: number;
  skip_incompatible: boolean;
  confirm_non_sandbox: boolean;
  cron_expr: string;
  timezone: string;
  enabled: boolean;
  concurrency_policy: "forbid" | "allow";
  gate_config: Partial<PatrolGateConfigPayload>;
  notify_channels: string[];
  notify_on_recovery: boolean;
  next_run_at: string | null;
  last_triggered_at: string | null;
  last_status: string;
  last_message: string;
  consecutive_failures: number;
  last_run_id: string | null;
  last_run_status?: string | null;
  last_run_gate_exit_code?: number | null;
  last_run_score?: number | null;
  created_by: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface PatrolCreatePayload {
  name: string;
  suite_id: string;
  version_policy: "latest_published" | "pinned";
  version_id?: string | null;
  target_project_id: string;
  target_graph_id?: EvalSuiteItem["default_graph_id"] | null;
  target_agent_id: string;
  target_model_id: string;
  judge_model_id?: string | null;
  embedding_model_id?: string | null;
  case_keys?: string[];
  concurrency?: number;
  repeat_k?: number;
  skip_incompatible?: boolean;
  confirm_non_sandbox?: boolean;
  cron_expr: string;
  timezone?: string;
  enabled?: boolean;
  concurrency_policy?: "forbid" | "allow";
  gate_config?: Partial<PatrolGateConfigPayload>;
  notify_channels?: string[];
  notify_on_recovery?: boolean;
}

export type PatrolUpdatePayload = Partial<
  Omit<PatrolCreatePayload, "suite_id">
>;

export interface CronPreviewResult {
  cron_expr: string;
  timezone: string;
  next_runs: string[];
  next_runs_utc: string[];
}

export interface CaseUpsertPayload {
  case_key: string;
  split: "dev" | "holdout";
  turns: Array<Record<string, unknown>>;
  simulation: Record<string, unknown> | null;
  expectations: Record<string, unknown>;
  metrics: Array<Record<string, unknown> | string>;
  metadata?: Record<string, unknown>;
}

function projectHeaders(projectId: string) {
  return { "X-Project-Id": projectId };
}

export function isFaultInjectionTestModel(
  model: Pick<RuntimeModelItem, "model" | "display_name">,
): boolean {
  const m = (model.model || "").toLowerCase();
  const d = (model.display_name || "").toLowerCase();
  return (
    m.includes("broken") || d.includes("故障测试") || d.includes("模拟宕机")
  );
}

export function pickPreferredDeepSeekModelId(
  models: RuntimeModelItem[],
): string {
  const enabled = models.filter(
    (m) => m.enabled && !isFaultInjectionTestModel(m),
  );
  const candidates =
    enabled.length > 0 ? enabled : models.filter((m) => m.enabled);
  const exactChickener = candidates.find(
    (m) =>
      m.provider.toLowerCase() === "chickener" &&
      (m.model.toLowerCase().includes("deepseek") ||
        m.display_name.toLowerCase().includes("deepseek")),
  );
  if (exactChickener) return exactChickener.id;
  const anyChickener = candidates.find(
    (m) => m.provider.toLowerCase() === "chickener",
  );
  if (anyChickener) return anyChickener.id;
  const exactXiaok = candidates.find(
    (m) =>
      m.provider.toLowerCase() === "xiaok" &&
      (m.model.toLowerCase().includes("deepseek") ||
        m.display_name.toLowerCase().includes("deepseek")),
  );
  if (exactXiaok) return exactXiaok.id;
  const anyXiaok = candidates.find(
    (m) =>
      m.provider.toLowerCase() === "xiaok" ||
      m.display_name.toLowerCase().includes("xiaok"),
  );
  if (anyXiaok) return anyXiaok.id;
  const anyDeepSeek = candidates.find(
    (m) =>
      m.model.toLowerCase().includes("deepseek") ||
      m.display_name.toLowerCase().includes("deepseek"),
  );
  if (anyDeepSeek) return anyDeepSeek.id;
  return candidates[0]?.id ?? "";
}

export async function listSuites(projectId: string): Promise<EvalSuiteItem[]> {
  const { data } = await platformHttpClient.get<{ items: EvalSuiteItem[] }>(
    "/api/evaluation/studio/suites",
    { headers: projectHeaders(projectId) },
  );
  return data.items;
}

export async function createSuite(
  projectId: string,
  payload: {
    name: string;
    description: string;
    suite_type: EvalSuiteItem["suite_type"];
    default_graph_id: EvalSuiteItem["default_graph_id"];
  },
): Promise<EvalSuiteItem> {
  const { data } = await platformHttpClient.post<EvalSuiteItem>(
    "/api/evaluation/studio/suites",
    payload,
    { headers: projectHeaders(projectId) },
  );
  return data;
}

export async function archiveSuite(
  projectId: string,
  suiteId: string,
): Promise<void> {
  await platformHttpClient.delete(`/api/evaluation/studio/suites/${suiteId}`, {
    headers: projectHeaders(projectId),
  });
}

export async function createSuiteFromSessions(
  projectId: string,
  payload: {
    name: string;
    description?: string;
    suite_type?: EvalSuiteItem["suite_type"];
    source_project_id?: string;
    default_graph_id?: EvalSuiteItem["default_graph_id"];
    thread_ids: string[];
    agent_id?: string;
  },
): Promise<{
  suite: EvalSuiteItem;
  cases: EvalCaseItem[];
  versions: EvalSuiteVersionSummary[];
}> {
  const { data } = await platformHttpClient.post<{
    suite: EvalSuiteItem;
    cases: EvalCaseItem[];
    versions: EvalSuiteVersionSummary[];
  }>("/api/evaluation/studio/suites/from-sessions", payload, {
    headers: projectHeaders(projectId),
  });
  return data;
}

export async function getSuiteDetail(
  projectId: string,
  suiteId: string,
): Promise<{
  suite: EvalSuiteItem;
  cases: EvalCaseItem[];
  versions: EvalSuiteVersionSummary[];
}> {
  const { data } = await platformHttpClient.get<{
    suite: EvalSuiteItem;
    cases: EvalCaseItem[];
    versions: EvalSuiteVersionSummary[];
  }>(`/api/evaluation/studio/suites/${suiteId}`, {
    headers: projectHeaders(projectId),
  });
  return data;
}

export async function upsertCase(
  projectId: string,
  suiteId: string,
  payload: CaseUpsertPayload,
): Promise<EvalCaseItem> {
  const { data } = await platformHttpClient.put<EvalCaseItem>(
    `/api/evaluation/studio/suites/${suiteId}/cases`,
    payload,
    { headers: projectHeaders(projectId) },
  );
  return data;
}

export async function importSuiteCases(
  projectId: string,
  suiteId: string,
  items: CaseUpsertPayload[],
): Promise<{ imported: number; items: EvalCaseItem[] }> {
  const { data } = await platformHttpClient.post<{
    imported: number;
    items: EvalCaseItem[];
  }>(
    `/api/evaluation/studio/suites/${suiteId}/cases/import`,
    { items },
    { headers: projectHeaders(projectId) },
  );
  return data;
}

export async function deleteCase(
  projectId: string,
  suiteId: string,
  caseKey: string,
): Promise<void> {
  await platformHttpClient.delete(
    `/api/evaluation/studio/suites/${suiteId}/cases/${encodeURIComponent(caseKey)}`,
    { headers: projectHeaders(projectId) },
  );
}

export async function publishSuiteVersion(
  projectId: string,
  suiteId: string,
  note = "",
): Promise<EvalSuiteVersionSummary> {
  const { data } = await platformHttpClient.post<EvalSuiteVersionSummary>(
    `/api/evaluation/studio/suites/${suiteId}/publish`,
    { note },
    { headers: projectHeaders(projectId) },
  );
  return data;
}

export async function checkReadiness(
  projectId: string,
  payload: {
    suite_id: string;
    target_project_id: string;
    agent_id: string;
    model_id: string;
    judge_model_id?: string | null;
    embedding_model_id?: string | null;
    case_keys?: string[];
  },
): Promise<ReadinessResult> {
  const { data } = await platformHttpClient.post<ReadinessResult>(
    "/api/evaluation/studio/readiness",
    payload,
    { headers: projectHeaders(projectId) },
  );
  return data;
}

export async function createRun(
  projectId: string,
  payload: {
    suite_id: string;
    version_id: string;
    target_project_id: string;
    agent_id: string;
    model_id: string;
    judge_model_id?: string | null;
    embedding_model_id?: string | null;
    concurrency: number;
    repeat_k: number;
    confirm_non_sandbox: boolean;
    skip_incompatible: boolean;
    case_keys?: string[];
  },
): Promise<EvalRunItem> {
  const { data } = await platformHttpClient.post<EvalRunItem>(
    "/api/evaluation/studio/runs",
    payload,
    { headers: projectHeaders(projectId) },
  );
  return data;
}

export async function createMatrixRuns(
  projectId: string,
  payload: {
    suite_id: string;
    version_id: string;
    target_project_id: string;
    judge_model_id?: string | null;
    embedding_model_id?: string | null;
    concurrency: number;
    repeat_k: number;
    confirm_non_sandbox: boolean;
    variants: Array<{ agent_id: string; model_id: string; label?: string }>;
    case_keys?: string[];
  },
): Promise<{ matrix_group_id: string; runs: EvalRunItem[] }> {
  const { data } = await platformHttpClient.post<{
    matrix_group_id: string;
    runs: EvalRunItem[];
  }>("/api/evaluation/studio/runs/matrix", payload, {
    headers: projectHeaders(projectId),
  });
  return data;
}

export async function listRuns(
  projectId: string,
  suiteId?: string,
): Promise<EvalRunItem[]> {
  const { data } = await platformHttpClient.get<{ items: EvalRunItem[] }>(
    "/api/evaluation/studio/runs",
    {
      headers: projectHeaders(projectId),
      params: suiteId ? { suite_id: suiteId } : undefined,
    },
  );
  return data.items;
}

export async function getRunDetail(
  projectId: string,
  runId: string,
): Promise<{ run: EvalRunItem; cases: EvalRunCaseItem[] }> {
  const { data } = await platformHttpClient.get<{
    run: EvalRunItem;
    cases: EvalRunCaseItem[];
  }>(`/api/evaluation/studio/runs/${runId}`, {
    headers: projectHeaders(projectId),
  });
  return data;
}

export async function controlRun(
  projectId: string,
  runId: string,
  action: "pause" | "resume" | "retry_failed" | "rescore" | "cancel",
): Promise<EvalRunItem> {
  const { data } = await platformHttpClient.post<EvalRunItem>(
    `/api/evaluation/studio/runs/${runId}/control`,
    { action },
    { headers: projectHeaders(projectId) },
  );
  return data;
}

export async function deleteRun(
  projectId: string,
  runId: string,
): Promise<{ deleted: boolean; run_id: string }> {
  const { data } = await platformHttpClient.delete<{
    deleted: boolean;
    run_id: string;
  }>(`/api/evaluation/studio/runs/${runId}`, {
    headers: projectHeaders(projectId),
  });
  return data;
}

export async function getRunLogs(
  projectId: string,
  runId: string,
  params?: {
    after_seq?: number;
    limit?: number;
    case_key?: string;
    level?: string;
  },
): Promise<EvalRunLogsResponse> {
  const { data } = await platformHttpClient.get<EvalRunLogsResponse>(
    `/api/evaluation/studio/runs/${runId}/logs`,
    {
      headers: projectHeaders(projectId),
      params,
    },
  );
  return data;
}

export async function compareRuns(
  projectId: string,
  baselineId: string,
  candidateId: string,
): Promise<CompareRunsResult> {
  const { data } = await platformHttpClient.get<CompareRunsResult>(
    "/api/evaluation/studio/runs/compare",
    {
      headers: projectHeaders(projectId),
      params: { baseline_id: baselineId, candidate_id: candidateId },
    },
  );
  return data;
}

export async function submitHumanReview(
  projectId: string,
  runCaseId: string,
  payload: { human_verdict: "pass" | "fail"; reason: string },
): Promise<void> {
  await platformHttpClient.post(
    `/api/evaluation/studio/run-cases/${runCaseId}/review`,
    payload,
    { headers: projectHeaders(projectId) },
  );
}

export async function listPatrols(
  projectId: string,
): Promise<PatrolScheduleItem[]> {
  const { data } = await platformHttpClient.get<{
    items: PatrolScheduleItem[];
  }>("/api/evaluation/studio/patrols", { headers: projectHeaders(projectId) });
  return data.items;
}

export async function createPatrol(
  projectId: string,
  payload: PatrolCreatePayload,
): Promise<PatrolScheduleItem> {
  const { data } = await platformHttpClient.post<PatrolScheduleItem>(
    "/api/evaluation/studio/patrols",
    payload,
    {
      headers: projectHeaders(projectId),
    },
  );
  return data;
}

export async function updatePatrol(
  projectId: string,
  scheduleId: string,
  payload: PatrolUpdatePayload,
): Promise<PatrolScheduleItem> {
  const { data } = await platformHttpClient.patch<PatrolScheduleItem>(
    `/api/evaluation/studio/patrols/${scheduleId}`,
    payload,
    { headers: projectHeaders(projectId) },
  );
  return data;
}

export async function deletePatrol(
  projectId: string,
  scheduleId: string,
): Promise<{ deleted: boolean; id: string }> {
  const { data } = await platformHttpClient.delete<{
    deleted: boolean;
    id: string;
  }>(`/api/evaluation/studio/patrols/${scheduleId}`, {
    headers: projectHeaders(projectId),
  });
  return data;
}

export async function triggerPatrol(
  projectId: string,
  scheduleId: string,
): Promise<{
  status: string;
  run: EvalRunItem;
  schedule: PatrolScheduleItem;
}> {
  const { data } = await platformHttpClient.post<{
    status: string;
    run: EvalRunItem;
    schedule: PatrolScheduleItem;
  }>(
    `/api/evaluation/studio/patrols/${scheduleId}/trigger`,
    {},
    { headers: projectHeaders(projectId) },
  );
  return data;
}

export async function previewPatrolCron(
  projectId: string,
  payload: { cron_expr: string; timezone?: string; count?: number },
): Promise<CronPreviewResult> {
  const { data } = await platformHttpClient.post<CronPreviewResult>(
    "/api/evaluation/studio/patrols/cron-preview",
    payload,
    { headers: projectHeaders(projectId) },
  );
  return data;
}

export async function setSandboxFlag(
  projectId: string,
  isSandbox: boolean,
): Promise<{ project_id: string; is_sandbox: boolean }> {
  const { data } = await platformHttpClient.put<{
    project_id: string;
    is_sandbox: boolean;
  }>(
    "/api/evaluation/studio/sandbox",
    { is_sandbox: isSandbox },
    { headers: projectHeaders(projectId) },
  );
  return data;
}

export interface ExpertThreadItem {
  thread_id: string;
  title: string;
  ref_id?: string | null;
  status: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export async function listExpertThreads(
  projectId: string,
  graphId: "eval_copilot" | "eval_diagnosis",
  refId?: string | null,
): Promise<ExpertThreadItem[]> {
  const { data } = await platformHttpClient.get<{ items: ExpertThreadItem[] }>(
    "/api/evaluation/studio/experts/threads",
    {
      params: {
        graph_id: graphId,
        ...(refId ? { ref_id: refId } : {}),
      },
      headers: projectHeaders(projectId),
    },
  );
  return data.items ?? [];
}

export async function createExpertThread(
  projectId: string,
  graphId: "eval_copilot" | "eval_diagnosis",
  title = "",
  refId?: string | null,
): Promise<{ thread_id: string }> {
  const { data } = await platformHttpClient.post<{ thread_id: string }>(
    "/api/evaluation/studio/experts/threads",
    { graph_id: graphId, title, ...(refId ? { ref_id: refId } : {}) },
    { headers: projectHeaders(projectId) },
  );
  return data;
}

export async function getExpertThreadState(
  projectId: string,
  threadId: string,
): Promise<{
  thread_id: string;
  status?: string | null;
  interrupts: ExpertInterruptRequest[];
  messages: Array<{ id: string; role: "user" | "assistant"; content: string }>;
}> {
  const { data } = await platformHttpClient.get<{
    thread_id: string;
    status?: string | null;
    interrupts?: unknown;
    messages?: Array<{
      id: string;
      role: "user" | "assistant";
      content: string;
    }>;
  }>(
    `/api/evaluation/studio/experts/threads/${encodeURIComponent(threadId)}/state`,
    { headers: projectHeaders(projectId) },
  );
  return {
    thread_id: data.thread_id,
    status: data.status,
    interrupts: data.interrupts ? parseExpertInterrupts(data.interrupts) : [],
    messages: Array.isArray(data.messages) ? data.messages : [],
  };
}

function extractTextBlocks(content: unknown): string {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .filter(
        (b): b is { type?: string; text?: string } =>
          Boolean(b) &&
          typeof b === "object" &&
          (b as { type?: string }).type === "text",
      )
      .map((b) => b.text ?? "")
      .join("");
  }
  return "";
}

function unwrapExpertChunk(
  rawEventName: string,
  parsed: unknown,
): { method: string; data: unknown } {
  const baseEvent = rawEventName.split("|")[0] || "";
  if (
    parsed &&
    typeof parsed === "object" &&
    "method" in parsed &&
    typeof (parsed as { method?: unknown }).method === "string" &&
    "params" in parsed &&
    (parsed as { params?: unknown }).params &&
    typeof (parsed as { params: unknown }).params === "object"
  ) {
    const params = (
      parsed as { method: string; params: Record<string, unknown> }
    ).params;
    const method = baseEvent || (parsed as { method: string }).method;
    return { method, data: "data" in params ? params.data : params };
  }
  return { method: baseEvent, data: parsed };
}

function extractDeltaFromMessagesArray(items: unknown[]): string {
  let out = "";
  for (const item of items) {
    if (!item || typeof item !== "object") continue;
    const obj = item as Record<string, unknown>;
    if (obj.event === "message-start") continue;
    if (obj.delta && typeof obj.delta === "object") {
      const text = (obj.delta as { text?: unknown }).text;
      if (typeof text === "string") out += text;
    } else if (typeof obj.delta === "string") {
      out += obj.delta;
    } else if (typeof obj.text === "string") {
      out += obj.text;
    } else if (
      obj.content &&
      (obj.role === "assistant" || obj.type === "ai" || !obj.role)
    ) {
      out += extractTextBlocks(obj.content);
    }
  }
  return out;
}

function extractLastAssistantFromValues(payload: unknown): string {
  if (!payload || typeof payload !== "object") return "";
  const msgs = (payload as { messages?: unknown }).messages;
  if (!Array.isArray(msgs)) return "";
  for (let i = msgs.length - 1; i >= 0; i--) {
    const item = msgs[i] as Record<string, unknown> | undefined;
    if (!item || typeof item !== "object") continue;
    const role = String(item.role ?? item.type ?? "");
    if (role === "assistant" || role === "ai") {
      const text = extractTextBlocks(item.content);
      if (text.trim()) return text;
    }
  }
  return "";
}

export interface ExpertInterruptRequest {
  id: string;
  actionName: string;
  argsSummary: string;
  description: string;
  raw: Record<string, unknown>;
}

export async function uploadExpertMaterial(
  projectId: string,
  threadId: string,
  file: File,
): Promise<{ path?: string; file_path?: string; sha256?: string }> {
  const authorizedFetch = createLanggraphAuthorizedFetch();
  const base = platformApiBaseUrl.replace(/\/+$/, "");
  const url = `${base}/api/evaluation/studio/experts/threads/${encodeURIComponent(threadId)}/upload?file_name=${encodeURIComponent(file.name)}`;
  const response = await authorizedFetch(url, {
    method: "POST",
    headers: {
      "content-type": file.type || "application/octet-stream",
      "x-project-id": projectId,
    },
    body: file,
  });
  if (!response.ok) {
    throw new Error(`参考资料上传失败 (${response.status})`);
  }
  return (await response.json()) as {
    path?: string;
    file_path?: string;
    sha256?: string;
  };
}

function parseExpertInterrupts(raw: unknown): ExpertInterruptRequest[] {
  const out: ExpertInterruptRequest[] = [];
  const pushItem = (id: string, val: unknown) => {
    if (!val || typeof val !== "object") return;
    const v = val as Record<string, unknown>;
    const actions = Array.isArray(v.action_requests)
      ? (v.action_requests as Array<Record<string, unknown>>)
      : [];
    const configs = Array.isArray(v.review_configs)
      ? (v.review_configs as Array<Record<string, unknown>>)
      : [];
    const firstAct = actions[0] ?? {};
    const firstCfg = configs[0] ?? {};
    const actionName = String(firstAct.name || v.name || "sensitive_action");
    const argsObj = firstAct.args ?? firstAct.arguments ?? {};
    const argsStr =
      typeof argsObj === "string" ? argsObj : JSON.stringify(argsObj);
    out.push({
      id: id || `int-${out.length + 1}`,
      actionName,
      argsSummary: argsStr.slice(0, 260),
      description: String(
        firstAct.description ||
          firstCfg.description ||
          "该操作将写入题库或发起定向试跑，请确认是否允许。",
      ),
      raw: v,
    });
  };

  if (Array.isArray(raw)) {
    for (let i = 0; i < raw.length; i++) {
      const item = raw[i] as Record<string, unknown> | undefined;
      if (!item || typeof item !== "object") continue;
      pushItem(String(item.id || `int-${i + 1}`), item.value ?? item);
    }
  } else if (raw && typeof raw === "object") {
    for (const [k, v] of Object.entries(raw as Record<string, unknown>)) {
      if (v && typeof v === "object" && "value" in (v as object)) {
        const inner = v as Record<string, unknown>;
        pushItem(String(inner.id || k), inner.value);
      } else {
        pushItem(k, v);
      }
    }
  }
  return out;
}

function scanToolOutcomesFromValues(
  payload: unknown,
  seenToolCallIds: Set<string>,
  callbacks: {
    onCasesMutated?: () => void;
    onTrialRun?: (runId: string) => void;
    onTrialRunUpdated?: () => void;
  },
) {
  if (!payload || typeof payload !== "object") return;
  const msgs = (payload as { messages?: unknown }).messages;
  if (!Array.isArray(msgs)) return;
  for (const item of msgs) {
    if (!item || typeof item !== "object") continue;
    const msg = item as Record<string, unknown>;
    const role = String(msg.role ?? msg.type ?? "").toLowerCase();
    if (role !== "tool") continue;
    const callId = String(msg.tool_call_id ?? msg.id ?? "");
    const dedupKey =
      callId || `${msg.name}:${String(msg.content).slice(0, 80)}`;
    if (seenToolCallIds.has(dedupKey)) continue;
    seenToolCallIds.add(dedupKey);
    const toolName = String(msg.name ?? "");
    const rawContent = extractTextBlocks(msg.content);
    let parsed: Record<string, unknown> | null = null;
    try {
      const candidate = JSON.parse(rawContent);
      if (candidate && typeof candidate === "object") {
        parsed = candidate as Record<string, unknown>;
      }
    } catch {
      parsed = null;
    }
    if (
      (toolName === "create_new_eval_cases" ||
        toolName === "update_existing_eval_cases") &&
      parsed &&
      "suite_id" in parsed
    ) {
      callbacks.onCasesMutated?.();
    } else if (
      toolName === "launch_trial_run" &&
      parsed &&
      typeof parsed.id === "string"
    ) {
      callbacks.onTrialRun?.(parsed.id);
    } else if (
      (toolName === "cancel_own_trial_run" ||
        toolName === "cancel_external_eval_run") &&
      parsed &&
      "status" in parsed
    ) {
      callbacks.onTrialRunUpdated?.();
    }
  }
}

export interface ExpertStreamCallbacks {
  onChunk: (fullText: string) => void;
  onError?: (message: string) => void;
  onInterrupt?: (interrupts: ExpertInterruptRequest[]) => void;
  onCasesMutated?: () => void;
  onTrialRun?: (runId: string) => void;
  onTrialRunUpdated?: () => void;
}

async function consumeExpertSseResponse(
  response: Response,
  callbacks: ExpertStreamCallbacks,
): Promise<string> {
  if (!response.ok || !response.body) {
    throw new Error(`专家会话请求失败 (${response.status})`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let eventName = "";
  let fullText = "";
  const seenToolOutcomes = new Set<string>();

  const processLine = (rawLine: string) => {
    const line = rawLine.trim();
    if (!line || line.startsWith(":")) return;
    if (line.startsWith("event:")) {
      eventName = line.slice(6).trim();
      return;
    }
    if (!line.startsWith("data:")) return;
    const dataStr = line.slice(5).trim();
    if (!dataStr) return;

    let parsed: unknown;
    try {
      parsed = JSON.parse(dataStr);
    } catch {
      return;
    }

    const { method, data } = unwrapExpertChunk(eventName, parsed);
    if (method === "error") {
      const msg = String(
        (data as { message?: string })?.message ?? "专家图执行出错",
      );
      callbacks.onError?.(msg);
      throw new Error(msg);
    }
    if (method === "lifecycle" && data && typeof data === "object") {
      const ev = data as {
        event?: string;
        status?: string;
        error?: { message?: string } | string;
        interrupts?: unknown;
      };
      if (ev.interrupts) {
        const list = parseExpertInterrupts(ev.interrupts);
        if (list.length > 0) callbacks.onInterrupt?.(list);
      }
      if (ev.event === "failed" || ev.status === "error") {
        const msg =
          typeof ev.error === "string"
            ? ev.error
            : String(ev.error?.message || "专家图执行失败");
        callbacks.onError?.(msg);
        throw new Error(msg);
      }
    }

    if (
      (method === "input.requested" || method === "input") &&
      data &&
      typeof data === "object"
    ) {
      const obj = data as Record<string, unknown>;
      const inner = (
        obj.data && typeof obj.data === "object" ? obj.data : obj
      ) as Record<string, unknown>;
      const intId = String(inner.interrupt_id ?? obj.interrupt_id ?? "");
      const val = inner.value ?? inner.payload ?? obj.value ?? inner;
      const list = parseExpertInterrupts(
        intId ? [{ id: intId, value: val }] : [val],
      );
      if (list.length > 0) callbacks.onInterrupt?.(list);
    }

    if (
      (method === "updates" || method === "values") &&
      data &&
      typeof data === "object"
    ) {
      const rawInt = (data as { __interrupt__?: unknown }).__interrupt__;
      if (rawInt) {
        const list = parseExpertInterrupts(rawInt);
        if (list.length > 0) callbacks.onInterrupt?.(list);
      }
    }

    if (method === "messages" && Array.isArray(data)) {
      const chunk = extractDeltaFromMessagesArray(data);
      if (chunk) {
        fullText += chunk;
        callbacks.onChunk(fullText);
      }
    } else if (method === "messages/partial" && Array.isArray(data)) {
      const last = data[data.length - 1] as Record<string, unknown> | undefined;
      if (last && (last.role === "assistant" || last.type === "ai")) {
        const text = extractTextBlocks(last.content);
        if (text) {
          fullText = text;
          callbacks.onChunk(fullText);
        }
      }
    } else if (method === "values") {
      scanToolOutcomesFromValues(data, seenToolOutcomes, callbacks);
      const valText = extractLastAssistantFromValues(data);
      if (valText) {
        fullText = valText;
        callbacks.onChunk(fullText);
      }
    } else if (method === "updates" && data && typeof data === "object") {
      for (const nodeVal of Object.values(data as Record<string, unknown>)) {
        if (nodeVal && typeof nodeVal === "object") {
          scanToolOutcomesFromValues(nodeVal, seenToolOutcomes, callbacks);
        }
      }
    }
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      if (buffer.trim()) processLine(buffer);
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split(/\r?\n/);
    buffer = lines.pop() ?? "";
    for (const raw of lines) {
      processLine(raw);
    }
  }
  return fullText;
}

export async function streamExpertTurn(
  projectId: string,
  threadId: string,
  payload: {
    graph_id: "eval_copilot" | "eval_diagnosis";
    content: string;
    model_id?: string | null;
    ref_id?: string | null;
  },
  callbacks: ExpertStreamCallbacks,
): Promise<string> {
  const authorizedFetch = createLanggraphAuthorizedFetch();
  const base = platformApiBaseUrl.replace(/\/+$/, "");
  const url = `${base}/api/evaluation/studio/experts/threads/${encodeURIComponent(threadId)}/stream`;
  const response = await authorizedFetch(url, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-project-id": projectId,
    },
    body: JSON.stringify(payload),
  });
  return consumeExpertSseResponse(response, callbacks);
}

export async function respondExpertInterrupt(
  projectId: string,
  threadId: string,
  payload: {
    graph_id: "eval_copilot" | "eval_diagnosis";
    command: { resume: Record<string, unknown> };
  },
  callbacks: ExpertStreamCallbacks,
): Promise<string> {
  const authorizedFetch = createLanggraphAuthorizedFetch();
  const base = platformApiBaseUrl.replace(/\/+$/, "");
  const url = `${base}/api/evaluation/studio/experts/threads/${encodeURIComponent(threadId)}/respond`;
  const response = await authorizedFetch(url, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-project-id": projectId,
    },
    body: JSON.stringify(payload),
  });
  return consumeExpertSseResponse(response, callbacks);
}

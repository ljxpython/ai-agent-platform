import { env } from "@/config/env";

export interface BuildLangfuseUrlOptions {
  projectId?: string;
  baseUrl?: string;
  template?: string;
}

export interface BuildMlflowUrlOptions {
  baseUrl?: string;
  experimentId?: string;
  projectId?: string;
  template?: string;
  threadId?: string;
  view?: "traces" | "sessions" | "trace";
}

const projectExperimentCache = new Map<string, string>();

/**
 * 获取本地缓存的项目 Experiment ID
 */
export function getProjectExperimentId(projectId?: string): string | undefined {
  if (!projectId) return undefined;
  return projectExperimentCache.get(projectId.trim());
}

/**
 * 设置或预注册项目的 Experiment ID 缓存
 */
export function setProjectExperimentId(
  projectId: string,
  experimentId: string,
): void {
  const p = projectId.trim();
  const e = experimentId.trim();
  if (p && e) {
    projectExperimentCache.set(p, e);
  }
}

export interface SessionTraceItem {
  requestId: string;
  timestampMs: number;
  sessionId?: string;
  runId?: string;
}

const sessionTracesCache = new Map<string, SessionTraceItem[]>();

export function clearSessionTracesCache(): void {
  sessionTracesCache.clear();
}

/**
 * 异步从 EvalFlow (MLflow) 按会话查询其真实的 Traces 列表（含原生 tr-xxxx Request ID）
 */
export async function fetchSessionTraces(
  experimentId: string,
  sessionId: string,
  baseUrl?: string,
): Promise<SessionTraceItem[]> {
  const expId = (experimentId || "").trim();
  const sId = (sessionId || "").trim();
  if (!expId || !sId) return [];

  const cacheKey = `${expId}:${sId}`;
  const base = (
    baseUrl ||
    env.mlflowBaseUrl ||
    "http://127.0.0.1:9128"
  ).replace(/\/+$/, "");

  try {
    const res = await fetch(
      `${base}/ajax-api/2.0/mlflow/traces?experiment_ids=${encodeURIComponent(expId)}`,
      { headers: { Accept: "application/json" } },
    );
    if (!res.ok) return sessionTracesCache.get(cacheKey) || [];

    const data = await res.json();
    const rawTraces: any[] = data?.traces || [];

    const matched: SessionTraceItem[] = [];
    for (const t of rawTraces) {
      const reqId = String(t.request_id || "").trim();
      const ts = Number(t.timestamp_ms || 0);
      const tags: Record<string, string> = {};
      for (const item of t.tags || []) {
        if (item?.key) tags[item.key] = String(item.value ?? "");
      }
      const metadata: Record<string, string> = {};
      for (const item of t.request_metadata || []) {
        if (item?.key) metadata[item.key] = String(item.value ?? "");
      }

      const traceSession =
        tags["mlflow.session_id"] ||
        tags["session_id"] ||
        metadata["thread_id"] ||
        metadata["mlflow.trace.session"];

      if (traceSession === sId && reqId.startsWith("tr-")) {
        matched.push({
          requestId: reqId,
          timestampMs: ts,
          sessionId: traceSession,
          runId: metadata["run_id"] || undefined,
        });
      }
    }

    matched.sort((a, b) => a.timestampMs - b.timestampMs);
    sessionTracesCache.set(cacheKey, matched);
    return matched;
  } catch {
    return sessionTracesCache.get(cacheKey) || [];
  }
}

/**
 * 清空项目的 Experiment ID 缓存（主要供测试使用）
 */
export function clearProjectExperimentCache(): void {
  projectExperimentCache.clear();
}

/**
 * 异步从 EvalFlow (MLflow) 解析当前项目对应的专属 Experiment ID
 */
export async function fetchProjectExperimentId(
  projectId: string,
  baseUrl?: string,
): Promise<string | null> {
  const pId = (projectId || "").trim();
  if (!pId) return null;
  const cached = projectExperimentCache.get(pId);
  if (cached) return cached;

  const base = (
    baseUrl ||
    env.mlflowBaseUrl ||
    "http://127.0.0.1:9128"
  ).replace(/\/+$/, "");
  try {
    const res = await fetch(
      `${base}/api/2.0/mlflow/experiments/get-by-name?experiment_name=${encodeURIComponent(`project-${pId}`)}`,
      { headers: { Accept: "application/json" } },
    );
    if (res.ok) {
      const data = await res.json();
      const expId = String(data?.experiment?.experiment_id || "").trim();
      if (expId) {
        projectExperimentCache.set(pId, expId);
        return expId;
      }
    }
  } catch {
    // 降级回退
  }
  return null;
}

export interface BuildTraceUrlOptions
  extends BuildLangfuseUrlOptions, BuildMlflowUrlOptions {
  provider?: "langfuse" | "mlflow" | "both" | "none" | string;
}

/**
 * 判断全局链路追踪是否处于激活状态（非 none / disabled / 空）
 */
export function isTracingEnabled(): boolean {
  const p = (env.tracingProvider || "").toLowerCase().trim();
  return p !== "" && p !== "none" && p !== "disabled" && p !== "false";
}

/**
 * 组装 Langfuse Trace 直达 URL
 * 支持三级自适应解析：
 * 1. 显式模板替换 (VITE_LANGFUSE_TRACE_URL_TEMPLATE 或 options.template)；
 * 2. 项目级搜索过滤直达 (VITE_LANGFUSE_PROJECT_ID 或 options.projectId)，精准适配多租户 SaaS，杜绝 404；
 * 3. 兜底默认回退 (base/trace/{traceId})。
 */
export function buildLangfuseTraceUrl(
  traceId: string,
  options: BuildLangfuseUrlOptions = {},
): string {
  const id = traceId.trim();
  if (!id) return "";

  const template = (
    options.template ||
    env.langfuseTraceUrlTemplate ||
    ""
  ).trim();
  if (template) {
    return template.split("{traceId}").join(encodeURIComponent(id));
  }

  const base = (
    options.baseUrl ||
    env.langfuseBaseUrl ||
    "https://jp.cloud.langfuse.com"
  ).replace(/\/+$/, "");
  const projectId = (options.projectId || env.langfuseProjectId || "").trim();

  if (projectId) {
    const params = new URLSearchParams();
    params.set("filter", "isRootObservation;boolean;;=;true");
    params.append("searchType", "id");
    params.append("searchType", "content");
    params.set("traceTab", "attributes");
    params.set("search", id);
    return `${base}/project/${encodeURIComponent(projectId)}/traces?${params.toString()}`;
  }

  return `${base}/trace/${encodeURIComponent(id)}`;
}

/**
 * 组装 MLflow GenAI Traces / Sessions 直达 URL
 * 1. 优先使用 options.template 或 VITE_MLFLOW_TRACE_URL_TEMPLATE；
 * 2. 否则指向 MLflow UI Traces 聚合视图，若携带 threadId 自动按 session_id 分组过滤。
 */
export function buildMlflowTraceUrl(
  traceId: string,
  options: BuildMlflowUrlOptions = {},
): string {
  const id = traceId.trim();
  const threadId = (options.threadId || "").trim();
  if (!id && !threadId) return "";

  const template = (
    options.template ||
    env.mlflowTraceUrlTemplate ||
    ""
  ).trim();
  if (template) {
    return template
      .split("{traceId}")
      .join(encodeURIComponent(id))
      .split("{threadId}")
      .join(encodeURIComponent(threadId))
      .split("{sessionId}")
      .join(encodeURIComponent(threadId));
  }

  const base = (
    options.baseUrl ||
    env.mlflowBaseUrl ||
    "http://127.0.0.1:9128"
  ).replace(/\/+$/, "");
  const experimentId = (
    options.experimentId ||
    (options.projectId
      ? getProjectExperimentId(options.projectId)
      : undefined) ||
    env.mlflowExperimentId ||
    "6"
  ).trim();

  // 若仅指定具体 traceId（或明确要求定位单条 trace），且非搜索模式
  if (id && (!threadId || options.view === "trace")) {
    if (id.startsWith("tr-")) {
      return `${base}/#/experiments/${encodeURIComponent(experimentId)}/traces/${encodeURIComponent(id)}`;
    }
    return `${base}/#/experiments/${encodeURIComponent(experimentId)}/traces?search=${encodeURIComponent(id)}`;
  }

  // 若明确请求 sessions 视角且携带 threadId，直接穿透至 MLflow 单会话全景详情页
  if (threadId && options.view === "sessions") {
    return `${base}/#/experiments/${encodeURIComponent(experimentId)}/chat-sessions/${encodeURIComponent(threadId)}`;
  }

  // 若携带 threadId 但处于 traces 视角，按 session_id 过滤 traces
  if (threadId) {
    const searchExpr = `session_id = '${threadId}'`;
    return `${base}/#/experiments/${encodeURIComponent(experimentId)}/traces?search=${encodeURIComponent(searchExpr)}`;
  }

  if (id) {
    return `${base}/#/experiments/${encodeURIComponent(experimentId)}/traces?search=${encodeURIComponent(id)}`;
  }

  return `${base}/#/experiments/${encodeURIComponent(experimentId)}/traces`;
}

/**
 * 获取 EvalFlow 评测平台大盘首页 URL
 */
export function buildEvalFlowDashboardUrl(baseUrl?: string): string {
  if (!isTracingEnabled()) return "";
  const base = (
    baseUrl ||
    env.mlflowBaseUrl ||
    "http://127.0.0.1:9128"
  ).replace(/\/+$/, "");
  return base;
}

/**
 * 统一根据 provider 动态分发 Trace 直达 URL
 */
export function buildTraceUrl(
  traceId: string,
  options: BuildTraceUrlOptions = {},
): string {
  if (!isTracingEnabled()) return "";
  const provider = (
    options.provider ||
    env.tracingProvider ||
    "mlflow"
  ).toLowerCase();
  if (provider === "none") return "";
  if (provider === "mlflow") {
    return buildMlflowTraceUrl(traceId, options);
  }
  return buildLangfuseTraceUrl(traceId, options);
}

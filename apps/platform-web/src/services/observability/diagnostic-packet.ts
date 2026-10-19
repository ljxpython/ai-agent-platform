/**
 * 排障诊断数据包 (Diagnostic Packet) 生成与复制工具
 * 用于一键聚合环境、路由、业务上下文、最近失败请求与前端堆栈，生成脱敏排障报告。
 * 内置安全上下文与非安全上下文 (纯 HTTP) 双模剪贴板复制兜底。
 */

import { errorRingBuffer, type DiagnosticErrorRecord } from "./error-buffer";

export interface DiagnosticContext {
  projectId?: string;
  threadId?: string;
  runId?: string;
  userEmail?: string;
  error?: unknown;
  customMessage?: string;
  requestId?: string;
  routePath?: string;
  traceId?: string;
  traceUrl?: string;
  backendDiagnostics?: Record<string, unknown> | null;
}

const SENSITIVE_PATTERNS = [
  /bearer\s+[a-zA-Z0-9_\-.]+/gi,
  /(access_token|refresh_token|api_key|secret|password)=([^&\s]+)/gi,
  /"(access_token|refresh_token|api_key|secret|password)"\s*:\s*"[^"]+"/gi,
];

/**
 * 结构化原因机器码的人话映射字典 (借鉴 open-swe 去业务化设计)
 */
export const REASON_CODE_TEXT: Record<string, string> = {
  provider_overloaded: "大模型上游服务商负载过高，暂未恢复响应",
  provider_rate_limited: "触发大模型服务商调用频率限制 (Rate Limit)",
  provider_unavailable: "大模型服务商持续返回服务不可用或内部错误 (5xx)",
  provider_timeout: "大模型调用超时或网络握手超时",
  context_too_long: "对话上下文长度超出大模型窗口上限",
  model_unavailable: "当前工作区未配置或不支持所选模型",
  sandbox_unreachable: "沙箱运行环境失联或已被销毁",
  step_limit: "单次任务执行达到最大步数限制 (GraphRecursionError)",
  "runtime.execution_failed": "智能体执行中断或发生不可恢复异常",
  "runtime.loop.detected": "检测到工具调用或模型输出进入死循环",
  context_offload_not_supported: "当前智能体未开启或不支持上下文手动整理",
  context_offload_empty_thread: "当前会话尚无历史消息，无需整理",
  context_offload_pending_input: "当前存在排队或待发送消息，请完成后再试",
  context_offload_interrupt_pending: "当前会话存在等待审批的动作，请先处理",
  thread_active_run_conflict: "当前会话正在执行中，请等待其结束",
};

/**
 * 结构化恢复操作指引字典 (Actionable Follow-up)
 */
export const REASON_CODE_FOLLOW_UP: Record<string, string> = {
  context_too_long: "建议点击左侧新建会话，开启新对话以重置上下文长度。",
  provider_rate_limited:
    "模型调用配额超限，请等待 1~2 分钟后再试，或在输入框切换其他可用模型。",
  provider_overloaded: "服务商服务器繁忙，请稍等片刻后发送新消息继续。",
  provider_unavailable: "上游接口故障，请核对模型接入配置或稍后重试。",
  provider_timeout: "响应超时，请重试发送消息或减小单次提示词复杂度。",
  model_unavailable: "请前往设置检查模型凭据是否有效，或选择其他可用模型。",
  sandbox_unreachable: "建议刷新页面并重新发起运行以自动重建沙箱。",
  step_limit: "任务复杂度过高，建议将大任务拆分为小步骤分别指派给智能体。",
  "runtime.loop.detected":
    "已触发安全保护终止循环，请调整 Prompt 明确停止条件后重试。",
  "runtime.execution_failed":
    "可点击【查看排障详情】或【复制排障信息】交由运维/开发定位。",
  context_offload_not_supported:
    "请联系管理员在服务配置中开启 AGENT_CONTEXT_MANAGEMENT_ENABLED=1 支持。",
  context_offload_empty_thread:
    "可在与智能体进行多轮对话产生历史消息后，再尝试整理上下文。",
  context_offload_pending_input:
    "请等待排队消息发送完成，或清空待发送队列后重试。",
  context_offload_interrupt_pending:
    "请先审批或处理当前挂起的工具调用与输入确认。",
  thread_active_run_conflict: "请等待当前运行结束或手动停止运行后再试。",
};

/**
 * 解析错误原因码、人话解释与可操作建议
 */
export function resolveReasonDetails(
  code?: string,
  rawMessage?: string,
): {
  reasonCode: string;
  reasonText: string;
  followUp: string;
} {
  const normCode = (code || "").trim();
  const haystack = `${normCode} ${rawMessage || ""}`.toLowerCase();

  let matchedCode = normCode;
  if (
    !normCode ||
    normCode === "runtime.execution_failed" ||
    normCode === "N/A"
  ) {
    if (haystack.includes("rate_limit") || haystack.includes("429")) {
      matchedCode = "provider_rate_limited";
    } else if (haystack.includes("overloaded") || haystack.includes("529")) {
      matchedCode = "provider_overloaded";
    } else if (
      haystack.includes("context_length_exceeded") ||
      haystack.includes("prompt is too long") ||
      haystack.includes("context_too_long")
    ) {
      matchedCode = "context_too_long";
    } else if (
      haystack.includes("model_not_found") ||
      haystack.includes("model_unavailable")
    ) {
      matchedCode = "model_unavailable";
    } else if (haystack.includes("timeout") || haystack.includes("timed out")) {
      matchedCode = "provider_timeout";
    } else if (
      haystack.includes("recursion") ||
      haystack.includes("step_limit")
    ) {
      matchedCode = "step_limit";
    } else if (
      haystack.includes("sandbox") &&
      (haystack.includes("unreachable") ||
        haystack.includes("lost") ||
        haystack.includes("failed"))
    ) {
      matchedCode = "sandbox_unreachable";
    } else if (haystack.includes("loop")) {
      matchedCode = "runtime.loop.detected";
    } else if (normCode) {
      matchedCode = normCode;
    } else {
      matchedCode = "runtime.execution_failed";
    }
  }

  const reasonText =
    REASON_CODE_TEXT[matchedCode] ||
    (rawMessage ? `执行异常: ${rawMessage}` : "智能体执行未完成，请重试。");
  const followUp =
    REASON_CODE_FOLLOW_UP[matchedCode] ||
    REASON_CODE_FOLLOW_UP["runtime.execution_failed"];

  return {
    reasonCode: matchedCode,
    reasonText,
    followUp,
  };
}

/**
 * 脱敏处理字符串，掩盖敏感 token、密码等
 */
export function sanitizeDiagnosticText(text: string): string {
  if (!text) return "";
  let sanitized = text;
  for (const pattern of SENSITIVE_PATTERNS) {
    sanitized = sanitized.replace(pattern, (match) => {
      if (match.toLowerCase().startsWith("bearer ")) {
        return "Bearer [REDACTED]";
      }
      return match.replace(/(=|:\s*")[^"&]+/i, "$1[REDACTED]");
    });
  }
  return sanitized;
}

/**
 * 组装结构化排障诊断报告 (Markdown 格式)
 */
export function generateDiagnosticMarkdown(
  context: DiagnosticContext = {},
): string {
  const now = new Date().toISOString();
  const href = typeof window !== "undefined" ? window.location.href : "N/A";
  const path =
    context.routePath ||
    (typeof window !== "undefined" ? window.location.pathname : "N/A");
  const ua =
    typeof navigator !== "undefined" ? navigator.userAgent : "Node/Unknown";
  const isSecure =
    typeof window !== "undefined" ? Boolean(window.isSecureContext) : false;

  // 1. 查找关联的最新错误或特定 request_id 错误
  let relatedRecord: DiagnosticErrorRecord | null = null;
  if (context.requestId) {
    relatedRecord = errorRingBuffer.getLatestByRequestId(context.requestId);
  }
  if (!relatedRecord) {
    relatedRecord = errorRingBuffer.getLatest();
  }

  // 2. 解析传入的直接错误
  let directErrorMsg = context.customMessage || "";
  let directErrorStack = "";
  if (context.error) {
    if (context.error instanceof Error) {
      directErrorMsg = directErrorMsg
        ? `${directErrorMsg} (${context.error.message})`
        : context.error.message;
      directErrorStack = context.error.stack || "";
    } else if (typeof context.error === "object") {
      directErrorMsg = directErrorMsg || JSON.stringify(context.error);
    } else {
      directErrorMsg = directErrorMsg || String(context.error);
    }
  }

  // 3. 最近失败请求摘要
  const recentErrors = errorRingBuffer.getAll().slice(0, 3);
  const recentErrorsSection =
    recentErrors.length > 0
      ? recentErrors
          .map((e, idx) => {
            const req = e.requestId ? ` (Request ID: \`${e.requestId}\`)` : "";
            const status = e.status ? `[${e.status}] ` : "";
            const code = e.code ? `[Code: ${e.code}] ` : "";
            return `  ${idx + 1}. ${e.timestamp} | ${e.type.toUpperCase()} ${status}${code}${e.url || ""}${req}\n     原因: ${sanitizeDiagnosticText(e.message)}`;
          })
          .join("\n")
      : "  无记录";

  const backendDiag = context.backendDiagnostics as
    | Record<string, unknown>
    | undefined;
  const correlation = backendDiag?.correlation as
    | Record<string, unknown>
    | undefined;
  const traceObj = backendDiag?.trace as Record<string, unknown> | undefined;

  const traceId =
    context.traceId || (traceObj?.trace_id as string) || undefined;
  const traceUrl = context.traceUrl;
  const executionRequestId =
    (correlation?.execution_request_id as string) ||
    (correlation?.platform_trace_id as string) ||
    (backendDiag?.request_id as string) ||
    undefined;

  const resolvedRequestId =
    context.requestId ||
    executionRequestId ||
    relatedRecord?.requestId ||
    "未关联";

  let rawErrMsg = directErrorMsg || relatedRecord?.message || "";
  let rawCode = relatedRecord?.code || "";

  // 兜底：若前端内存无错误，但后端诊断有 model_errors 或 graph_executions，提取之
  const modelErrors = Array.isArray(backendDiag?.model_errors)
    ? (backendDiag?.model_errors as Array<Record<string, unknown>>)
    : [];
  const graphExecutions = Array.isArray(backendDiag?.graph_executions)
    ? (backendDiag?.graph_executions as Array<Record<string, unknown>>)
    : [];

  if (!rawErrMsg && modelErrors.length > 0) {
    const firstErr = modelErrors[0];
    rawCode = rawCode || String(firstErr.code || "");
    rawErrMsg = `[Model Error] Code: ${firstErr.code}, Scope: ${firstErr.scope || "primary"}${firstErr.provider_status ? `, HTTP: ${firstErr.provider_status}` : ""}`;
  } else if (
    !rawErrMsg &&
    graphExecutions.some((g) => g.outcome !== "success")
  ) {
    const failedGraph = graphExecutions.find((g) => g.outcome !== "success");
    rawCode =
      rawCode || String(failedGraph?.error_code || "runtime.execution_failed");
    rawErrMsg = `[Graph Execution Failed] Outcome: ${failedGraph?.outcome}, Code: ${failedGraph?.error_code || "N/A"}`;
  }

  const reasonDetails = resolveReasonDetails(rawCode, rawErrMsg);

  const tracingSection = `- **分布式链路追踪 (Distributed Tracing / Open Trace)**:
  - Trace Provider: Langfuse
  - Trace ID: \`${traceId || "未分配或暂无"}\`
${traceUrl ? `  - Trace 直达链接: [在 Langfuse 中打开追踪 (Open Trace ↗)](${sanitizeDiagnosticText(traceUrl)})\n` : ""}${executionRequestId ? `  - Execution Request ID: \`${executionRequestId}\`\n` : ""}`;

  const report = `### 🛠️ 故障诊断数据包 (Diagnostic Packet)
- **发生时间**: ${now}
- **访问路径**: \`${path}\`
- **完整链接**: ${sanitizeDiagnosticText(href)}
- **客户端环境**:
  - 安全上下文: ${isSecure ? "是 (HTTPS/Localhost)" : "否 (纯 HTTP 裸访问)"}
  - User Agent: \`${ua}\`
- **业务上下文**:
  - Project ID: \`${context.projectId || "未提供"}\`
  - Thread ID: \`${context.threadId || "未提供"}\`
  - Run ID: \`${context.runId || "未提供"}\`
  - 关联 Request ID: \`${resolvedRequestId}\`
${tracingSection}- **错误概况**:
  - 原始错误: ${sanitizeDiagnosticText(rawErrMsg || "未捕获明确错误信息")}
  - 机器代码: \`${reasonDetails.reasonCode}\`
- **根因分析与恢复建议**:
  - 根因分析: ${reasonDetails.reasonText}
  - 操作建议: ${reasonDetails.followUp}
${
  directErrorStack
    ? `- **前端调用栈**:\n\`\`\`\n${sanitizeDiagnosticText(directErrorStack.trim())}\n\`\`\`\n`
    : ""
}- **最近异常记录 (最近 3 条)**:
${recentErrorsSection}
`;

  return report;
}

/**
 * 复制文本到剪贴板，支持原生 clipboard 与 execCommand 双模降级
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  if (!text) return false;

  // 1. 尝试现代 Clipboard API (仅在安全上下文可用)
  if (
    typeof navigator !== "undefined" &&
    navigator.clipboard &&
    typeof navigator.clipboard.writeText === "function"
  ) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // 降级到 document.execCommand
    }
  }

  // 2. 降级方案: document.execCommand('copy')
  if (typeof document !== "undefined") {
    try {
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.style.position = "fixed";
      textarea.style.left = "-9999px";
      textarea.style.top = "-9999px";
      textarea.setAttribute("readonly", "true");
      document.body.appendChild(textarea);
      textarea.select();
      textarea.setSelectionRange(0, textarea.value.length);
      const successful = document.execCommand("copy");
      document.body.removeChild(textarea);
      return successful;
    } catch {
      return false;
    }
  }

  return false;
}

/**
 * 一键组装并复制排障诊断包
 */
export async function copyDiagnosticPacket(
  context: DiagnosticContext = {},
): Promise<{ success: boolean; markdown: string }> {
  const markdown = generateDiagnosticMarkdown(context);
  const success = await copyToClipboard(markdown);
  return { success, markdown };
}

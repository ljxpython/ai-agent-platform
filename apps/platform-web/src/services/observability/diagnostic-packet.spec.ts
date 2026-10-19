import { describe, it, expect, beforeEach, vi } from "vitest";
import {
  sanitizeDiagnosticText,
  generateDiagnosticMarkdown,
  copyToClipboard,
  copyDiagnosticPacket,
  resolveReasonDetails,
} from "./diagnostic-packet";
import { errorRingBuffer } from "./error-buffer";

describe("diagnostic-packet", () => {
  beforeEach(() => {
    errorRingBuffer.clear();
    vi.restoreAllMocks();
  });

  describe("sanitizeDiagnosticText", () => {
    it("应当脱敏 Bearer 令牌与敏感 query/json 字段", () => {
      const text =
        'Authorization: Bearer eyJhbGciOi... and url?access_token=secret123&password=my-pass and {"secret":"topsecret"}';
      const sanitized = sanitizeDiagnosticText(text);

      expect(sanitized).not.toContain("eyJhbGciOi...");
      expect(sanitized).toContain("Bearer [REDACTED]");
      expect(sanitized).toContain("access_token=[REDACTED]");
      expect(sanitized).toContain("password=[REDACTED]");
      expect(sanitized).toContain('"secret":"[REDACTED]"');
    });

    it("空字符串应当安全返回空", () => {
      expect(sanitizeDiagnosticText("")).toBe("");
    });
  });

  describe("generateDiagnosticMarkdown", () => {
    it("应当正确组装包含业务上下文与关联 request_id 的 Markdown", () => {
      errorRingBuffer.push({
        type: "http",
        status: 502,
        code: "runtime_execution_failed",
        requestId: "req-abc-123",
        url: "/api/runs",
        message: "Docker execution timeout",
      });

      const md = generateDiagnosticMarkdown({
        projectId: "proj-1",
        threadId: "thread-2",
        runId: "run-3",
        requestId: "req-abc-123",
        error: new Error("UI Render Crash"),
      });

      expect(md).toContain("### 🛠️ 故障诊断数据包");
      expect(md).toContain("Project ID: `proj-1`");
      expect(md).toContain("Thread ID: `thread-2`");
      expect(md).toContain("Run ID: `run-3`");
      expect(md).toContain("关联 Request ID: `req-abc-123`");
      expect(md).toContain("UI Render Crash");
      expect(md).toContain("HTTP [502] [Code: runtime_execution_failed]");
      expect(md).toContain("Docker execution timeout");
    });

    it("应当正确在 Markdown 中渲染分布式链路追踪信息与后端诊断快照", () => {
      const md = generateDiagnosticMarkdown({
        projectId: "proj-101",
        threadId: "thread-202",
        runId: "run-303",
        traceId: "langfuse-trace-777",
        traceUrl: "https://jp.cloud.langfuse.com/trace/langfuse-trace-777",
        backendDiagnostics: {
          correlation: {
            execution_request_id: "backend-exec-888",
          },
          model_errors: [
            {
              code: "context_too_long",
              scope: "primary",
              provider_status: 400,
            },
          ],
        },
      });

      expect(md).toContain("分布式链路追踪 (Distributed Tracing / Open Trace)");
      expect(md).toContain("Trace ID: `langfuse-trace-777`");
      expect(md).toContain("在 Langfuse 中打开追踪 (Open Trace ↗)");
      expect(md).toContain("Execution Request ID: `backend-exec-888`");
      expect(md).toContain("context_too_long");
    });
  });

  describe("copyToClipboard", () => {
    it("当现代 clipboard 存在时应当优先调用 writeText", async () => {
      const writeTextMock = vi.fn().mockResolvedValue(undefined);
      Object.assign(navigator, {
        clipboard: {
          writeText: writeTextMock,
        },
      });

      const res = await copyToClipboard("test content");
      expect(res).toBe(true);
      expect(writeTextMock).toHaveBeenCalledWith("test content");
    });

    it("当 clipboard 抛异常时应当降级到 document.execCommand", async () => {
      Object.assign(navigator, {
        clipboard: {
          writeText: vi.fn().mockRejectedValue(new Error("Permission denied")),
        },
      });

      const execCommandMock = vi.fn().mockReturnValue(true);
      document.execCommand = execCommandMock;

      const res = await copyToClipboard("fallback content");
      expect(res).toBe(true);
      expect(execCommandMock).toHaveBeenCalledWith("copy");
    });
  });

  describe("copyDiagnosticPacket", () => {
    it("应当生成并触发复制", async () => {
      Object.assign(navigator, {
        clipboard: {
          writeText: vi.fn().mockResolvedValue(undefined),
        },
      });

      const result = await copyDiagnosticPacket({
        customMessage: "Custom test error",
      });

      expect(result.success).toBe(true);
      expect(result.markdown).toContain("Custom test error");
    });
  });

  describe("resolveReasonDetails (借鉴 open-swe 规则)", () => {
    it("应当准确解析常见机器码并附带 Actionable 恢复建议", () => {
      const res1 = resolveReasonDetails("context_too_long");
      expect(res1.reasonCode).toBe("context_too_long");
      expect(res1.reasonText).toContain("窗口上限");
      expect(res1.followUp).toContain("开启新对话");

      const res2 = resolveReasonDetails("provider_timeout");
      expect(res2.reasonCode).toBe("provider_timeout");
      expect(res2.reasonText).toContain("超时");

      const res3 = resolveReasonDetails("step_limit");
      expect(res3.reasonCode).toBe("step_limit");
      expect(res3.reasonText).toContain("最大步数限制");
      expect(res3.followUp).toContain("拆分为小步骤");
    });

    it("当遇到通用错误但包含关键词时，应当智能推导具体机器码", () => {
      const inferred1 = resolveReasonDetails(
        "runtime.execution_failed",
        "Rate limit exceeded (429) from provider",
      );
      expect(inferred1.reasonCode).toBe("provider_rate_limited");
      expect(inferred1.followUp).toContain("配额超限");

      const inferred2 = resolveReasonDetails(
        "",
        "GraphRecursionError: recursion limit of 25 reached",
      );
      expect(inferred2.reasonCode).toBe("step_limit");

      const inferred3 = resolveReasonDetails(
        "",
        "Sandbox connection lost or unreachable",
      );
      expect(inferred3.reasonCode).toBe("sandbox_unreachable");
    });
  });
});

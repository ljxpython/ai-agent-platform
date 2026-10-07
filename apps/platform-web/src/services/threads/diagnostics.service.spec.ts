import { beforeEach, describe, expect, it, vi } from "vitest";
import { getRunDiagnostics } from "./diagnostics.service";
import { platformHttpClient } from "@/services/http/client";

vi.mock("@/services/http/client", () => ({
  platformHttpClient: {
    get: vi.fn(),
  },
}));

describe("diagnostics.service", () => {
  const threadId = "thread-1111-2222";
  const runId = "run-3333-4444";
  const projectId = "project-5555";

  const validResponsePayload = {
    version: 1,
    thread_id: threadId,
    run_id: runId,
    run_status: "success",
    request_id: "req-1",
    availability: "available",
    unavailable_reason: null,
    correlation: {
      execution_request_id: "exec-1",
      platform_trace_id: "trace-1",
    },
    trace: {
      provider: "langfuse",
      trace_id: "trace-id-1",
      url: null,
    },
    graph_executions: [],
    model_errors: [],
    startup: null,
    truncated: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("成功发起 GET 请求并返回安全解析后的 DTO", async () => {
    vi.mocked(platformHttpClient.get).mockResolvedValueOnce({
      data: validResponsePayload,
      status: 200,
    });

    const data = await getRunDiagnostics(threadId, runId, { projectId });

    expect(platformHttpClient.get).toHaveBeenCalledWith(
      `/api/langgraph/threads/${encodeURIComponent(threadId)}/runs/${encodeURIComponent(runId)}/diagnostics`,
      {
        headers: { "x-project-id": projectId },
        signal: undefined,
      },
    );
    expect(data.run_id).toBe(runId);
    expect(data.availability).toBe("available");
  });

  it("当返回数据与请求的目标 threadId 或 runId 不匹配时报错", async () => {
    vi.mocked(platformHttpClient.get).mockResolvedValueOnce({
      data: {
        ...validResponsePayload,
        run_id: "different-run-id",
      },
      status: 200,
    });

    await expect(getRunDiagnostics(threadId, runId)).rejects.toThrow(
      "诊断响应编号与当前目标不匹配",
    );
  });

  it("空参数拦截", async () => {
    await expect(getRunDiagnostics("", runId)).rejects.toThrow("不能为空");
    await expect(getRunDiagnostics(threadId, "")).rejects.toThrow("不能为空");
  });

  it("当返回格式不合法时报错", async () => {
    vi.mocked(platformHttpClient.get).mockResolvedValueOnce({
      data: { invalid_key: "no_version" },
      status: 200,
    });

    await expect(getRunDiagnostics(threadId, runId)).rejects.toThrow(
      "诊断格式校验失败",
    );
  });

  it("正确提取 HTTP 403 权限错误", async () => {
    const errorResponse = {
      response: {
        status: 403,
        data: {
          code: "project_access_denied",
          message: "无权访问此项目",
        },
      },
    };
    vi.mocked(platformHttpClient.get).mockRejectedValueOnce(errorResponse);

    await expect(getRunDiagnostics(threadId, runId)).rejects.toMatchObject({
      status: 403,
      code: "project_access_denied",
    });
  });
});

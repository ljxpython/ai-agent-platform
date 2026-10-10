import { beforeEach, describe, expect, it, vi } from "vitest";
import { getRunCompletion } from "./completion.service";
import { platformHttpClient } from "@/services/http/client";

vi.mock("@/services/http/client", () => ({
  platformHttpClient: {
    get: vi.fn(),
  },
}));

describe("completion.service", () => {
  const threadId = "5752312c-5893-4ba9-914e-d4b7748f42b8";
  const runId = "cf4d5956-c579-459d-a106-1c3fb05a639a";
  const projectId = "project-5555";

  const validAvailableResponse = {
    version: 1,
    thread_id: threadId,
    run_id: runId,
    availability: "available",
    completion: {
      event_id: "354bd564-c2b7-4d38-b538-f53f53a8d37a",
      graph_id: "reference_agent",
      status: "success",
      reason: "completed",
      reason_code: null,
      model_error_code: null,
      notification_code: null,
      occurred_at: "2026-10-09T04:52:44.707165Z",
      can_mark_read: false,
      read_at: null,
    },
    request_id: "req-comp-1",
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("成功发起 GET 请求并返回安全解析的 completion", async () => {
    vi.mocked(platformHttpClient.get).mockResolvedValueOnce({
      data: validAvailableResponse,
      status: 200,
    });

    const data = await getRunCompletion(threadId, runId, { projectId });

    expect(platformHttpClient.get).toHaveBeenCalledWith(
      `/api/langgraph/threads/${encodeURIComponent(threadId)}/runs/${encodeURIComponent(runId)}/completion`,
      {
        headers: { "x-project-id": projectId },
        signal: undefined,
      },
    );
    expect(data.availability).toBe("available");
    if (data.availability === "available") {
      expect(data.completion.status).toBe("success");
    }
  });

  it("当返回数据与请求的目标 threadId 或 runId 不匹配时报错", async () => {
    vi.mocked(platformHttpClient.get).mockResolvedValueOnce({
      data: {
        ...validAvailableResponse,
        run_id: "11111111-2222-3333-4444-555555555555",
      },
      status: 200,
    });

    await expect(getRunCompletion(threadId, runId)).rejects.toThrow(
      "终态摘要响应目标与请求不匹配",
    );
  });

  it("空参数拦截", async () => {
    await expect(getRunCompletion("", runId)).rejects.toThrow("不能为空");
    await expect(getRunCompletion(threadId, "")).rejects.toThrow("不能为空");
  });

  it("返回非法格式时抛出 invalid_completion_dto", async () => {
    vi.mocked(platformHttpClient.get).mockResolvedValueOnce({
      data: { unknown_foo: "bar" },
      status: 200,
    });

    await expect(getRunCompletion(threadId, runId)).rejects.toThrow(
      "终态摘要格式校验失败",
    );
  });
});

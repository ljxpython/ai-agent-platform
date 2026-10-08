import { describe, it, expect, vi, beforeEach } from "vitest";
import { getRunUsage, getThreadUsage } from "./usage.service";
import { platformHttpClient } from "@/services/http/client";
import usageFixtures from "../../../../../docs/projects/20261007-agent-usage-cost-governance/fixtures/usage-v1.json";

vi.mock("@/services/http/client", () => ({
  platformHttpClient: {
    get: vi.fn(),
  },
}));

describe("usage.service", () => {
  const runSample = (usageFixtures as any).samples.run_complete_page1;
  const threadSample = (usageFixtures as any).samples.thread_complete;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("getRunUsage", () => {
    it("正常返回解析后的 Run 用量，并传递正确 headers 与 params", async () => {
      vi.mocked(platformHttpClient.get).mockResolvedValueOnce({
        data: runSample,
      });

      const res = await getRunUsage(runSample.thread_id, runSample.run_id, {
        projectId: "proj-123",
        limit: 100,
        cursor: "cur-abc",
      });

      expect(res.run_id).toBe(runSample.run_id);
      expect(platformHttpClient.get).toHaveBeenCalledWith(
        `/api/langgraph/threads/${runSample.thread_id}/runs/${runSample.run_id}/usage`,
        expect.objectContaining({
          headers: { "x-project-id": "proj-123" },
          params: { limit: 100, cursor: "cur-abc" },
        }),
      );
    });

    it("空 threadId 或 runId 时直接抛错", async () => {
      await expect(getRunUsage("", "run-1")).rejects.toThrow("不能为空");
      await expect(getRunUsage("th-1", "")).rejects.toThrow("不能为空");
    });

    it("响应中的 thread_id 或 run_id 不匹配请求目标时抛错", async () => {
      vi.mocked(platformHttpClient.get).mockResolvedValueOnce({
        data: {
          ...runSample,
          run_id: "different-run-id",
        },
      });

      await expect(
        getRunUsage(runSample.thread_id, runSample.run_id),
      ).rejects.toMatchObject({
        code: "mismatched_usage_target",
      });
    });

    it("响应数据格式损坏时抛出 invalid_usage_dto", async () => {
      vi.mocked(platformHttpClient.get).mockResolvedValueOnce({
        data: { broken: true },
      });

      await expect(
        getRunUsage(runSample.thread_id, runSample.run_id),
      ).rejects.toMatchObject({
        code: "invalid_usage_dto",
      });
    });
  });

  describe("getThreadUsage", () => {
    it("正常返回 Thread 用量，且默认不带任何 created_from/created_to query", async () => {
      vi.mocked(platformHttpClient.get).mockResolvedValueOnce({
        data: threadSample,
      });

      const res = await getThreadUsage(threadSample.thread_id, {
        projectId: "proj-456",
      });

      expect(res.thread_id).toBe(threadSample.thread_id);
      expect(platformHttpClient.get).toHaveBeenCalledWith(
        `/api/langgraph/threads/${threadSample.thread_id}/usage`,
        expect.objectContaining({
          headers: { "x-project-id": "proj-456" },
          params: {},
        }),
      );
    });

    it("仅当 createdFrom 和 createdTo 同时有效时才拼接 params", async () => {
      vi.mocked(platformHttpClient.get).mockResolvedValueOnce({
        data: threadSample,
      });

      // 仅传 createdFrom，没传 createdTo -> 不应携带 params
      await getThreadUsage(threadSample.thread_id, {
        createdFrom: "2026-10-01T00:00:00Z",
        createdTo: "   ",
      });

      expect(platformHttpClient.get).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          params: {},
        }),
      );

      vi.mocked(platformHttpClient.get).mockResolvedValueOnce({
        data: threadSample,
      });

      // 双边都有效
      await getThreadUsage(threadSample.thread_id, {
        createdFrom: "2026-10-01T00:00:00Z",
        createdTo: "2026-10-07T00:00:00Z",
      });

      expect(platformHttpClient.get).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          params: {
            created_from: "2026-10-01T00:00:00Z",
            created_to: "2026-10-07T00:00:00Z",
          },
        }),
      );
    });

    it("响应 thread_id 错位时抛错", async () => {
      vi.mocked(platformHttpClient.get).mockResolvedValueOnce({
        data: {
          ...threadSample,
          thread_id: "other-th",
        },
      });

      await expect(
        getThreadUsage(threadSample.thread_id),
      ).rejects.toMatchObject({
        code: "mismatched_thread_usage_target",
      });
    });
  });
});

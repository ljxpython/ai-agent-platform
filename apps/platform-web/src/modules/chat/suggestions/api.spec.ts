import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  loadSuggestionsConfig,
  generateThreadSuggestions,
  _resetSuggestionsConfigCache,
} from "./api";
import { platformHttpClient } from "@/services/http/client";

vi.mock("@/services/http/client", () => ({
  platformHttpClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

describe("suggestions/api", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    _resetSuggestionsConfigCache();
  });

  describe("loadSuggestionsConfig", () => {
    it("正确携带 x-project-id 头调用配置接口并缓存结果", async () => {
      const mockConfig = { enabled: true, max_suggestions: 3 };
      vi.mocked(platformHttpClient.get).mockResolvedValueOnce({
        data: mockConfig,
      } as any);

      const res1 = await loadSuggestionsConfig("project-1");
      expect(platformHttpClient.get).toHaveBeenCalledTimes(1);
      expect(platformHttpClient.get).toHaveBeenCalledWith(
        "/api/langgraph/suggestions/config",
        expect.objectContaining({
          headers: { "x-project-id": "project-1" },
        }),
      );
      expect(res1).toEqual(mockConfig);

      // 第二次调用命中单例缓存，不发网络请求
      const res2 = await loadSuggestionsConfig("project-1");
      expect(platformHttpClient.get).toHaveBeenCalledTimes(1);
      expect(res2).toEqual(mockConfig);
    });

    it("接口异常时安全降级为 enabled: false", async () => {
      vi.mocked(platformHttpClient.get).mockRejectedValueOnce(
        new Error("Network Error"),
      );

      const res = await loadSuggestionsConfig("project-err");
      expect(res).toEqual({ enabled: false, max_suggestions: 3 });
    });
  });

  describe("generateThreadSuggestions", () => {
    it("正确携带 x-project-id、payload 和 signal 调用生成接口", async () => {
      const mockResult = {
        suggestions: [" 推荐问题 1 ", "推荐问题 2", ""],
      };
      vi.mocked(platformHttpClient.post).mockResolvedValueOnce({
        data: mockResult,
      } as any);

      const controller = new AbortController();
      const payload = {
        messages: [{ role: "user" as const, content: "你好" }],
        n: 3,
      };

      const res = await generateThreadSuggestions(
        "project-1",
        "thread-123",
        payload,
        controller.signal,
      );

      expect(platformHttpClient.post).toHaveBeenCalledWith(
        "/api/langgraph/threads/thread-123/suggestions",
        payload,
        expect.objectContaining({
          headers: { "x-project-id": "project-1" },
          signal: controller.signal,
        }),
      );
      // 空白项被过滤，字符串被 trim
      expect(res).toEqual(["推荐问题 1", "推荐问题 2"]);
    });

    it("服务端报错或 5xx 时静默降级返回空数组", async () => {
      vi.mocked(platformHttpClient.post).mockRejectedValueOnce(
        new Error("Internal Server Error"),
      );

      const res = await generateThreadSuggestions("project-1", "thread-123", {
        messages: [{ role: "user", content: "test" }],
      });
      expect(res).toEqual([]);
    });
  });
});

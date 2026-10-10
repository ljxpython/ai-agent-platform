import { describe, it, expect, vi, beforeEach } from "vitest";
import { ref, nextTick } from "vue";
import { useAutomaticThreadTitle } from "./useAutomaticThreadTitle";
import * as sessionServiceModule from "@/services/threads/session.service";

vi.mock("@/services/langgraph/client", () => ({
  createLanggraphAuthorizedFetch: vi.fn(() => vi.fn()),
}));

describe("useAutomaticThreadTitle", () => {
  const mockSummarizeTitle = vi.fn();
  const mockGet = vi.fn();
  const mockCreateSessionService = vi.fn(() => ({
    summarizeTitle: mockSummarizeTitle,
    get: mockGet,
  }));

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(sessionServiceModule, "createSessionService").mockImplementation(
      mockCreateSessionService as unknown as typeof sessionServiceModule.createSessionService,
    );
  });

  it("当满足四项黄金门禁时，触发自动提炼并成功更新标题", async () => {
    mockSummarizeTitle.mockResolvedValueOnce({
      thread_id: "thread-1",
      title: "新生成的简洁标题",
      outcome: "applied",
      reason: null,
    });

    const runStatus = ref("running");
    const runId = ref("run-1");
    const accessThread = ref<any>({
      thread_id: "thread-1",
      metadata: { auto_title_pending: true },
    });
    const messages = ref<any[]>([
      { type: "human", content: "请帮我写个脚本" },
      { id: "ai-1", type: "ai", content: "这是脚本内容代码" },
    ]);
    const onTitleUpdated = vi.fn();

    useAutomaticThreadTitle({
      projectId: "proj-1",
      threadId: "thread-1",
      runStatus,
      runId,
      accessThread,
      messages,
      onTitleUpdated,
    });

    expect(mockSummarizeTitle).not.toHaveBeenCalled();

    // 运行完成变为 success
    runStatus.value = "success";
    await nextTick();

    await vi.waitFor(() => {
      expect(mockSummarizeTitle).toHaveBeenCalledWith(
        "thread-1",
        { mode: "auto", run_id: "run-1" },
        expect.any(AbortSignal),
      );
      expect(onTitleUpdated).toHaveBeenCalledWith("新生成的简洁标题");
    });
  });

  it("当 auto_title_pending 为 false 时，阻断触发", async () => {
    const runStatus = ref("success");
    const runId = ref("run-1");
    const accessThread = ref<any>({
      thread_id: "thread-1",
      metadata: { auto_title_pending: false },
    });
    const messages = ref<any[]>([
      { type: "human", content: "你好" },
      { id: "ai-1", type: "ai", content: "你好呀！" },
    ]);
    const onTitleUpdated = vi.fn();

    useAutomaticThreadTitle({
      projectId: "proj-1",
      threadId: "thread-1",
      runStatus,
      runId,
      accessThread,
      messages,
      onTitleUpdated,
    });

    await nextTick();
    expect(mockSummarizeTitle).not.toHaveBeenCalled();
    expect(onTitleUpdated).not.toHaveBeenCalled();
  });

  it("当最后一条消息包含 tool_calls 时，视为工具中间态，阻断触发", async () => {
    const runStatus = ref("success");
    const runId = ref("run-1");
    const accessThread = ref<any>({
      thread_id: "thread-1",
      metadata: { auto_title_pending: true },
    });
    const messages = ref<any[]>([
      { type: "human", content: "查天气" },
      {
        id: "ai-1",
        type: "ai",
        content: "正在查询...",
        tool_calls: [{ name: "search", args: {} }],
      },
    ]);
    const onTitleUpdated = vi.fn();

    useAutomaticThreadTitle({
      projectId: "proj-1",
      threadId: "thread-1",
      runStatus,
      runId,
      accessThread,
      messages,
      onTitleUpdated,
    });

    await nextTick();
    expect(mockSummarizeTitle).not.toHaveBeenCalled();
    expect(onTitleUpdated).not.toHaveBeenCalled();
  });

  it("当后端返回 skipped/conflict 时，应用返回的当前标题", async () => {
    mockSummarizeTitle.mockResolvedValueOnce({
      thread_id: "thread-1",
      title: "用户之前修改的自定义标题",
      outcome: "skipped",
      reason: "conflict",
    });

    const runStatus = ref("success");
    const runId = ref("run-1");
    const accessThread = ref<any>({
      thread_id: "thread-1",
      metadata: { auto_title_pending: true },
    });
    const messages = ref<any[]>([
      { type: "human", content: "查天气" },
      { id: "ai-1", type: "ai", content: "今天天气晴朗" },
    ]);
    const onTitleUpdated = vi.fn();

    useAutomaticThreadTitle({
      projectId: "proj-1",
      threadId: "thread-1",
      runStatus,
      runId,
      accessThread,
      messages,
      onTitleUpdated,
    });

    await nextTick();

    await vi.waitFor(() => {
      expect(mockSummarizeTitle).toHaveBeenCalled();
      expect(onTitleUpdated).toHaveBeenCalledWith("用户之前修改的自定义标题");
    });
  });

  it("当发生 503 title_write_unconfirmed 时，触发单次 GET 对账并自愈", async () => {
    const error503: any = new Error("Title write is unconfirmed");
    error503.status = 503;
    error503.code = "title_write_unconfirmed";
    mockSummarizeTitle.mockRejectedValueOnce(error503);

    mockGet.mockResolvedValueOnce({
      thread_id: "thread-1",
      metadata: { title: "已落库的对账标题", auto_title_pending: false },
    });

    const runStatus = ref("success");
    const runId = ref("run-1");
    const accessThread = ref<any>({
      thread_id: "thread-1",
      metadata: { auto_title_pending: true },
    });
    const messages = ref<any[]>([
      { type: "human", content: "测试对账" },
      { id: "ai-1", type: "ai", content: "对账回复正文" },
    ]);
    const onTitleUpdated = vi.fn();

    useAutomaticThreadTitle({
      projectId: "proj-1",
      threadId: "thread-1",
      runStatus,
      runId,
      accessThread,
      messages,
      onTitleUpdated,
    });

    await nextTick();

    await vi.waitFor(() => {
      expect(mockSummarizeTitle).toHaveBeenCalled();
      expect(mockGet).toHaveBeenCalledWith("thread-1");
      expect(onTitleUpdated).toHaveBeenCalledWith("已落库的对账标题");
    });
  });

  it("单飞守卫：同一 projectId:threadId:runId 不重复调用", async () => {
    mockSummarizeTitle.mockResolvedValueOnce({
      thread_id: "thread-1",
      title: "单飞标题",
      outcome: "applied",
      reason: null,
    });

    const runStatus = ref("success");
    const runId = ref("run-1");
    const accessThread = ref<any>({
      thread_id: "thread-1",
      metadata: { auto_title_pending: true },
    });
    const messages = ref<any[]>([
      { type: "human", content: "你好" },
      { id: "ai-1", type: "ai", content: "世界" },
    ]);
    const onTitleUpdated = vi.fn();

    const hook = useAutomaticThreadTitle({
      projectId: "proj-1",
      threadId: "thread-1",
      runStatus,
      runId,
      accessThread,
      messages,
      onTitleUpdated,
    });

    await nextTick();
    await vi.waitFor(() => {
      expect(mockSummarizeTitle).toHaveBeenCalledTimes(1);
    });

    // 再次手动触发检查
    await hook.trigger();
    expect(mockSummarizeTitle).toHaveBeenCalledTimes(1);
  });
});

import { describe, it, expect, vi, beforeEach } from "vitest";
import { ref, nextTick } from "vue";
import { useFollowUpSuggestions } from "./useFollowUpSuggestions";
import * as api from "../suggestions/api";

vi.mock("../suggestions/api", () => ({
  loadSuggestionsConfig: vi.fn(),
  generateThreadSuggestions: vi.fn(),
}));

describe("useFollowUpSuggestions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("当回答完成（isRunning: true -> false）时自动触发建议生成", async () => {
    vi.mocked(api.loadSuggestionsConfig).mockResolvedValueOnce({
      enabled: true,
      max_suggestions: 3,
    });
    vi.mocked(api.generateThreadSuggestions).mockResolvedValueOnce([
      "问题 1",
      "问题 2",
    ]);

    const isRunning = ref(true);
    const messages = ref([
      { type: "human", content: "请介绍一下架构" },
      { id: "ai-1", type: "ai", content: "这是架构介绍" },
    ]);

    const hook = useFollowUpSuggestions({
      projectId: "proj-1",
      threadId: "thread-1",
      messages,
      isRunning,
    });

    expect(hook.suggestions.value).toEqual([]);
    expect(hook.loading.value).toBe(false);

    // 模拟运行结束
    isRunning.value = false;
    await nextTick();
    // 等待异步完成
    await vi.waitFor(() => {
      expect(hook.loading.value).toBe(false);
      expect(hook.suggestions.value).toEqual(["问题 1", "问题 2"]);
    });

    expect(api.loadSuggestionsConfig).toHaveBeenCalledWith(
      "proj-1",
      expect.any(AbortSignal),
    );
    expect(api.generateThreadSuggestions).toHaveBeenCalledWith(
      "proj-1",
      "thread-1",
      expect.objectContaining({
        messages: [
          { role: "user", content: "请介绍一下架构" },
          { role: "assistant", content: "这是架构介绍" },
        ],
        n: 3,
      }),
      expect.any(AbortSignal),
    );
  });

  it("用户主动停止（markStoppedByUser）时抑制建议生成", async () => {
    const isRunning = ref(true);
    const messages = ref([{ id: "ai-1", type: "ai", content: "半截回答..." }]);

    const hook = useFollowUpSuggestions({
      projectId: "proj-1",
      threadId: "thread-1",
      messages,
      isRunning,
    });

    hook.markStoppedByUser();
    isRunning.value = false;
    await nextTick();

    expect(api.generateThreadSuggestions).not.toHaveBeenCalled();
    expect(hook.suggestions.value).toEqual([]);
  });

  it("切换 threadId 时立即清空并重置建议", async () => {
    vi.mocked(api.loadSuggestionsConfig).mockResolvedValue({
      enabled: true,
      max_suggestions: 3,
    });
    vi.mocked(api.generateThreadSuggestions).mockResolvedValue(["建议 A"]);

    const isRunning = ref(false);
    const threadId = ref("thread-1");
    const messages = ref([{ id: "ai-1", type: "ai", content: "答复 1" }]);

    const hook = useFollowUpSuggestions({
      projectId: "proj-1",
      threadId,
      messages,
      isRunning,
    });

    await hook.trigger();
    expect(hook.suggestions.value).toEqual(["建议 A"]);

    // 切换到 thread-2
    threadId.value = "thread-2";
    await nextTick();

    expect(hook.suggestions.value).toEqual([]);
  });

  it("KeepAlive 后台抑制与切回前台补偿拉取", async () => {
    vi.mocked(api.loadSuggestionsConfig).mockResolvedValue({
      enabled: true,
      max_suggestions: 3,
    });
    vi.mocked(api.generateThreadSuggestions).mockResolvedValue([
      "后台补偿建议",
    ]);

    const isRunning = ref(true);
    const visible = ref(false); // 后台状态
    const messages = ref([{ id: "ai-1", type: "ai", content: "后台回答完成" }]);

    const hook = useFollowUpSuggestions({
      projectId: "proj-1",
      threadId: "thread-1",
      messages,
      isRunning,
      visible,
    });

    // 后台跑完
    isRunning.value = false;
    await nextTick();

    // 后台不发请求
    expect(api.generateThreadSuggestions).not.toHaveBeenCalled();
    expect(hook.suggestions.value).toEqual([]);

    // 切回前台
    visible.value = true;
    await nextTick();

    await vi.waitFor(() => {
      expect(hook.suggestions.value).toEqual(["后台补偿建议"]);
    });
  });

  it("dismiss 能主动收起建议", async () => {
    vi.mocked(api.loadSuggestionsConfig).mockResolvedValue({
      enabled: true,
      max_suggestions: 3,
    });
    vi.mocked(api.generateThreadSuggestions).mockResolvedValue(["建议 1"]);

    const isRunning = ref(false);
    const messages = ref([{ id: "ai-1", type: "ai", content: "回答" }]);

    const hook = useFollowUpSuggestions({
      projectId: "proj-1",
      threadId: "thread-1",
      messages,
      isRunning,
    });

    await hook.trigger();
    expect(hook.suggestions.value).toEqual(["建议 1"]);
    expect(hook.dismissed.value).toBe(false);

    hook.dismiss();
    expect(hook.dismissed.value).toBe(true);
    expect(hook.suggestions.value).toEqual([]);
  });

  it("当 hasError 为 true 时严格拦截推荐问题生成", async () => {
    vi.mocked(api.loadSuggestionsConfig).mockResolvedValue({
      enabled: true,
      max_suggestions: 3,
    });
    vi.mocked(api.generateThreadSuggestions).mockResolvedValue(["建议 1"]);

    const isRunning = ref(true);
    const hasError = ref(true);
    const messages = ref([
      { id: "ai-1", type: "ai", content: "部分回答中断..." },
    ]);

    const hook = useFollowUpSuggestions({
      projectId: "proj-1",
      threadId: "thread-1",
      messages,
      isRunning,
      hasError,
    });

    isRunning.value = false;
    await nextTick();

    expect(api.generateThreadSuggestions).not.toHaveBeenCalled();
    expect(hook.suggestions.value).toEqual([]);
  });

  it("当 runStatus 非 success (如 error 或 interrupted) 时严格拦截推荐问题生成", async () => {
    vi.mocked(api.loadSuggestionsConfig).mockResolvedValue({
      enabled: true,
      max_suggestions: 3,
    });
    vi.mocked(api.generateThreadSuggestions).mockResolvedValue(["建议 1"]);

    const isRunning = ref(true);
    const runStatus = ref("interrupted");
    const messages = ref([{ id: "ai-1", type: "ai", content: "已被用户停止" }]);

    const hook = useFollowUpSuggestions({
      projectId: "proj-1",
      threadId: "thread-1",
      messages,
      isRunning,
      runStatus,
    });

    isRunning.value = false;
    await nextTick();

    expect(api.generateThreadSuggestions).not.toHaveBeenCalled();
    expect(hook.suggestions.value).toEqual([]);

    // 切换为 success 时正常触发
    runStatus.value = "success";
    await hook.trigger();
    await vi.waitFor(() => {
      expect(hook.suggestions.value).toEqual(["建议 1"]);
    });
  });
});

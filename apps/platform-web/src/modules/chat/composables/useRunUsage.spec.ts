import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { ref, nextTick } from "vue";
import { useRunUsage } from "./useRunUsage";
import * as usageService from "@/services/threads/usage.service";
import usageFixtures from "../../../../../../docs/projects/20261007-agent-usage-cost-governance/fixtures/usage-v1.json";

describe("useRunUsage composable", () => {
  const runSample1 = (usageFixtures as any).samples.run_complete_page1;
  const threadSample = (usageFixtures as any).samples.thread_complete;

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("初始加载并发拉取 Run 用量与 Thread 摘要", async () => {
    vi.spyOn(usageService, "getRunUsage").mockResolvedValueOnce(runSample1);
    vi.spyOn(usageService, "getThreadUsage").mockResolvedValueOnce(
      threadSample,
    );

    const threadId = ref("th-1");
    const runId = ref("run-1");

    const usage = useRunUsage({
      threadId,
      runId,
    });

    await nextTick();
    expect(usageService.getRunUsage).toHaveBeenCalledWith(
      "th-1",
      "run-1",
      expect.any(Object),
    );
    expect(usageService.getThreadUsage).toHaveBeenCalledWith(
      "th-1",
      expect.any(Object),
    );

    // 等待状态设置
    await vi.waitFor(() => {
      expect(usage.runData.value?.run_id).toBe(runSample1.run_id);
      expect(usage.threadData.value?.thread_id).toBe(threadSample.thread_id);
      expect(usage.calls.value.length).toBe(runSample1.calls.items.length);
      expect(usage.nextCursor.value).toBe(runSample1.calls.next_cursor);
    });
  });

  it("仅切换 runId 时，只刷新 Run 用量，保留原 Thread 摘要且不重复发起 Thread 请求", async () => {
    vi.spyOn(usageService, "getRunUsage").mockResolvedValue(runSample1);
    vi.spyOn(usageService, "getThreadUsage").mockResolvedValue(threadSample);

    const threadId = ref("th-1");
    const runId = ref("run-1");

    const usage = useRunUsage({ threadId, runId });
    await nextTick();

    await vi.waitFor(() => {
      expect(usage.threadData.value).not.toBeNull();
    });

    // 清空 mock 计数
    vi.mocked(usageService.getThreadUsage).mockClear();
    vi.mocked(usageService.getRunUsage).mockClear();

    // 仅切换 runId
    runId.value = "run-2";
    await nextTick();

    expect(usageService.getRunUsage).toHaveBeenCalledWith(
      "th-1",
      "run-2",
      expect.any(Object),
    );
    // 关键断言：Thread 请求决不能再次调用！
    expect(usageService.getThreadUsage).not.toHaveBeenCalled();
    // 关键断言：Thread 数据依然保留！
    expect(usage.threadData.value?.thread_id).toBe(threadSample.thread_id);
  });

  it("loadMoreCalls 基于 cursor 正确分页追加并按 model_call_id 去重", async () => {
    const page1 = {
      ...runSample1,
      calls: {
        items: [{ ...runSample1.calls.items[0], model_call_id: "call-1" }],
        next_cursor: "cursor-token-2",
      },
    };
    const page2 = {
      ...runSample1,
      calls: {
        items: [
          { ...runSample1.calls.items[0], model_call_id: "call-1" }, // 重复项
          { ...runSample1.calls.items[0], model_call_id: "call-2" }, // 新项
        ],
        next_cursor: null,
      },
    };

    vi.spyOn(usageService, "getRunUsage")
      .mockResolvedValueOnce(page1)
      .mockResolvedValueOnce(page2);
    vi.spyOn(usageService, "getThreadUsage").mockResolvedValue(threadSample);

    const usage = useRunUsage({
      threadId: ref("th-1"),
      runId: ref("run-1"),
    });

    await nextTick();
    await vi.waitFor(() => {
      expect(usage.calls.value.length).toBe(1);
    });

    // 加载第二页
    await usage.loadMoreCalls();

    expect(usage.calls.value.length).toBe(2);
    expect(usage.calls.value.map((c) => c.model_call_id)).toEqual([
      "call-1",
      "call-2",
    ]);
    expect(usage.nextCursor.value).toBeNull();
  });

  it("403 权限拒绝时立即清空数据", async () => {
    vi.spyOn(usageService, "getRunUsage").mockRejectedValueOnce(
      Object.assign(new Error("Forbidden"), { status: 403 }),
    );
    vi.spyOn(usageService, "getThreadUsage").mockResolvedValue(threadSample);

    const usage = useRunUsage({
      threadId: ref("th-1"),
      runId: ref("run-1"),
    });

    await nextTick();
    await vi.waitFor(() => {
      expect(usage.runData.value).toBeNull();
      expect(usage.runError.value).toBeDefined();
    });
  });

  it("Run 状态由 running 转为 terminal 且未 finalized 时，单次延迟 2 秒重查，绝不死循环", async () => {
    const unfinishedRun = {
      ...runSample1,
      finalized: false,
    };
    const finishedRun = {
      ...runSample1,
      finalized: true,
    };

    const getRunUsageSpy = vi
      .spyOn(usageService, "getRunUsage")
      .mockResolvedValueOnce(unfinishedRun)
      .mockResolvedValueOnce(finishedRun);
    vi.spyOn(usageService, "getThreadUsage").mockResolvedValue(threadSample);

    const runStatus = ref("running");
    const usage = useRunUsage({
      threadId: ref("th-1"),
      runId: ref("run-1"),
      runStatus,
    });

    await nextTick();
    await vi.waitFor(() => {
      expect(usage.runData.value?.finalized).toBe(false);
    });

    // 状态转为 success
    runStatus.value = "success";
    await nextTick();

    // 还没过 2 秒，不触发
    expect(getRunUsageSpy).toHaveBeenCalledTimes(1);

    // 快进 2000ms
    vi.advanceTimersByTime(2000);
    await nextTick();

    expect(getRunUsageSpy).toHaveBeenCalledTimes(2);

    // 再次变动 status，不会再次触发延迟重查（单次锁）
    runStatus.value = "error";
    await nextTick();
    vi.advanceTimersByTime(2000);
    await nextTick();

    expect(getRunUsageSpy).toHaveBeenCalledTimes(2);
  });

  it("Run 状态由 running 转为 completed 终态时也能正确触发 2 秒延迟重查", async () => {
    const unfinishedRun = { ...runSample1, finalized: false };
    const finishedRun = { ...runSample1, finalized: true };

    const getRunUsageSpy = vi
      .spyOn(usageService, "getRunUsage")
      .mockResolvedValueOnce(unfinishedRun)
      .mockResolvedValueOnce(finishedRun);
    vi.spyOn(usageService, "getThreadUsage").mockResolvedValue(threadSample);

    const runStatus = ref("running");
    const usage = useRunUsage({
      threadId: ref("th-1"),
      runId: ref("run-1"),
      runStatus,
    });

    await nextTick();
    await vi.waitFor(() => {
      expect(usage.runData.value?.finalized).toBe(false);
    });

    // 状态转为 LangGraph 原生 completed
    runStatus.value = "completed";
    await nextTick();

    vi.advanceTimersByTime(2000);
    await nextTick();

    expect(getRunUsageSpy).toHaveBeenCalledTimes(2);
  });

  it("切换 projectId 时清空数据并重新拉取", async () => {
    vi.spyOn(usageService, "getRunUsage").mockResolvedValue(runSample1);
    vi.spyOn(usageService, "getThreadUsage").mockResolvedValue(threadSample);

    const projectId = ref<string | undefined>("proj-1");
    const threadId = ref("th-1");
    const runId = ref("run-1");

    useRunUsage({ projectId, threadId, runId });
    await nextTick();

    vi.mocked(usageService.getRunUsage).mockClear();
    vi.mocked(usageService.getThreadUsage).mockClear();

    // 切换 projectId
    projectId.value = "proj-2";
    await nextTick();

    expect(usageService.getRunUsage).toHaveBeenCalledWith(
      "th-1",
      "run-1",
      expect.objectContaining({ projectId: "proj-2" }),
    );
    expect(usageService.getThreadUsage).toHaveBeenCalledWith(
      "th-1",
      expect.objectContaining({ projectId: "proj-2" }),
    );
  });
});

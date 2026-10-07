import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import { useRunDiagnostics } from "./useRunDiagnostics";
import { getRunDiagnostics } from "@/services/threads/diagnostics.service";
import type { RunDiagnosticsV1 } from "../diagnostics/types";

vi.mock("@/services/threads/diagnostics.service", () => ({
  getRunDiagnostics: vi.fn(),
}));

describe("useRunDiagnostics", () => {
  const mockDiagnostic: RunDiagnosticsV1 = {
    version: 1,
    thread_id: "thread-1",
    run_id: "run-1",
    run_status: "success",
    request_id: "req-1",
    availability: "available",
    unavailable_reason: null,
    correlation: { execution_request_id: null, platform_trace_id: null },
    trace: null,
    graph_executions: [],
    model_errors: [],
    startup: null,
    truncated: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("当 runId 存在且 enabled 为 true 时自动加载诊断", async () => {
    vi.mocked(getRunDiagnostics).mockResolvedValueOnce(mockDiagnostic);

    const projectId = ref("proj-1");
    const threadId = ref("thread-1");
    const runId = ref("run-1");
    const enabled = ref(true);

    const { data, loading } = useRunDiagnostics({
      projectId,
      threadId,
      runId,
      enabled,
    });

    expect(loading.value).toBe(true);
    await vi.runAllTimersAsync();

    expect(getRunDiagnostics).toHaveBeenCalledWith(
      "thread-1",
      "run-1",
      expect.any(Object),
    );
    expect(data.value?.run_id).toBe("run-1");
    expect(loading.value).toBe(false);
  });

  it("防竞态：旧请求慢返回不会覆盖新请求的数据", async () => {
    let resolveFirst: (val: RunDiagnosticsV1) => void;
    const firstPromise = new Promise<RunDiagnosticsV1>((resolve) => {
      resolveFirst = resolve;
    });

    const secondDiagnostic: RunDiagnosticsV1 = {
      ...mockDiagnostic,
      run_id: "run-2",
    };

    vi.mocked(getRunDiagnostics)
      .mockImplementationOnce(() => firstPromise)
      .mockResolvedValueOnce(secondDiagnostic);

    const projectId = ref("proj-1");
    const threadId = ref("thread-1");
    const runId = ref("run-1");

    const { data } = useRunDiagnostics({
      projectId,
      threadId,
      runId,
    });

    // 迅速切换到 run-2
    runId.value = "run-2";
    await vi.runAllTimersAsync();

    expect(data.value?.run_id).toBe("run-2");

    // 此时第 1 个慢请求 resolve
    resolveFirst!(mockDiagnostic);
    await vi.runAllTimersAsync();

    // 数据必须仍是 run-2，绝不能被旧请求覆盖
    expect(data.value?.run_id).toBe("run-2");
  });

  it("切换 thread 时立即物理清空旧诊断数据", async () => {
    vi.mocked(getRunDiagnostics).mockResolvedValueOnce(mockDiagnostic);

    const projectId = ref("proj-1");
    const threadId = ref("thread-1");
    const runId = ref("run-1");

    const { data } = useRunDiagnostics({
      projectId,
      threadId,
      runId,
    });

    await vi.runAllTimersAsync();
    expect(data.value?.run_id).toBe("run-1");

    // 切换到新 thread
    threadId.value = "thread-2";
    expect(data.value).toBeNull();
  });

  it("403 权限拒绝时清空数据", async () => {
    vi.mocked(getRunDiagnostics).mockRejectedValueOnce(
      Object.assign(new Error("无权访问"), { status: 403, code: "forbidden" }),
    );

    const projectId = ref("proj-1");
    const threadId = ref("thread-1");
    const runId = ref("run-1");

    const { data, error } = useRunDiagnostics({
      projectId,
      threadId,
      runId,
    });

    await vi.runAllTimersAsync();
    expect(data.value).toBeNull();
    expect(error.value).toMatchObject({ status: 403 });
  });

  it("收到 unavailable/not_recorded 时延迟 2 秒自动重查最多一次", async () => {
    const unrecDiagnostic: RunDiagnosticsV1 = {
      ...mockDiagnostic,
      availability: "unavailable",
      unavailable_reason: "not_recorded",
      run_status: "success",
    };

    const finalDiagnostic: RunDiagnosticsV1 = {
      ...mockDiagnostic,
      availability: "available",
      run_status: "success",
    };

    vi.mocked(getRunDiagnostics)
      .mockResolvedValueOnce(unrecDiagnostic)
      .mockResolvedValueOnce(finalDiagnostic);

    const projectId = ref("proj-1");
    const threadId = ref("thread-1");
    const runId = ref("run-1");

    const { data } = useRunDiagnostics({
      projectId,
      threadId,
      runId,
    });

    await vi.advanceTimersByTimeAsync(0);
    expect(data.value?.availability).toBe("unavailable");
    expect(getRunDiagnostics).toHaveBeenCalledTimes(1);

    // 前进 2 秒，触发单次重查
    await vi.advanceTimersByTimeAsync(2000);
    expect(getRunDiagnostics).toHaveBeenCalledTimes(2);
    expect(data.value?.availability).toBe("available");

    // 再过 5 秒，绝不能无限轮询
    await vi.advanceTimersByTimeAsync(5000);
    expect(getRunDiagnostics).toHaveBeenCalledTimes(2);
  });
});

import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { ref } from "vue";
import { useThreadStopControl } from "./useThreadStopControl";
import type { StopRequest } from "../stop/types";

describe("useThreadStopControl", () => {
  const mockReceipt: StopRequest = {
    version: 1,
    stop_id: "33333333-3333-4333-8333-333333333333",
    thread_id: "11111111-1111-4111-8111-111111111111",
    phase: "stopped",
    requested_at: "2026-10-07T06:00:00Z",
    accepted_at: "2026-10-07T06:00:00.100Z",
    confirmed_at: "2026-10-07T06:00:01Z",
    target_count: 2,
    execution_stopped: true,
    resource_cleanup: "confirmed",
    has_pending_interrupts: false,
    queue: {
      pending_cancelled_count: 1,
      inbox_consumed_count: 1,
      inbox_not_consumed_count: 0,
    },
    report: {
      version: 1,
      source: "checkpoint_and_receipts",
      checkpoint_id: "cp-1",
      checkpoints: [
        {
          run_id: "22222222-2222-4222-8222-222222222222",
          checkpoint_id: "cp-1",
        },
      ],
      progress: [
        {
          kind: "saved_plan",
          label: "plan",
          observed_status: "in_progress",
          source_run_id: "22222222-2222-4222-8222-222222222222",
        },
      ],
      artifacts: [],
      uncertainties: [],
      truncated: false,
    },
    reason_code: null,
    request_id: "req-1",
  };

  const stoppingReceipt: StopRequest = {
    ...mockReceipt,
    phase: "stopping",
    confirmed_at: null,
    execution_stopped: null,
    resource_cleanup: "pending",
  };

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    localStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
    localStorage.clear();
  });

  it("initiates stop request, polls until confirmed, and cleans localStorage", async () => {
    const threadId = ref("11111111-1111-4111-8111-111111111111");
    const stopThreadMock = vi.fn().mockResolvedValueOnce(stoppingReceipt);
    const getStopRequestMock = vi.fn().mockResolvedValueOnce(mockReceipt);
    const listStopRequestsMock = vi.fn().mockResolvedValue({ items: [] });
    const onStopConfirmed = vi.fn();

    const mockService = {
      stopThread: stopThreadMock,
      getStopRequest: getStopRequestMock,
      listStopRequests: listStopRequestsMock,
    } as any;

    const control = useThreadStopControl({
      projectId: ref("p-1"),
      threadId,
      userId: ref("u-1"),
      service: mockService,
      onStopConfirmed,
    });

    expect(control.phase.value).toBe("idle");
    const stopPromise = control.stop();
    expect(control.phase.value).toBe("submitting");

    await stopPromise;
    expect(control.phase.value).toBe("stopping");
    expect(control.currentStopId.value).toBe(mockReceipt.stop_id);
    expect(stopThreadMock).toHaveBeenCalledWith(
      threadId.value,
      expect.stringMatching(/^stop:[0-9a-f-]+$/i),
    );

    // Fast-forward 2000ms for polling step
    await vi.advanceTimersByTimeAsync(2000);
    expect(getStopRequestMock).toHaveBeenCalledWith(
      threadId.value,
      mockReceipt.stop_id,
    );

    expect(control.phase.value).toBe("stopped");
    expect(control.isConfirmed.value).toBe(true);
    expect(control.targetCount.value).toBe(2);
    expect(onStopConfirmed).toHaveBeenCalledWith(mockReceipt);

    // localStorage should be cleaned upon confirmation
    expect(
      localStorage.getItem(`pw:thread:stop:u-1:0:p-1:${threadId.value}`),
    ).toBeNull();
  });

  it("handles timeout after 45 seconds by degrading to confirmation_unavailable and stops polling", async () => {
    const threadId = ref("11111111-1111-4111-8111-111111111111");
    const stopThreadMock = vi.fn().mockResolvedValueOnce(stoppingReceipt);
    const getStopRequestMock = vi.fn().mockResolvedValue(stoppingReceipt);

    const mockService = {
      stopThread: stopThreadMock,
      getStopRequest: getStopRequestMock,
      listStopRequests: vi.fn().mockResolvedValue({ items: [] }),
    } as any;

    const control = useThreadStopControl({
      projectId: ref("p-1"),
      threadId,
      userId: ref("u-1"),
      service: mockService,
    });

    await control.stop();
    expect(control.phase.value).toBe("stopping");

    // Advance 24 * 2000ms to allow each chained async poll step to execute
    for (let i = 0; i < 24; i++) {
      await vi.advanceTimersByTimeAsync(2000);
    }

    expect(control.phase.value).toBe("confirmation_unavailable");
    expect(control.isConfirmationUnavailable.value).toBe(true);
    expect(control.stopError.value).toBe("停止确认超时，请手动核实");

    // Ensure no further polling occurs
    const callCount = getStopRequestMock.mock.calls.length;
    await vi.advanceTimersByTimeAsync(10000);
    expect(getStopRequestMock.mock.calls.length).toBe(callCount);
  });

  it("handles network failure by preserving Idempotency-Key and allowing retry", async () => {
    const threadId = ref("11111111-1111-4111-8111-111111111111");
    const networkError = new Error("Gateway Timeout");
    (networkError as any).status = 504;

    const stopThreadMock = vi
      .fn()
      .mockRejectedValueOnce(networkError)
      .mockResolvedValueOnce(mockReceipt);

    const mockService = {
      stopThread: stopThreadMock,
      getStopRequest: vi.fn(),
      listStopRequests: vi.fn().mockResolvedValue({ items: [] }),
    } as any;

    const control = useThreadStopControl({
      projectId: ref("p-1"),
      threadId,
      userId: ref("u-1"),
      service: mockService,
    });

    await control.stop();
    expect(control.phase.value).toBe("confirmation_unavailable");
    expect(control.stopError.value).toContain("停止请求结果待确认");

    // Key must be saved in localStorage
    const saved = JSON.parse(
      localStorage.getItem(`pw:thread:stop:u-1:0:p-1:${threadId.value}`)!,
    );
    expect(saved.key).toMatch(/^stop:/);
    expect(saved.status).toBe("unknown");

    // Retry should reuse the original key
    await control.retry();
    expect(stopThreadMock).toHaveBeenLastCalledWith(threadId.value, saved.key);
    expect(control.phase.value).toBe("stopped");
  });

  it("isolates scope and aborts polling when thread changes", async () => {
    const threadId = ref("thread-alpha");
    const stopThreadMock = vi.fn().mockResolvedValueOnce(stoppingReceipt);
    const getStopRequestMock = vi.fn().mockResolvedValue(stoppingReceipt);

    const mockService = {
      stopThread: stopThreadMock,
      getStopRequest: getStopRequestMock,
      listStopRequests: vi.fn().mockResolvedValue({ items: [] }),
    } as any;

    const control = useThreadStopControl({
      projectId: ref("p-1"),
      threadId,
      userId: ref("u-1"),
      service: mockService,
    });

    await control.stop();
    expect(control.phase.value).toBe("stopping");

    // Switch thread
    threadId.value = "thread-beta";
    await vi.advanceTimersByTimeAsync(0);

    expect(control.phase.value).toBe("idle");
    expect(control.currentStopId.value).toBeNull();

    // Advancing timers should not poll for thread-alpha anymore
    const countBefore = getStopRequestMock.mock.calls.length;
    await vi.advanceTimersByTimeAsync(5000);
    expect(getStopRequestMock.mock.calls.length).toBe(countBefore);
  });
});

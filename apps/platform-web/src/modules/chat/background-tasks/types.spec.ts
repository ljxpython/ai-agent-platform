import { describe, expect, it } from "vitest";
import {
  safeParseOutputV1,
  safeParseTaskListV1,
  safeParseTaskV1,
} from "./types";

describe("background-tasks/types Schema 校验", () => {
  const validTaskPayload = {
    version: 1,
    task_id: "4ce62cd1-4d07-493e-89ed-d107bdddc8dd",
    thread_id: "3f435938-f5f2-42df-9a31-33839c623671",
    graph_id: "showcase_demo",
    origin_run_id: "734d3540-a0f8-4550-bdf7-f0fa8d0ae0e4",
    status: "succeeded",
    reason_code: null,
    exit_code: 0,
    created_at: "2026-10-09T01:00:00+08:00",
    started_at: "2026-10-09T01:00:01+08:00",
    finished_at: "2026-10-09T01:00:10+08:00",
    deadline_at: "2026-10-09T01:15:00+08:00",
    updated_at: "2026-10-09T01:00:10+08:00",
    cleanup_state: "confirmed",
    output: {
      available: true,
      retained_bytes: 15,
      omitted_bytes: 0,
      truncated: false,
      updated_at: "2026-10-09T01:00:10+08:00",
      extra_unknown_field: "should be stripped",
    },
    delivery: {
      state: "accepted",
      event_id: "11111111-2222-3333-4444-555555555555",
      run_id: "ad3a85dd-1035-4dca-93e7-22ec5e7c6b23",
      reason_code: null,
    },
    allowed_actions: ["read", "logs"],
  };

  it("应当正确解析合法的 TaskV1 并 strip 掉未知字段", () => {
    const result = safeParseTaskV1(validTaskPayload);
    expect(result.success).toBe(true);
    expect(result.data?.task_id).toBe("4ce62cd1-4d07-493e-89ed-d107bdddc8dd");
    expect(
      (result.data?.output as Record<string, unknown>).extra_unknown_field,
    ).toBeUndefined();
  });

  it("应当支持负信号退出码 (例如 SIGKILL -9 或 SIGTERM -15)", () => {
    const payloadWithNegativeExit = {
      ...validTaskPayload,
      exit_code: -9,
      status: "failed",
    };
    const result = safeParseTaskV1(payloadWithNegativeExit);
    expect(result.success).toBe(true);
    expect(result.data?.exit_code).toBe(-9);
  });

  it("应当支持 null 退出码 (例如 running 状态)", () => {
    const payloadRunning = {
      ...validTaskPayload,
      exit_code: null,
      status: "running",
    };
    const result = safeParseTaskV1(payloadRunning);
    expect(result.success).toBe(true);
    expect(result.data?.exit_code).toBeNull();
  });

  it("应当拒绝超出范围的非法退出码 (例如 > 255 或 < -255)", () => {
    const invalidExit = {
      ...validTaskPayload,
      exit_code: 999,
    };
    const result = safeParseTaskV1(invalidExit);
    expect(result.success).toBe(false);
  });

  it("应当正确解析 TaskListV1", () => {
    const listPayload = {
      version: 1,
      thread_id: "3f435938-f5f2-42df-9a31-33839c623671",
      items: [validTaskPayload],
      next_cursor: "cursor-123",
      has_unresolved: true,
      latest_delivery_run_id: "ad3a85dd-1035-4dca-93e7-22ec5e7c6b23",
    };
    const result = safeParseTaskListV1(listPayload);
    expect(result.success).toBe(true);
    expect(result.data?.items).toHaveLength(1);
    expect(result.data?.has_unresolved).toBe(true);
  });

  it("应当正确解析 OutputV1 并检验最大文本上限", () => {
    const outputPayload = {
      version: 1,
      task_id: "4ce62cd1-4d07-493e-89ed-d107bdddc8dd",
      thread_id: "3f435938-f5f2-42df-9a31-33839c623671",
      available: true,
      text: "build succeeded\n10 passed",
      retained_bytes: 1024,
      omitted_bytes: 0,
      truncated: false,
      updated_at: "2026-10-09T01:00:10Z",
    };
    const result = safeParseOutputV1(outputPayload);
    expect(result.success).toBe(true);
    expect(result.data?.text).toBe("build succeeded\n10 passed");
  });
});

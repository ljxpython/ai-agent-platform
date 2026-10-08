import { computed, ref, shallowRef } from "vue";
import { describe, expect, it, vi } from "vitest";
import { BoundedNoticeCache, useRunBudget } from "./useRunBudget";

// Mock useChannel from @langchain/vue
const mockRawEvents = shallowRef<any[]>([]);
vi.mock("@langchain/vue", () => ({
  useChannel: vi.fn(() => mockRawEvents),
}));

describe("composables/useRunBudget.ts", () => {
  it("isolates notices strictly matching current runId", () => {
    const runId = ref("run-current");
    const stream = {} as any;

    const { activeNotice, budget } = useRunBudget(stream, {
      runId,
    });

    // Populate events with both old run and current run
    mockRawEvents.value = [
      {
        method: "custom",
        params: {
          namespace: [],
          data: {
            version: 1,
            type: "runtime_budget_notice",
            notice_id: "notice-old",
            run_id: "run-old",
            scope: "primary",
            budget_scope: "run",
            code: "model_call_limit_reached",
            limit: 10,
            used: 10,
            remaining: 0,
            unit: "model_calls",
          },
        },
      },
      {
        method: "custom",
        params: {
          namespace: [],
          data: {
            version: 1,
            type: "runtime_budget_notice",
            notice_id: "notice-current",
            run_id: "run-current",
            scope: "primary",
            budget_scope: "run",
            code: "model_call_limit_approaching",
            limit: 10,
            used: 7,
            remaining: 3,
            unit: "model_calls",
          },
        },
      },
    ];

    expect(activeNotice.value).not.toBeNull();
    expect(activeNotice.value?.notice_id).toBe("notice-current");
    expect(budget.value?.level).toBe("warning");
    expect(budget.value?.remaining).toBe(3);
  });

  it("filters notices matching subagent namespace", () => {
    const runId = ref("run-subagent");
    const namespace = ref(["tools:task-1"]);
    const stream = {} as any;

    const { activeNotice } = useRunBudget(stream, {
      runId,
      namespace,
    });

    mockRawEvents.value = [
      {
        method: "custom",
        params: {
          namespace: ["tools:other-task"], // Different subagent namespace
          data: {
            version: 1,
            type: "runtime_budget_notice",
            notice_id: "notice-other",
            run_id: "run-subagent",
            scope: "subagent",
            budget_scope: "run",
            code: "model_call_limit_approaching",
            limit: 4,
            used: 1,
            remaining: 3,
            unit: "model_calls",
          },
        },
      },
      {
        method: "custom",
        params: {
          namespace: ["tools:task-1"], // Matching namespace
          data: {
            version: 1,
            type: "runtime_budget_notice",
            notice_id: "notice-matching",
            run_id: "run-subagent",
            scope: "subagent",
            budget_scope: "run",
            code: "model_call_limit_reached",
            limit: 4,
            used: 4,
            remaining: 0,
            unit: "model_calls",
          },
        },
      },
    ];

    expect(activeNotice.value).not.toBeNull();
    expect(activeNotice.value?.notice_id).toBe("notice-matching");
  });

  it("extracts end marker from lastMessage when live custom event has ended", () => {
    const runId = ref("run-end-marker");
    const stream = {} as any;
    mockRawEvents.value = []; // No live events

    const lastMessage = computed(() => ({
      role: "assistant",
      content: "Task ended due to budget limit",
      additional_kwargs: {
        runtime_budget_notice: {
          version: 1,
          type: "runtime_budget_notice",
          notice_id: "notice-end-marker",
          run_id: "run-end-marker",
          scope: "primary",
          budget_scope: "run",
          code: "model_call_limit_reached",
          limit: 10,
          used: 10,
          remaining: 0,
          unit: "model_calls",
        },
      },
    }));

    const { activeNotice, budget } = useRunBudget(stream, {
      runId,
      lastMessage,
      nativeStatus: ref("success"),
    });

    expect(activeNotice.value).not.toBeNull();
    expect(activeNotice.value?.notice_id).toBe("notice-end-marker");
    expect(budget.value?.isTerminal).toBe(true);
    expect(budget.value?.title).toBe("本次执行因额度限制停止");
  });

  it("identifies thread exhaustion state and sets isThreadExhausted flag", () => {
    const runId = ref("run-thread-exhausted");
    const stream = {} as any;

    const { isThreadExhausted, budget } = useRunBudget(stream, {
      runId,
    });

    mockRawEvents.value = [
      {
        method: "custom",
        params: {
          namespace: [],
          data: {
            version: 1,
            type: "runtime_budget_notice",
            notice_id: "notice-thread-1",
            run_id: "run-thread-exhausted",
            scope: "primary",
            budget_scope: "thread",
            code: "model_call_limit_reached",
            limit: 5,
            used: 5,
            remaining: 0,
            unit: "model_calls",
          },
        },
      },
    ];

    expect(isThreadExhausted.value).toBe(true);
    expect(budget.value?.actionType).toBe("new_thread");
  });

  it("enforces 200 item LRU bounded eviction on cache", () => {
    const cache = new BoundedNoticeCache(200);

    // Insert 205 entries
    for (let i = 1; i <= 205; i++) {
      cache.set(`notice-${i}`, {
        notice: {
          version: 1,
          type: "runtime_budget_notice",
          notice_id: `notice-${i}`,
          run_id: "run-test",
          scope: "primary",
          budget_scope: "run",
          code: "model_call_limit_approaching",
          limit: 10,
          used: 5,
          remaining: 5,
          unit: "model_calls",
        },
      });
    }

    expect(cache.size).toBe(200);
    const ids = cache.entries().map((e) => e.notice.notice_id);
    // Oldest 5 entries (1 to 5) should have been evicted
    expect(ids).not.toContain("notice-1");
    expect(ids).not.toContain("notice-5");
    expect(ids).toContain("notice-6");
    expect(ids).toContain("notice-205");
  });

  it("suppresses endMarkerNotice when native status is running to prevent flickering", () => {
    const runId = ref("run-new");
    const stream = {} as any;
    mockRawEvents.value = [];

    const lastMessage = computed(() => ({
      role: "assistant",
      content: "Previous stop",
      additional_kwargs: {
        runtime_budget_notice: {
          version: 1,
          type: "runtime_budget_notice",
          notice_id: "notice-old-end",
          run_id: "run-old",
          scope: "primary",
          budget_scope: "run",
          code: "model_call_limit_reached",
          limit: 10,
          used: 10,
          remaining: 0,
          unit: "model_calls",
        },
      },
    }));

    const { activeNotice, budget } = useRunBudget(stream, {
      runId,
      lastMessage,
      nativeStatus: ref("running"),
    });

    expect(activeNotice.value).toBeNull();
    expect(budget.value).toBeNull();
  });
});

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

  describe("Token Budget governance (F01)", () => {
    it("handles token_budget_approaching in-flight warning", () => {
      const runId = ref("run-token-1");
      const stream = {} as any;

      const { activeNotice, budget } = useRunBudget(stream, {
        runId,
        nativeStatus: ref("running"),
        isRunning: ref(true),
      });

      mockRawEvents.value = [
        {
          method: "custom",
          params: {
            namespace: [],
            data: {
              version: 1,
              type: "runtime_budget_notice",
              notice_id: "notice-token-warn",
              run_id: "run-token-1",
              scope: "primary",
              budget_scope: "run",
              code: "token_budget_approaching",
              limit: 100000,
              used: 81000,
              remaining: 19000,
              unit: "tokens_total",
            },
          },
        },
      ];

      expect(activeNotice.value).not.toBeNull();
      expect(activeNotice.value?.code).toBe("token_budget_approaching");
      expect(budget.value?.level).toBe("warning");
      expect(budget.value?.isTerminal).toBe(false);
      expect(budget.value?.remaining).toBe(19000);
      expect(budget.value?.description).toContain("19,000");
    });

    it("handles token_budget_exhausted in-flight transitioning to terminal error", () => {
      const runId = ref("run-token-2");
      const stream = {} as any;
      const nativeStatus = ref("running");
      const isRunning = ref(true);

      const { activeNotice, budget, isThreadExhausted } = useRunBudget(stream, {
        runId,
        nativeStatus,
        isRunning,
      });

      mockRawEvents.value = [
        {
          method: "custom",
          params: {
            namespace: [],
            data: {
              version: 1,
              type: "runtime_budget_notice",
              notice_id: "notice-token-exhausted",
              run_id: "run-token-2",
              scope: "primary",
              budget_scope: "run",
              code: "token_budget_exhausted",
              limit: 100000,
              used: 105000,
              remaining: 0,
              unit: "tokens_total",
            },
          },
        },
      ];

      // 1. In-flight transitioning state (running)
      expect(activeNotice.value?.code).toBe("token_budget_exhausted");
      expect(budget.value?.level).toBe("warning");
      expect(budget.value?.isTerminal).toBe(false);
      expect(budget.value?.description).toBe(
        "已触发额度保护，正在确认执行结果",
      );
      expect(budget.value?.actionType).toBe("none");
      expect(isThreadExhausted.value).toBe(false);

      // 2. Native error arrives (terminal)
      nativeStatus.value = "error";
      isRunning.value = false;

      expect(budget.value?.level).toBe("error");
      expect(budget.value?.isTerminal).toBe(true);
      expect(budget.value?.title).toBe("本次执行因Token额度停止");
      expect(budget.value?.actionType).toBe("adjust_draft");
      expect(budget.value?.actionLabel).toBe("调整请求");
      expect(isThreadExhausted.value).toBe(false);
    });

    it("handles token_budget_unverifiable with remaining=null and no retry action", () => {
      const runId = ref("run-token-3");
      const stream = {} as any;
      const nativeStatus = ref("error");
      const isRunning = ref(false);

      const { budget } = useRunBudget(stream, {
        runId,
        nativeStatus,
        isRunning,
      });

      mockRawEvents.value = [
        {
          method: "custom",
          params: {
            namespace: [],
            data: {
              version: 1,
              type: "runtime_budget_notice",
              notice_id: "notice-token-unverifiable",
              run_id: "run-token-3",
              scope: "primary",
              budget_scope: "run",
              code: "token_budget_unverifiable",
              limit: 100000,
              used: 0,
              remaining: null,
              unit: "tokens_total",
            },
          },
        },
      ];

      expect(budget.value?.level).toBe("error");
      expect(budget.value?.isTerminal).toBe(true);
      expect(budget.value?.title).toBe("用量无法确认");
      expect(budget.value?.remaining).toBeNull();
      expect(budget.value?.actionType).toBe("none");
    });

    it("recovers budget state via historicalStopCode when events are expired", () => {
      const runId = ref("run-token-hist");
      const stream = {} as any;
      mockRawEvents.value = []; // No live SSE events

      const historicalStopCode = ref<
        "token_budget_exhausted" | "token_budget_unverifiable" | null
      >("token_budget_exhausted");

      const { budget } = useRunBudget(stream, {
        runId,
        nativeStatus: ref("error"),
        isRunning: ref(false),
        historicalStopCode,
      });

      expect(budget.value).not.toBeNull();
      expect(budget.value?.code).toBe("token_budget_exhausted");
      expect(budget.value?.title).toBe("本次执行因Token额度停止");
      expect(budget.value?.actionType).toBe("adjust_draft");
    });
  });
});

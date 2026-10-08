import { describe, expect, it } from "vitest";
import {
  deriveBudgetViewModel,
  safeExtractBudgetNotice,
  safeExtractBudgetSafetyError,
} from "./view-model";

describe("budget/view-model.ts", () => {
  describe("safeExtractBudgetNotice", () => {
    it("extracts notice from v3 protocol raw event structure", () => {
      const rawEvent = {
        method: "custom",
        params: {
          namespace: [],
          data: {
            version: 1,
            type: "runtime_budget_notice",
            notice_id: "budget:run-1:primary:run:model_call_limit_approaching",
            run_id: "run-1",
            scope: "primary",
            budget_scope: "run",
            code: "model_call_limit_approaching",
            limit: 10,
            used: 7,
            remaining: 3,
            unit: "model_calls",
          },
        },
      };

      const notice = safeExtractBudgetNotice(rawEvent);
      expect(notice).not.toBeNull();
      expect(notice?.notice_id).toBe(
        "budget:run-1:primary:run:model_call_limit_approaching",
      );
      expect(notice?.remaining).toBe(3);
    });

    it("extracts floating-point seconds notice (wrapup_started) without rejection", () => {
      const rawNotice = {
        version: 1,
        type: "runtime_budget_notice",
        notice_id: "budget:run-3:primary:wrapup-started",
        run_id: "run-3",
        scope: "primary",
        budget_scope: "run",
        code: "wrapup_started",
        limit: 0.01,
        used: 0.9075320040001316,
        remaining: null,
        unit: "seconds",
      };

      const notice = safeExtractBudgetNotice(rawNotice);
      expect(notice).not.toBeNull();
      expect(notice?.code).toBe("wrapup_started");
      expect(notice?.limit).toBe(0.01);
      expect(notice?.used).toBe(0.9075320040001316);
      expect(notice?.remaining).toBeNull();
      expect(notice?.unit).toBe("seconds");
    });

    it("rejects non-integer limits for model_calls", () => {
      const invalidNotice = {
        version: 1,
        type: "runtime_budget_notice",
        notice_id: "budget:invalid",
        run_id: "run-1",
        scope: "primary",
        budget_scope: "run",
        code: "model_call_limit_approaching",
        limit: 10.5, // Invalid: must be integer
        used: 7,
        remaining: 3,
        unit: "model_calls",
      };

      const notice = safeExtractBudgetNotice(invalidNotice);
      expect(notice).toBeNull();
    });

    it("safely ignores unknown types and formats", () => {
      expect(safeExtractBudgetNotice(null)).toBeNull();
      expect(safeExtractBudgetNotice(undefined)).toBeNull();
      expect(safeExtractBudgetNotice({ foo: "bar" })).toBeNull();
      expect(safeExtractBudgetNotice({ type: "other_notice" })).toBeNull();
    });
  });

  describe("safeExtractBudgetSafetyError", () => {
    it("extracts valid safety error codes from direct object", () => {
      const err = {
        type: "GraphRecursionError",
        code: "runtime_graph_step_limit_reached",
        message: "Graph step limit reached",
      };
      const res = safeExtractBudgetSafetyError(err);
      expect(res).not.toBeNull();
      expect(res?.code).toBe("runtime_graph_step_limit_reached");
    });

    it("extracts safety error from nested error object", () => {
      const err = {
        status: "error",
        error: {
          code: "runtime_tool_call_limit_reached",
          type: "ToolCallLimitExceededError",
        },
      };
      const res = safeExtractBudgetSafetyError(err);
      expect(res).not.toBeNull();
      expect(res?.code).toBe("runtime_tool_call_limit_reached");
    });

    it("extracts safety error from Error instances and string messages", () => {
      const err1 = new Error("Graph step limit reached");
      expect(safeExtractBudgetSafetyError(err1)?.code).toBe(
        "runtime_graph_step_limit_reached",
      );

      const err2 =
        "Recursion limit of 3 reached without hitting a stop condition.";
      expect(safeExtractBudgetSafetyError(err2)?.code).toBe(
        "runtime_graph_step_limit_reached",
      );

      const err3 = new Error("Model call limit reached");
      expect(safeExtractBudgetSafetyError(err3)?.code).toBe(
        "runtime_model_call_limit_reached",
      );
    });

    it("extracts safety error from Error instance with [object Object] message and nested error", () => {
      const err = new Error("[object Object]");
      (err as any).error = {
        type: "GraphRecursionError",
        message:
          "Recursion limit of 10 reached without hitting a stop condition.",
      };
      const res = safeExtractBudgetSafetyError(err);
      expect(res).not.toBeNull();
      expect(res?.code).toBe("runtime_graph_step_limit_reached");
    });

    it("extracts safety error from Error instance with cause or response body", () => {
      const err = new Error("Request failed");
      (err as any).cause = {
        code: "runtime_graph_step_limit_reached",
      };
      const res = safeExtractBudgetSafetyError(err);
      expect(res).not.toBeNull();
      expect(res?.code).toBe("runtime_graph_step_limit_reached");
    });

    it("returns null for non-budget errors", () => {
      expect(
        safeExtractBudgetSafetyError({ code: "unknown_error" }),
      ).toBeNull();
      expect(safeExtractBudgetSafetyError("An error occurred")).toBeNull();
      expect(
        safeExtractBudgetSafetyError(new Error("Network timeout")),
      ).toBeNull();
    });
  });

  describe("deriveBudgetViewModel", () => {
    it("derives new_thread action when thread limit is reached", () => {
      const notice = {
        version: 1 as const,
        type: "runtime_budget_notice" as const,
        notice_id: "budget:1",
        run_id: "run-1",
        scope: "primary" as const,
        budget_scope: "thread" as const,
        code: "model_call_limit_reached" as const,
        limit: 5,
        used: 5,
        remaining: 0,
        unit: "model_calls" as const,
      };

      const vm = deriveBudgetViewModel(notice, null);
      expect(vm).not.toBeNull();
      expect(vm?.level).toBe("error");
      expect(vm?.isTerminal).toBe(true);
      expect(vm?.title).toBe("本会话累计调用额度已耗尽");
      expect(vm?.actionType).toBe("new_thread");
      expect(vm?.actionLabel).toBe("新建会话");
    });

    it("derives adjust_draft action when run limit is reached", () => {
      const notice = {
        version: 1 as const,
        type: "runtime_budget_notice" as const,
        notice_id: "budget:2",
        run_id: "run-1",
        scope: "primary" as const,
        budget_scope: "run" as const,
        code: "model_call_limit_reached" as const,
        limit: 10,
        used: 10,
        remaining: 0,
        unit: "model_calls" as const,
      };

      const vm = deriveBudgetViewModel(notice, null);
      expect(vm).not.toBeNull();
      expect(vm?.level).toBe("error");
      expect(vm?.isTerminal).toBe(true);
      expect(vm?.title).toBe("本次执行因额度限制停止");
      expect(vm?.actionType).toBe("adjust_draft");
      expect(vm?.actionLabel).toBe("调整请求");
    });

    it("supports end marker on native success (H04 scenario)", () => {
      const notice = {
        version: 1 as const,
        type: "runtime_budget_notice" as const,
        notice_id: "budget:3",
        run_id: "run-1",
        scope: "primary" as const,
        budget_scope: "run" as const,
        code: "model_call_limit_reached" as const,
        limit: 10,
        used: 10,
        remaining: 0,
        unit: "model_calls" as const,
      };

      const vm = deriveBudgetViewModel(notice, null, "success");
      expect(vm).not.toBeNull();
      expect(vm?.isTerminal).toBe(true);
      expect(vm?.title).toBe("本次执行因额度限制停止");
    });

    it("suppresses approaching notice when run completed with native success", () => {
      const notice = {
        version: 1 as const,
        type: "runtime_budget_notice" as const,
        notice_id: "budget:4",
        run_id: "run-1",
        scope: "primary" as const,
        budget_scope: "run" as const,
        code: "model_call_limit_approaching" as const,
        limit: 10,
        used: 7,
        remaining: 3,
        unit: "model_calls" as const,
      };

      const vm = deriveBudgetViewModel(notice, null, "success");
      expect(vm).toBeNull();
    });

    it("shows warning for wrapup_started during execution without copy repeating", () => {
      const notice = {
        version: 1 as const,
        type: "runtime_budget_notice" as const,
        notice_id: "budget:5",
        run_id: "run-1",
        scope: "primary" as const,
        budget_scope: "run" as const,
        code: "wrapup_started" as const,
        limit: 600,
        used: 603.5,
        remaining: null,
        unit: "seconds" as const,
      };

      const vm = deriveBudgetViewModel(notice, null, "running");
      expect(vm).not.toBeNull();
      expect(vm?.level).toBe("warning");
      expect(vm?.isTerminal).toBe(false);
      expect(vm?.title).toBe("运行时间较长");
      expect(vm?.description).toBe("正在收尾");
      expect(vm?.actionType).toBe("none");
    });

    it("derives safety error codes correctly and demotes unknown scope for model limit", () => {
      // 1. Model limit safety error without notice -> scope unknown, action none
      const vmModel = deriveBudgetViewModel(null, {
        code: "runtime_model_call_limit_reached",
        type: "ModelCallLimitExceededError",
      });
      expect(vmModel?.title).toBe("本次执行因额度限制停止");
      expect(vmModel?.scope).toBe("unknown");
      expect(vmModel?.actionType).toBe("none");

      // 2. Graph step limit safety error -> scope graph, action adjust_draft
      const vmGraph = deriveBudgetViewModel(null, {
        code: "runtime_graph_step_limit_reached",
        type: "GraphRecursionError",
      });
      expect(vmGraph?.title).toBe("本次执行达到图步骤上限");
      expect(vmGraph?.scope).toBe("graph");
      expect(vmGraph?.actionType).toBe("adjust_draft");

      // 3. Timeout safety error -> action none (not retry automatically)
      const vmTimeout = deriveBudgetViewModel(null, {
        code: "runtime_run_timeout",
      });
      expect(vmTimeout?.title).toBe("本次执行已超时");
      expect(vmTimeout?.scope).toBe("run");
      expect(vmTimeout?.actionType).toBe("none");
    });

    it("extracts notice from outer transport wrapper", () => {
      const wrapped = {
        event: "custom",
        id: "123",
        payload: {
          version: 1,
          type: "runtime_budget_notice",
          notice_id: "budget:wrapped-1",
          run_id: "run-wrapped",
          scope: "primary",
          budget_scope: "run",
          code: "model_call_limit_approaching",
          limit: 10,
          used: 8,
          remaining: 2,
          unit: "model_calls",
        },
      };

      const notice = safeExtractBudgetNotice(wrapped);
      expect(notice).not.toBeNull();
      expect(notice?.notice_id).toBe("budget:wrapped-1");
      expect(notice?.remaining).toBe(2);
    });
  });
});

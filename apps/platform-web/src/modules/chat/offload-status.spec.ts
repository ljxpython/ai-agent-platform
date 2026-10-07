import { describe, expect, it } from "vitest";
import {
  parseOffloadCustomEvent,
  parseOffloadPersistedState,
  toOffloadDisplayState,
  type ConversationOffloadEventData,
} from "./offload-status";

describe("offload-status module", () => {
  describe("parseOffloadCustomEvent", () => {
    it("parses valid root namespace custom offloading event", () => {
      const rawEvent = {
        method: "custom",
        params: {
          namespace: [],
          data: {
            type: "conversation_offloading",
            status: "started",
            trigger: "manual",
            operation_id: "op-123",
            run_id: "run-456",
          },
        },
      };

      const result = parseOffloadCustomEvent(rawEvent);
      expect(result).toEqual({
        type: "conversation_offloading",
        status: "started",
        trigger: "manual",
        operation_id: "op-123",
        run_id: "run-456",
        history_saved: undefined,
        reason_code: undefined,
      });
    });

    it("parses completed event with history_saved flag", () => {
      const rawEvent = {
        method: "custom",
        params: {
          namespace: [],
          data: {
            type: "conversation_offloading",
            status: "completed",
            trigger: "automatic",
            operation_id: "op-123",
            run_id: "run-456",
            history_saved: true,
          },
        },
      };

      const result = parseOffloadCustomEvent(rawEvent);
      expect(result).not.toBeNull();
      expect(result?.status).toBe("completed");
      expect(result?.history_saved).toBe(true);
    });

    it("ignores events from child subagents (non-empty namespace)", () => {
      const rawEvent = {
        method: "custom",
        params: {
          namespace: ["subagent_1"],
          data: {
            type: "conversation_offloading",
            status: "started",
          },
        },
      };

      expect(parseOffloadCustomEvent(rawEvent)).toBeNull();
    });

    it("ignores non-custom events or events without offload data", () => {
      expect(parseOffloadCustomEvent(null)).toBeNull();
      expect(parseOffloadCustomEvent(undefined)).toBeNull();
      expect(parseOffloadCustomEvent({ method: "values" })).toBeNull();
      expect(
        parseOffloadCustomEvent({
          method: "custom",
          params: { namespace: [], data: { type: "other_event" } },
        }),
      ).toBeNull();
    });

    it("ignores events with invalid status", () => {
      const rawEvent = {
        method: "custom",
        params: {
          namespace: [],
          data: {
            type: "conversation_offloading",
            status: "unknown_status",
          },
        },
      };

      expect(parseOffloadCustomEvent(rawEvent)).toBeNull();
    });
  });

  describe("toOffloadDisplayState", () => {
    it("maps started status to spinning info variant", () => {
      const data: ConversationOffloadEventData = {
        type: "conversation_offloading",
        status: "started",
        trigger: "manual",
        operation_id: "op-1",
        run_id: "run-1",
      };

      const display = toOffloadDisplayState(data);
      expect(display.status).toBe("started");
      expect(display.text).toBe("正在整理上下文...");
      expect(display.icon).toBe("refresh");
      expect(display.variant).toBe("info");
      expect(display.operationId).toBe("op-1");
      expect(display.runId).toBe("run-1");
    });

    it("maps completed status to success checkmark variant", () => {
      const data: ConversationOffloadEventData = {
        type: "conversation_offloading",
        status: "completed",
        trigger: "automatic",
      };

      const display = toOffloadDisplayState(data);
      expect(display.status).toBe("completed");
      expect(display.text).toBe("上下文已整理");
      expect(display.icon).toBe("check");
      expect(display.variant).toBe("success");
    });

    it("maps skipped status to neutral info variant", () => {
      const data: ConversationOffloadEventData = {
        type: "conversation_offloading",
        status: "skipped",
      };

      const display = toOffloadDisplayState(data);
      expect(display.status).toBe("skipped");
      expect(display.text).toBe("暂无需要整理的历史");
      expect(display.icon).toBe("info");
      expect(display.variant).toBe("neutral");
    });

    it("maps failed status to danger alert variant", () => {
      const data: ConversationOffloadEventData = {
        type: "conversation_offloading",
        status: "failed",
        reason_code: "summary_timeout",
      };

      const display = toOffloadDisplayState(data);
      expect(display.status).toBe("failed");
      expect(display.text).toBe("上下文整理失败");
      expect(display.icon).toBe("alert");
      expect(display.variant).toBe("danger");
    });
  });

  describe("parseOffloadPersistedState", () => {
    it("extracts valid persisted state from state values", () => {
      const values = {
        messages: [],
        conversation_offloading: {
          type: "conversation_offloading",
          status: "completed",
          trigger: "automatic",
          history_saved: true,
        },
      };

      const persisted = parseOffloadPersistedState(values);
      expect(persisted).not.toBeNull();
      expect(persisted?.status).toBe("completed");
      expect(persisted?.history_saved).toBe(true);
    });

    it("returns null when no offload state exists", () => {
      expect(parseOffloadPersistedState({})).toBeNull();
      expect(parseOffloadPersistedState({ messages: [] })).toBeNull();
      expect(parseOffloadPersistedState(null)).toBeNull();
    });
  });
});

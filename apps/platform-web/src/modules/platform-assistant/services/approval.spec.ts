import { describe, expect, it } from "vitest";
import {
  DEFAULT_REJECT_MESSAGE,
  buildAssistantReviewCommand,
  parseAssistantReviews,
} from "./approval";

describe("platform-assistant approval service", () => {
  describe("parseAssistantReviews", () => {
    it("正确解析标准的 HITL interrupt 结构", () => {
      const mockInterrupts = [
        {
          id: "int-12345",
          value: {
            action_requests: [
              {
                name: "test_write",
                args: { table: "orders", id: 42 },
                description: "此操作将修改业务数据。",
              },
            ],
            review_configs: [
              {
                action_name: "test_write",
                allowed_decisions: ["approve", "reject"],
              },
            ],
          },
        },
      ];

      const result = parseAssistantReviews(mockInterrupts);
      expect(result).toHaveLength(1);
      expect(result[0].interrupt_id).toBe("int-12345");
      expect(result[0].actions).toHaveLength(1);
      expect(result[0].actions[0].name).toBe("test_write");
      expect(result[0].actions[0].args).toEqual({ table: "orders", id: 42 });
      expect(result[0].actions[0].allowed_decisions).toEqual([
        "approve",
        "reject",
      ]);
    });

    it("当 action_requests 为空或缺少 id 时安全忽略", () => {
      const emptyInterrupts = [
        { id: "", value: {} },
        { id: "int-empty", value: { action_requests: [] } },
      ];
      const result = parseAssistantReviews(emptyInterrupts);
      expect(result).toHaveLength(0);
    });
  });

  describe("buildAssistantReviewCommand", () => {
    it("构建 approve 审批恢复报文", () => {
      const cmd = buildAssistantReviewCommand("int-999", "approve");
      expect(cmd).toEqual({
        assistant_id: "platform_assistant",
        command: {
          resume: {
            "int-999": {
              decisions: [{ type: "approve" }],
            },
          },
        },
      });
    });

    it("构建 reject 审批恢复报文时自动使用默认文案，免去手写输入", () => {
      const cmd = buildAssistantReviewCommand("int-999", "reject");
      expect(cmd).toEqual({
        assistant_id: "platform_assistant",
        command: {
          resume: {
            "int-999": {
              decisions: [
                {
                  type: "reject",
                  message: DEFAULT_REJECT_MESSAGE,
                },
              ],
            },
          },
        },
      });
      expect(cmd.command.resume["int-999"].decisions[0].message).toBe(
        "用户选择不执行",
      );
    });

    it("支持自定义拒绝理由覆盖默认文案", () => {
      const cmd = buildAssistantReviewCommand(
        "int-999",
        "reject",
        "参数有误，需要重新核算",
      );
      expect(cmd.command.resume["int-999"].decisions[0].message).toBe(
        "参数有误，需要重新核算",
      );
    });

    it("当缺少 interruptId 时抛出清晰错误", () => {
      expect(() => buildAssistantReviewCommand("", "approve")).toThrow(
        "缺少有效的审批 interrupt_id",
      );
    });
  });
});

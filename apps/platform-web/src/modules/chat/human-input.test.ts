import { describe, expect, it } from "vitest";
import {
  buildClarificationResponse,
  isClarificationInterrupt,
  parseClarifications,
  validateClarificationValues,
} from "./human-input";

describe("chat/human-input", () => {
  it("correctly identifies clarification interrupts", () => {
    // 场景 1: 用户实际报错的 Agent 提问多选
    const questionsInterrupt = {
      questions: [
        {
          is_multi_select: true,
          options: ["nfr (非功能性需求)", "document (完整设计文档)"],
          question: "还有哪些其他内容需要我补充？",
        },
      ],
    };
    expect(isClarificationInterrupt(questionsInterrupt)).toBe(true);

    // 场景 2: 标准 DearFlow clarification
    const dearflowInterrupt = {
      kind: "clarification",
      question: "请选择模型",
      fields: [{ name: "model", type: "select", options: ["v3", "v4"] }],
    };
    expect(isClarificationInterrupt(dearflowInterrupt)).toBe(true);

    // 场景 3: 顶层单问答带 options
    const singleQuestionInterrupt = {
      question: "请选择环境",
      options: ["staging", "prod"],
    };
    expect(isClarificationInterrupt(singleQuestionInterrupt)).toBe(true);

    // 场景 4: 工具审批中断（绝不能误判为澄清）
    const toolApprovalInterrupt = {
      action_requests: [{ name: "execute", args: { command: "ls" } }],
      review_configs: [{ action_name: "execute", allowed_decisions: ["approve"] }],
    };
    expect(isClarificationInterrupt(toolApprovalInterrupt)).toBe(false);
  });

  it("parses questions array interrupt into valid PendingClarification", () => {
    const rawValue = {
      questions: [
        {
          is_multi_select: true,
          options: ["nfr (非功能性需求)", "document (完整设计文档)"],
          question: "还有哪些其他内容需要我补充？",
        },
      ],
    };

    const parsed = parseClarifications([{ id: "intr-1", value: rawValue }]);
    expect(parsed).toHaveLength(1);
    expect(parsed[0].supported).toBe(true);
    expect(parsed[0].request.question).toBe("还有哪些其他内容需要我补充？");
    expect(parsed[0].request.fields).toHaveLength(1);

    const field = parsed[0].request.fields[0];
    expect(field.type).toBe("multi_select");
    expect(field.options).toEqual([
      { label: "nfr (非功能性需求)", value: "nfr (非功能性需求)" },
      { label: "document (完整设计文档)", value: "document (完整设计文档)" },
    ]);
  });

  it("validates multi_select values properly", () => {
    const fields = [
      {
        name: "selection",
        type: "multi_select",
        label: "测试多选",
        required: true,
        options: [
          { label: "A", value: "A" },
          { label: "B", value: "B" },
        ],
      },
    ];

    // 空值校验失败
    const err1 = validateClarificationValues(fields as any, { selection: [] });
    expect(err1.selection).toBeTruthy();

    // 包含有效值校验通过
    const err2 = validateClarificationValues(fields as any, { selection: ["A"] });
    expect(Object.keys(err2)).toHaveLength(0);
  });

  it("builds correct resume response for questions interrupt", () => {
    const rawValue = {
      questions: [
        {
          is_multi_select: true,
          options: ["A", "B"],
          question: "选择",
        },
      ],
    };

    const resp = buildClarificationResponse(
      "intr-1",
      { selection: ["A"] },
      1,
      rawValue,
    );

    expect(resp["intr-1"]).toBeDefined();
    const payload = resp["intr-1"] as any;
    expect(payload.values).toEqual({ selection: ["A"] });
    expect(payload.answers).toEqual([["A"]]);
    expect(payload.answer).toEqual(["A"]);
  });
});

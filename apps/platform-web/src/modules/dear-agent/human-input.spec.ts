import { describe, expect, it } from "vitest";
import {
  buildClarificationResponse,
  isClarificationInterrupt,
  parseClarifications,
  validateClarificationValues,
  type ClarificationField,
} from "./human-input";

describe("human-input", () => {
  it("recognizes clarification interrupts correctly", () => {
    expect(isClarificationInterrupt(null)).toBe(false);
    expect(isClarificationInterrupt({ kind: "clarification" })).toBe(true);
    expect(
      isClarificationInterrupt({
        question: "请确认周期",
        fields: [{ name: "period", type: "select" }],
      }),
    ).toBe(true);
    expect(isClarificationInterrupt({ action_requests: [] })).toBe(false);
  });

  it("parses clarification interrupts into structured pending clarification items", () => {
    const rawInterrupts = [
      {
        id: "intr-1",
        ns: ["sub-1"],
        value: {
          kind: "clarification",
          question: "请选择分析周期和关注指标",
          context: "这是背景信息",
          fields: [
            {
              name: "period",
              type: "select",
              label: "周期",
              required: true,
              options: [
                { label: "按天", value: "daily" },
                { label: "按月", value: "monthly" },
              ],
            },
            {
              name: "note",
              type: "text",
              label: "备注",
              required: false,
              placeholder: "请输入额外说明",
            },
          ],
        },
      },
      {
        id: "intr-invalid",
        value: {
          action_requests: [{ name: "bash", args: {} }],
        },
      },
    ];

    const parsed = parseClarifications(rawInterrupts);
    expect(parsed).toHaveLength(1);
    expect(parsed[0].id).toBe("intr-1");
    expect(parsed[0].request.question).toBe("请选择分析周期和关注指标");
    expect(parsed[0].request.context).toBe("这是背景信息");
    expect(parsed[0].request.fields).toHaveLength(2);
    expect(parsed[0].supported).toBe(true);
  });

  it("validates required fields and select options", () => {
    const fields: ClarificationField[] = [
      {
        name: "period",
        type: "select",
        label: "周期",
        required: true,
        options: [
          { label: "按天", value: "daily" },
          { label: "按月", value: "monthly" },
        ],
      },
      {
        name: "keyword",
        type: "text",
        label: "关键字",
        required: true,
      },
    ];

    // Missing all required
    const err1 = validateClarificationValues(fields, {});
    expect(err1.period).toBe("请填写周期");
    expect(err1.keyword).toBe("请填写关键字");

    // Invalid select option
    const err2 = validateClarificationValues(fields, {
      period: "yearly",
      keyword: "AI",
    });
    expect(err2.period).toBe("请选择有效的选项");
    expect(err2.keyword).toBeUndefined();

    // Valid values
    const err3 = validateClarificationValues(fields, {
      period: "daily",
      keyword: "Agent",
    });
    expect(Object.keys(err3)).toHaveLength(0);
  });

  it("builds clarification response conforming to contract", () => {
    const resp = buildClarificationResponse("intr-123", {
      period: "monthly",
      note: "季度汇总",
    });

    expect(resp).toEqual({
      "intr-123": {
        schema_version: 1,
        status: "answered",
        values: {
          period: "monthly",
          note: "季度汇总",
        },
      },
    });
  });
});

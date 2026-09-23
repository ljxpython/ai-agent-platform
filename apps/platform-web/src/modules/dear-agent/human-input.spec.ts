import { describe, expect, it } from "vitest";
import {
  buildClarificationResponse,
  filterActiveClarifications,
  isClarificationActive,
  isClarificationInterrupt,
  normalizeClarificationValues,
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

  it("validates all 7 clarification field types including checkbox false and date format", () => {
    const fields: ClarificationField[] = [
      { name: "name", type: "text", label: "姓名", required: true },
      { name: "requirement", type: "textarea", label: "需求", required: true },
      { name: "budget", type: "number", label: "预算", required: true },
      {
        name: "level",
        type: "select",
        label: "级别",
        required: true,
        options: [
          { label: "基础", value: "basic" },
          { label: "高级", value: "advanced" },
        ],
      },
      {
        name: "channels",
        type: "multi_select",
        label: "渠道",
        required: true,
        options: [
          { label: "网页", value: "web" },
          { label: "邮件", value: "email" },
        ],
      },
      { name: "notify", type: "checkbox", label: "通知", required: true },
      { name: "delivery_date", type: "date", label: "交付日期", required: true },
    ];

    // Missing all required
    const errEmpty = validateClarificationValues(fields, {});
    expect(errEmpty.name).toBe("请填写姓名");
    expect(errEmpty.requirement).toBe("请填写需求");
    expect(errEmpty.budget).toBe("请填写有效的预算数值");
    expect(errEmpty.level).toBe("请填写级别");
    expect(errEmpty.channels).toBe("请选择渠道");
    expect(errEmpty.notify).toBe("请确认通知");
    expect(errEmpty.delivery_date).toBe("请填写交付日期");

    // Invalid format cases
    const errInvalid = validateClarificationValues(fields, {
      name: "张三",
      requirement: "系统开发",
      budget: "not-a-number",
      level: "invalid-level",
      channels: ["invalid-channel"],
      notify: "yes", // should be boolean
      delivery_date: "2026/09/16", // invalid date format
    });
    expect(errInvalid.budget).toBe("请填写有效的预算数值");
    expect(errInvalid.level).toBe("请选择有效的选项");
    expect(errInvalid.channels).toBe("存在无效的选项");
    expect(errInvalid.notify).toBe("请确认通知");
    expect(errInvalid.delivery_date).toBe("请输入有效的日期格式 (YYYY-MM-DD)");

    // Valid values (critical: notify=false is valid!)
    const validRaw = {
      name: "李四",
      requirement: "重构模块",
      budget: 120,
      level: "basic",
      channels: ["web"],
      notify: false,
      delivery_date: "2026-09-16",
    };
    const errValid = validateClarificationValues(fields, validRaw);
    expect(Object.keys(errValid)).toHaveLength(0);

    // Normalize values
    const normalized = normalizeClarificationValues(fields, {
      ...validRaw,
      budget: "120",
    });
    expect(normalized.budget).toBe(120);
    expect(normalized.notify).toBe(false);
    expect(normalized.channels).toEqual(["web"]);
    expect(normalized.delivery_date).toBe("2026-09-16");
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

  describe("filterActiveClarifications & isClarificationActive", () => {
    const mockClarification = {
      id: "call_req_1",
      namespace: [],
      supported: true,
      raw: {},
      request: {
        question: "请提供现场信息",
        fields: [{ name: "error", type: "text", label: "错误" }],
        schema_version: 1,
      },
    };

    it("filters out clarification when resolvedIds contains it", () => {
      const resolved = new Set(["call_req_1"]);
      expect(isClarificationActive(mockClarification, [], resolved)).toBe(false);
      expect(filterActiveClarifications([mockClarification], [], resolved)).toHaveLength(0);
    });

    it("keeps clarification when it is pending in current turn without tool output", () => {
      const messages = [
        { type: "human", content: "帮我定位错误" },
        {
          type: "ai",
          content: "",
          tool_calls: [
            {
              id: "call_req_1",
              name: "request_information",
              args: { question: "请提供现场信息" },
            },
          ],
        },
      ];
      expect(isClarificationActive(mockClarification, messages)).toBe(true);
      expect(filterActiveClarifications([mockClarification], messages)).toHaveLength(1);
    });

    it("filters out clarification when matching request_information already has tool output", () => {
      const messages = [
        { type: "human", content: "帮我定位错误" },
        {
          type: "ai",
          content: "",
          tool_calls: [
            {
              id: "call_req_1",
              name: "request_information",
              args: { question: "请提供现场信息" },
            },
          ],
        },
        {
          type: "tool",
          name: "request_information",
          tool_call_id: "call_req_1",
          content: JSON.stringify({ status: "answered", values: { error: "NullPointerException" } }),
        },
        {
          type: "ai",
          content: "收到错误日志，正在为您生成补丁...",
        },
      ];
      expect(isClarificationActive(mockClarification, messages)).toBe(false);
      expect(filterActiveClarifications([mockClarification], messages)).toHaveLength(0);
    });

    it("filters out historical clarification when a subsequent user message has advanced the turn", () => {
      const messages = [
        { type: "human", content: "帮我定位错误" },
        {
          type: "ai",
          content: "",
          tool_calls: [
            {
              id: "call_req_1",
              name: "request_information",
              args: { question: "请提供现场信息" },
            },
          ],
        },
        {
          type: "human",
          content: "算了，不要排查这个了，帮我写个新脚本",
        },
      ];
      expect(isClarificationActive(mockClarification, messages)).toBe(false);
      expect(filterActiveClarifications([mockClarification], messages)).toHaveLength(0);
    });
  });
});

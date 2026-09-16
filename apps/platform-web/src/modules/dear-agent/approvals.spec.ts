import { describe, expect, it } from "vitest";
import { buildReviewResponses, parseReviews } from "./approvals";

describe("dear-agent approvals", () => {
  const sampleValue = {
    action_requests: [
      { name: "edit_file", args: { path: "/work/test.ts", count: 2, enabled: false } },
    ],
    review_configs: [
      {
        action_name: "edit_file",
        allowed_decisions: ["approve", "reject", "edit"],
      },
    ],
  };

  it("parses valid action requests into PendingReview", () => {
    const reviews = parseReviews([
      { id: "rev-1", value: sampleValue, ns: ["dearflow", "main"] },
    ]);

    expect(reviews).toHaveLength(1);
    expect(reviews[0].id).toBe("rev-1");
    expect(reviews[0].namespace).toEqual(["dearflow", "main"]);
    expect(reviews[0].supported).toBe(true);
    expect(reviews[0].actions).toHaveLength(1);
    expect(reviews[0].actions[0].name).toBe("edit_file");
    expect(reviews[0].actions[0].allowed).toEqual(["approve", "reject", "edit"]);
  });

  it("filters out clarification interrupts so they do not show up as tool reviews", () => {
    const clarificationValue = {
      type: "clarification",
      title: "请选择运行模式",
      questions: [{ question: "Mode?", type: "select", options: ["a", "b"] }],
    };
    const reviews = parseReviews([
      { id: "clarify-1", value: clarificationValue },
      { id: "rev-1", value: sampleValue },
    ]);

    expect(reviews).toHaveLength(1);
    expect(reviews[0].id).toBe("rev-1");
  });

  it("handles approve decision correctly", () => {
    const reviews = parseReviews([{ id: "rev-1", value: sampleValue }]);
    const responses = buildReviewResponses(reviews, {
      "rev-1": [{ type: "approve" }],
    });

    expect(responses["rev-1"].decisions).toEqual([{ type: "approve" }]);
  });

  it("handles reject decision with message validation", () => {
    const reviews = parseReviews([{ id: "rev-1", value: sampleValue }]);
    const responses = buildReviewResponses(reviews, {
      "rev-1": [{ type: "reject", message: "不允许修改系统文件" }],
    });

    expect(responses["rev-1"].decisions).toEqual([
      { type: "reject", message: "不允许修改系统文件" },
    ]);

    // Empty reject message should throw
    expect(() =>
      buildReviewResponses(reviews, {
        "rev-1": [{ type: "reject", message: "   " }],
      }),
    ).toThrow("拒绝原因须为 1–2000 个字符");
  });

  it("handles edit decision with strict argument validation", () => {
    const reviews = parseReviews([{ id: "rev-1", value: sampleValue }]);
    const validEditedArgs = JSON.stringify({
      path: "/work/modified.ts",
      count: 10,
      enabled: true,
    });

    const responses = buildReviewResponses(reviews, {
      "rev-1": [{ type: "edit", args: validEditedArgs }],
    });

    expect(responses["rev-1"].decisions).toEqual([
      {
        type: "edit",
        edited_action: {
          name: "edit_file",
          args: { path: "/work/modified.ts", count: 10, enabled: true },
        },
      },
    ]);

    // Invalid JSON
    expect(() =>
      buildReviewResponses(reviews, {
        "rev-1": [{ type: "edit", args: "{invalid json}" }],
      }),
    ).toThrow("编辑参数必须为有效 JSON");

    // Type change (number to string)
    expect(() =>
      buildReviewResponses(reviews, {
        "rev-1": [
          {
            type: "edit",
            args: JSON.stringify({
              path: "/work/test.ts",
              count: "10",
              enabled: false,
            }),
          },
        ],
      }),
    ).toThrow("不能改变参数类型");

    // Extra injected keys
    expect(() =>
      buildReviewResponses(reviews, {
        "rev-1": [
          {
            type: "edit",
            args: JSON.stringify({
              path: "/work/test.ts",
              count: 10,
              enabled: false,
              injected: "danger",
            }),
          },
        ],
      }),
    ).toThrow("只能修改原有参数，不能增删参数或注入配置");
  });
});

import { describe, expect, it } from "vitest";
import {
  isPlanReviewInterrupt,
  parsePlanReview,
  buildPlanResponse,
  extractAgentPlan,
  type PendingPlanReview,
} from "./plan-review";
import { renderMarkdown } from "@/utils/markdown";

describe("plan-review module", () => {
  const validInterrupt = {
    id: "interrupt-plan-001",
    ns: [],
    value: {
      type: "agent_plan_review",
      version: 1,
      plan_id: "plan-uuid-1234",
      revision: 1,
      content_hash:
        "sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
      title: "核心重构计划",
      markdown:
        "## 步骤 1\n全面重构后端架构。\n\n## 步骤 2\n编写高覆盖率单测。",
      allowed_decisions: ["approve", "request_changes", "abandon"],
    },
  };

  it("isPlanReviewInterrupt accurately identifies native agent_plan_review interrupts", () => {
    // 兼容外层包装中断与内层 value
    expect(isPlanReviewInterrupt(validInterrupt)).toBe(true);
    expect(isPlanReviewInterrupt(validInterrupt.value)).toBe(true);

    // 非对象或空
    expect(isPlanReviewInterrupt(null)).toBe(false);
    expect(isPlanReviewInterrupt(undefined)).toBe(false);
    expect(isPlanReviewInterrupt("string")).toBe(false);

    // 普通工具审批
    expect(
      isPlanReviewInterrupt({
        id: "tool-int",
        value: {
          action_requests: [{ name: "edit_file", args: {} }],
        },
      }),
    ).toBe(false);

    // type 不对或 version 不对
    expect(
      isPlanReviewInterrupt({
        id: "err-type",
        value: { ...validInterrupt.value, type: "other_review" },
      }),
    ).toBe(false);
    expect(
      isPlanReviewInterrupt({
        id: "err-version",
        value: { ...validInterrupt.value, version: 2 },
      }),
    ).toBe(false);
  });

  it("parsePlanReview correctly parses interrupt fields", () => {
    const parsed = parsePlanReview(validInterrupt);
    expect(parsed).not.toBeNull();
    expect(parsed?.id).toBe("interrupt-plan-001");
    expect(parsed?.planId).toBe("plan-uuid-1234");
    expect(parsed?.revision).toBe(1);
    expect(parsed?.contentHash).toBe(validInterrupt.value.content_hash);
    expect(parsed?.title).toBe("核心重构计划");
    expect(parsed?.markdown).toContain("全面重构后端架构");
    expect(parsed?.allowedDecisions).toEqual([
      "approve",
      "request_changes",
      "abandon",
    ]);
  });

  it("parsePlanReview handles up to 64 KiB markdown content and rejects exceeding size", () => {
    const exactLargeMarkdown = "a".repeat(64 * 1024);
    const validLargeInterrupt = {
      id: "interrupt-large",
      value: {
        ...validInterrupt.value,
        markdown: exactLargeMarkdown,
      },
    };
    const parsed = parsePlanReview(validLargeInterrupt);
    expect(parsed?.markdown.length).toBe(64 * 1024);

    const overflowInterrupt = {
      id: "interrupt-overflow",
      value: {
        ...validInterrupt.value,
        markdown: "a".repeat(64 * 1024 + 1),
      },
    };
    expect(parsePlanReview(overflowInterrupt)).toBeNull();
  });

  it("buildPlanResponse constructs valid responses and enforces validation", () => {
    const review: PendingPlanReview = {
      id: "int-1",
      namespace: [],
      planId: "p-1",
      revision: 2,
      contentHash: "sha256:abc",
      title: "测试计划",
      markdown: "正文",
      allowedDecisions: ["approve", "request_changes", "abandon"],
      plan: {
        type: "agent_plan_review",
        version: 1,
        plan_id: "p-1",
        revision: 2,
        content_hash: "sha256:abc",
        title: "测试计划",
        markdown: "正文",
        allowed_decisions: ["approve", "request_changes", "abandon"],
      },
      fingerprint: "{}",
      supported: true,
      raw: {},
    };

    // approve
    expect(buildPlanResponse(review, "approve")).toEqual({
      "int-1": {
        version: 1,
        type: "agent_plan_response",
        plan_id: "p-1",
        revision: 2,
        content_hash: "sha256:abc",
        decision: "approve",
      },
    });

    // abandon
    expect(buildPlanResponse(review, "abandon")).toEqual({
      "int-1": {
        version: 1,
        type: "agent_plan_response",
        plan_id: "p-1",
        revision: 2,
        content_hash: "sha256:abc",
        decision: "abandon",
      },
    });

    // request_changes with feedback
    expect(
      buildPlanResponse(
        review,
        "request_changes",
        "请修改测试步骤并补充回滚方案",
      ),
    ).toEqual({
      "int-1": {
        version: 1,
        type: "agent_plan_response",
        plan_id: "p-1",
        revision: 2,
        content_hash: "sha256:abc",
        decision: "request_changes",
        feedback: "请修改测试步骤并补充回滚方案",
      },
    });

    // request_changes 缺少 feedback 或反馈为空时必须抛出异常
    expect(() => buildPlanResponse(review, "request_changes")).toThrow(
      "必须提供具体修改意见",
    );
    expect(() => buildPlanResponse(review, "request_changes", "   ")).toThrow(
      "必须提供具体修改意见",
    );

    // request_changes 反馈超长 (>2000) 必须抛出异常
    const tooLongFeedback = "x".repeat(2001);
    expect(() =>
      buildPlanResponse(review, "request_changes", tooLongFeedback),
    ).toThrow("不能超过 2000 个字符");

    // 不在 allowed_decisions 中的操作必须抛出异常
    const restrictedReview: PendingPlanReview = {
      ...review,
      allowedDecisions: ["approve"],
    };
    expect(() =>
      buildPlanResponse(restrictedReview, "request_changes", "意见"),
    ).toThrow("不允许的操作决定");
  });

  it("extractAgentPlan extracts snapshot from state values safely", () => {
    const snapshot = {
      plan_id: "p-100",
      revision: 3,
      status: "awaiting_review",
      title: "待审计划",
      markdown: "正文内容",
    };

    const extracted = extractAgentPlan({ agent_plan: snapshot });
    expect(extracted?.plan_id).toBe("p-100");
    expect(extracted?.revision).toBe(3);
    expect(extracted?.status).toBe("awaiting_review");
    expect(extracted?.title).toBe("待审计划");
    expect(extracted?.markdown).toBe("正文内容");

    expect(extractAgentPlan({})).toBeNull();
    expect(extractAgentPlan(null)).toBeNull();
    expect(extractAgentPlan({ agent_plan: "invalid" })).toBeNull();
  });
});

describe("markdown XSS sanitization", () => {
  it("sanitizes dangerous pseudo-protocols like javascript: and data:", () => {
    const xssSource = "[恶意链接](javascript:alert(1))";
    const rendered = renderMarkdown(xssSource);
    expect(rendered).not.toContain("javascript:alert(1)");
    expect(rendered).toContain('href="#"');

    const dataXss =
      "[数据链接](data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==)";
    const renderedData = renderMarkdown(dataXss);
    expect(renderedData).not.toContain("data:text/html");
  });

  it("preserves safe http, https, and mailto links with secure attributes", () => {
    const safeSource = "[官方文档](https://example.com/docs)";
    const rendered = renderMarkdown(safeSource);
    expect(rendered).toContain('href="https://example.com/docs"');
    expect(rendered).toContain('target="_blank"');
    expect(rendered).toContain('rel="noreferrer noopener"');

    const mailtoSource = "[发送邮件](mailto:test@example.com)";
    const renderedMailto = renderMarkdown(mailtoSource);
    expect(renderedMailto).toContain('href="mailto:test@example.com"');
  });

  it("escapes raw html tags preventing arbitrary html and iframe injection", () => {
    const htmlSource =
      '<script>alert("xss")</script><iframe src="evil.com"></iframe>';
    const rendered = renderMarkdown(htmlSource);
    expect(rendered).not.toContain("<script>");
    expect(rendered).not.toContain("<iframe");
    expect(rendered).toContain("&lt;script&gt;");
  });
});

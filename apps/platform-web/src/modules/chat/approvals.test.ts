import { expect, it } from "vitest";
import { buildReviewResponses, parseReviews } from "./approvals";

const value = {
  action_requests: [
    { name: "edit_file", args: { path: "/work/a", count: 2, enabled: false } },
  ],
  review_configs: [
    {
      action_name: "edit_file",
      allowed_decisions: ["approve", "reject", "edit"],
    },
  ],
};

it("keeps parallel decisions bound to IDs after reordering and preserves edited types", () => {
  const reviews = parseReviews([
    { id: "B", value },
    { id: "A", value },
  ]);
  const responses = buildReviewResponses(reviews, {
    A: [{ type: "edit", args: '{"path":"/work/b","count":3,"enabled":true}' }],
    B: [{ type: "reject", message: "保留原文件" }],
  });
  expect(responses.B?.decisions).toEqual([
    { type: "reject", message: "保留原文件" },
  ]);
  expect(responses.A?.decisions).toEqual([
    {
      type: "edit",
      edited_action: {
        name: "edit_file",
        args: { path: "/work/b", count: 3, enabled: true },
      },
    },
  ]);
});

it("fails closed for unknown reviews, missing choices, changed types and extra config", () => {
  const reviews = parseReviews([{ id: "A", value }]);
  expect(() => buildReviewResponses(reviews, {})).toThrow();
  for (const args of [
    "not json",
    '{"path":"/work/a","count":"3","enabled":false}',
    '{"path":"/work/a","count":3,"enabled":false,"config":{}}',
  ]) {
    expect(() =>
      buildReviewResponses(reviews, { A: [{ type: "edit", args }] }),
    ).toThrow();
  }
  expect(
    parseReviews([{ id: "unknown", value: { question: "yes?" } }])[0]
      ?.supported,
  ).toBe(false);
});

it("compares review content independently of JSON object key order", () => {
  const reordered = {
    review_configs: value.review_configs,
    action_requests: [
      {
        args: { enabled: false, count: 2, path: "/work/a" },
        name: "edit_file",
      },
    ],
  };
  expect(parseReviews([{ id: "A", value }])[0]?.fingerprint).toBe(
    parseReviews([{ id: "A", value: reordered }])[0]?.fingerprint,
  );
});

it("ignores SDK aliases but detects actual action changes", () => {
  const enriched = {
    ...value,
    actionRequests: value.action_requests,
    reviewConfigs: value.review_configs,
    action_requests: value.action_requests.map((action) => ({
      ...action,
      action_name: action.name,
    })),
    review_configs: value.review_configs.map((config) => ({
      ...config,
      allowedDecisions: config.allowed_decisions,
    })),
  };
  const original = parseReviews([{ id: "A", value }])[0]?.fingerprint;
  expect(parseReviews([{ id: "A", value: enriched }])[0]?.fingerprint).toBe(
    original,
  );
  expect(
    parseReviews([
      {
        id: "A",
        value: {
          ...value,
          action_requests: [
            { name: "edit_file", args: { path: "/different" } },
          ],
        },
      },
    ])[0]?.fingerprint,
  ).not.toBe(original);
});

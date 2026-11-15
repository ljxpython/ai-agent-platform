import { describe, expect, it } from "vitest";
import type { Proposal } from "@/services/evaluation/workbench";
import { proposalDiff } from "./proposalDiff";

describe("proposal changes", () => {
  it("compares saved fields rather than trusting an AI change summary", () => {
    const before = {
      summary: "原方案",
      missing_information: [],
      excluded: [],
      cases: [{ case_id: "C1", expectations: { answer_contains: ["270"] } }],
    } as unknown as Proposal;
    const after = structuredClone(before);
    after.changes = ["没有变化"];
    after.cases[0]!.expectations.answer_contains = ["130"];
    expect(proposalDiff(before, after)).toEqual([
      {
        label: "C1 · 答案及文件标准",
        before: "answer_contains：270",
        after: "answer_contains：130",
      },
    ]);
    expect(proposalDiff(after, after)).toEqual([]);
  });
});

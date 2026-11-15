import type { Proposal } from "@/services/evaluation/workbench";

function describe(value: unknown): string {
  if (value == null) return "未设置";
  if (typeof value !== "object") return String(value);
  if (Array.isArray(value)) return value.map(describe).join("；") || "无";
  return (
    Object.entries(value)
      .map(([key, part]) => `${key}：${describe(part)}`)
      .join("；") || "无"
  );
}

export function proposalDiff(previous: Proposal, current: Proposal) {
  const changes: { label: string; before: string; after: string }[] = [];
  const add = (label: string, before: unknown, after: unknown) => {
    if (describe(before) !== describe(after))
      changes.push({ label, before: describe(before), after: describe(after) });
  };
  add("方案摘要", previous.summary, current.summary);
  add("整体缺口", previous.missing_information, current.missing_information);
  add(
    "按题缺口",
    previous.case_missing_information,
    current.case_missing_information,
  );
  add("不覆盖的情况", previous.excluded, current.excluded);
  for (const id of new Set(
    [...previous.cases, ...current.cases].map((c) => c.case_id),
  )) {
    const before = previous.cases.find((c) => c.case_id === id);
    const after = current.cases.find((c) => c.case_id === id);
    if (!before || !after) {
      add(
        `${id} · 用例`,
        before ? "包含此题" : "不包含",
        after ? "包含此题" : "不包含",
      );
      continue;
    }
    for (const [key, label] of Object.entries({
      turns: "提问与审批",
      business_rules: "业务口径",
      turn_expectations: "逐轮预期",
      expectations: "答案及文件标准",
      metrics: "检查项",
      fixture: "合成文件",
      rubric_version: "评分标准版本",
    })) {
      add(`${id} · ${label}`, before[key], after[key]);
    }
  }
  return changes;
}

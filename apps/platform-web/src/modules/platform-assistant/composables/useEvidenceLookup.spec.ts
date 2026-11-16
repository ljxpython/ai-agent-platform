import { describe, expect, it } from "vitest";
import { useEvidenceLookup } from "./useEvidenceLookup";

describe("useEvidenceLookup", () => {
  it("正常从合法 JSON ToolMessage 中提取 evidence_id 并建立索引", () => {
    const lookup = useEvidenceLookup();
    const mockToolContent = JSON.stringify({
      evidence_id: "550e8400-e29b-41d4-a716-446655440000",
      operation: "sql_query",
      observed_at: "2026-11-16T12:00:00Z",
      scope: { project_id: "proj-1" },
      audit_recorded: true,
      data: {
        rows: [{ total: 2 }],
        row_count: 1,
      },
    });

    const parsedId = lookup.parseAndIndexToolMessage(mockToolContent);
    expect(parsedId).toBe("550e8400-e29b-41d4-a716-446655440000");

    expect(
      lookup.evidenceMap.value.has("550e8400-e29b-41d4-a716-446655440000"),
    ).toBe(true);

    lookup.openEvidence("550e8400-e29b-41d4-a716-446655440000");
    expect(lookup.isEvidenceDrawerOpen.value).toBe(true);
    expect(lookup.activeEvidence.value?.operation).toBe("sql_query");
    expect(lookup.activeEvidence.value?.data?.row_count).toBe(1);
  });

  it("当查询未收录的 evidenceId 时展示未核实提示", () => {
    const lookup = useEvidenceLookup();
    lookup.openEvidence("unknown-id-8888");

    expect(lookup.isEvidenceDrawerOpen.value).toBe(true);
    expect(lookup.activeEvidence.value?.evidence_id).toBe("unknown-id-8888");
    expect(lookup.activeEvidence.value?.operation).toBe("unknown");
    expect(lookup.activeEvidence.value?.data?.error).toContain("引用未核实");
  });

  it("非 JSON 文本安全跳过，不崩溃", () => {
    const lookup = useEvidenceLookup();
    const result = lookup.parseAndIndexToolMessage("plain text error output");
    expect(result).toBeNull();
    expect(lookup.evidenceMap.value.size).toBe(0);
  });
});

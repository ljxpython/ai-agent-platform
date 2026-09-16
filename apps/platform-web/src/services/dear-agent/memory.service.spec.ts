import { describe, expect, it, vi, beforeEach } from "vitest";
import { platformHttpClient } from "@/services/http/client";
import {
  readMemory,
  saveMemoryFact,
  deleteMemoryFact,
  clearMemory,
  acceptMemoryCandidate,
  rejectMemoryCandidate,
  updateMemorySettings,
  restoreMemoryFacts,
} from "./memory.service";

vi.mock("@/services/http/client", () => ({
  platformHttpClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

describe("memory.service", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("readMemory 携带 query 与 header 发送请求", async () => {
    const mockData = {
      schema_version: 1,
      revision: 1,
      epoch: 0,
      automatic_candidates: false,
      facts: [],
      candidates: [],
    };
    (platformHttpClient.get as any).mockResolvedValueOnce({ data: mockData });

    const result = await readMemory("proj-1", "th-1", "偏好");
    expect(platformHttpClient.get).toHaveBeenCalledWith(
      "/api/langgraph/threads/th-1/dear/memory",
      {
        headers: { "x-project-id": "proj-1" },
        params: { query: "偏好" },
        signal: undefined,
      },
    );
    expect(result).toEqual(mockData);
  });

  it("saveMemoryFact 提交 action=save 并携带 expected_revision", async () => {
    (platformHttpClient.post as any).mockResolvedValueOnce({ data: { revision: 2 } });

    await saveMemoryFact("proj-1", "th-1", 1, { text: "新事实", category: "fact" }, "f-1");
    expect(platformHttpClient.post).toHaveBeenCalledWith(
      "/api/langgraph/threads/th-1/dear/memory",
      {
        action: "save",
        expected_revision: 1,
        fact: { text: "新事实", category: "fact" },
        fact_id: "f-1",
      },
      {
        headers: { "x-project-id": "proj-1" },
      },
    );
  });

  it("deleteMemoryFact 提交 action=delete", async () => {
    (platformHttpClient.post as any).mockResolvedValueOnce({ data: { revision: 2 } });

    await deleteMemoryFact("proj-1", "th-1", 1, "f-1");
    expect(platformHttpClient.post).toHaveBeenCalledWith(
      "/api/langgraph/threads/th-1/dear/memory",
      {
        action: "delete",
        expected_revision: 1,
        fact_id: "f-1",
      },
      {
        headers: { "x-project-id": "proj-1" },
      },
    );
  });

  it("clearMemory 提交 action=clear", async () => {
    (platformHttpClient.post as any).mockResolvedValueOnce({ data: { revision: 1 } });

    await clearMemory("proj-1", "th-1", 1);
    expect(platformHttpClient.post).toHaveBeenCalledWith(
      "/api/langgraph/threads/th-1/dear/memory",
      {
        action: "clear",
        expected_revision: 1,
      },
      {
        headers: { "x-project-id": "proj-1" },
      },
    );
  });

  it("acceptMemoryCandidate & rejectMemoryCandidate 提交正确指令", async () => {
    (platformHttpClient.post as any).mockResolvedValue({ data: { revision: 2 } });

    await acceptMemoryCandidate("proj-1", "th-1", 1, "c-1");
    expect(platformHttpClient.post).toHaveBeenLastCalledWith(
      "/api/langgraph/threads/th-1/dear/memory",
      {
        action: "accept",
        expected_revision: 1,
        fact_id: "c-1",
      },
      { headers: { "x-project-id": "proj-1" } },
    );

    await rejectMemoryCandidate("proj-1", "th-1", 2, "c-1");
    expect(platformHttpClient.post).toHaveBeenLastCalledWith(
      "/api/langgraph/threads/th-1/dear/memory",
      {
        action: "reject",
        expected_revision: 2,
        fact_id: "c-1",
      },
      { headers: { "x-project-id": "proj-1" } },
    );
  });

  it("updateMemorySettings 更新自动候选开关", async () => {
    (platformHttpClient.post as any).mockResolvedValueOnce({ data: { automatic_candidates: true } });

    await updateMemorySettings("proj-1", "th-1", 1, true);
    expect(platformHttpClient.post).toHaveBeenCalledWith(
      "/api/langgraph/threads/th-1/dear/memory",
      {
        action: "settings",
        expected_revision: 1,
        automatic_candidates: true,
      },
      { headers: { "x-project-id": "proj-1" } },
    );
  });

  it("restoreMemoryFacts 批量追加恢复事实", async () => {
    (platformHttpClient.post as any).mockResolvedValueOnce({ data: { revision: 3 } });

    const factsToRestore = [{ text: "偏好1", category: "preference" as const }];
    await restoreMemoryFacts("proj-1", "th-1", 2, factsToRestore);
    expect(platformHttpClient.post).toHaveBeenCalledWith(
      "/api/langgraph/threads/th-1/dear/memory",
      {
        action: "restore",
        expected_revision: 2,
        facts: factsToRestore,
      },
      { headers: { "x-project-id": "proj-1" } },
    );
  });
});

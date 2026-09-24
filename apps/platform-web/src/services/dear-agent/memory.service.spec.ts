import { describe, expect, it, vi, beforeEach } from "vitest";
import { platformHttpClient } from "@/services/http/client";
import { extractPlatformHttpError } from "@/utils/http-error";
import {
  readMemory,
  saveMemoryFact,
  deleteMemoryFact,
  clearMemory,
  acceptMemoryCandidate,
  rejectMemoryCandidate,
  updateMemorySettings,
  restoreMemoryFacts,
  type MemoryView,
} from "./memory.service";

vi.mock("@/services/http/client", () => ({
  platformHttpClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

function createMockMemoryView(overrides: Partial<MemoryView> = {}): MemoryView {
  return {
    status: "ready",
    scope: { kind: "project_user", project_id: "proj-1", user_id: "user-1" },
    capabilities: { memory_enabled: true, can_read: true, can_write: true },
    limits: {
      fact_text_chars: 1000,
      facts: 100,
      candidates: 100,
      restore_items: 100,
      request_bytes: 1500000,
    },
    document: {
      schema_version: 1,
      revision: 3,
      epoch: 1,
      automatic_candidates: false,
      facts: [],
      candidates: [],
    },
    counts: { facts: 0, candidates: 0 },
    extraction: {
      status: "never",
      updated_at: null,
      source_thread_id: null,
      candidate_count: 0,
      error_code: null,
      pause_reason: null,
    },
    mutation: null,
    ...overrides,
  };
}

describe("memory.service (无线程项目级个人记忆契约)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("readMemory 调用无线程 GET /api/langgraph/dear/memory 并携带 x-project-id 与 signal", async () => {
    const mockView = createMockMemoryView();
    (platformHttpClient.get as any).mockResolvedValueOnce({ data: mockView });
    const controller = new AbortController();

    const result = await readMemory("proj-1", controller.signal);
    expect(platformHttpClient.get).toHaveBeenCalledWith(
      "/api/langgraph/dear/memory",
      {
        headers: { "x-project-id": "proj-1" },
        signal: controller.signal,
      },
    );
    expect(result).toEqual(mockView);
  });

  it("saveMemoryFact 新增与编辑分别提交正确 payload（不含多余 undefined 字段）", async () => {
    const mockView = createMockMemoryView();
    (platformHttpClient.post as any).mockResolvedValue({ data: mockView });

    await saveMemoryFact("proj-1", 3, {
      text: "偏好简洁中文回答",
      category: "preference",
      expires_at: null,
    });
    expect(platformHttpClient.post).toHaveBeenLastCalledWith(
      "/api/langgraph/dear/memory",
      {
        action: "save",
        expected_revision: 3,
        fact: {
          text: "偏好简洁中文回答",
          category: "preference",
          expires_at: null,
        },
      },
      { headers: { "x-project-id": "proj-1" } },
    );

    await saveMemoryFact(
      "proj-1",
      4,
      { text: "修改后的事实", category: "fact", expires_at: "2026-12-31T23:59:59.999Z" },
      "fact-001",
    );
    expect(platformHttpClient.post).toHaveBeenLastCalledWith(
      "/api/langgraph/dear/memory",
      {
        action: "save",
        expected_revision: 4,
        fact: {
          text: "修改后的事实",
          category: "fact",
          expires_at: "2026-12-31T23:59:59.999Z",
        },
        fact_id: "fact-001",
      },
      { headers: { "x-project-id": "proj-1" } },
    );
  });

  it("deleteMemoryFact 与 clearMemory 提交无线程 POST 命令", async () => {
    (platformHttpClient.post as any).mockResolvedValue({ data: createMockMemoryView() });

    await deleteMemoryFact("proj-1", 5, "fact-001");
    expect(platformHttpClient.post).toHaveBeenLastCalledWith(
      "/api/langgraph/dear/memory",
      {
        action: "delete",
        expected_revision: 5,
        fact_id: "fact-001",
      },
      { headers: { "x-project-id": "proj-1" } },
    );

    await clearMemory("proj-1", 6);
    expect(platformHttpClient.post).toHaveBeenLastCalledWith(
      "/api/langgraph/dear/memory",
      {
        action: "clear",
        expected_revision: 6,
      },
      { headers: { "x-project-id": "proj-1" } },
    );
  });

  it("acceptMemoryCandidate 支持直接采纳与带 replace_fact_id 替换，rejectMemoryCandidate 拒绝候选", async () => {
    (platformHttpClient.post as any).mockResolvedValue({ data: createMockMemoryView() });

    await acceptMemoryCandidate("proj-1", 7, "cand-001");
    expect(platformHttpClient.post).toHaveBeenLastCalledWith(
      "/api/langgraph/dear/memory",
      {
        action: "accept",
        expected_revision: 7,
        fact_id: "cand-001",
      },
      { headers: { "x-project-id": "proj-1" } },
    );

    await acceptMemoryCandidate("proj-1", 8, "cand-002", "fact-old-1");
    expect(platformHttpClient.post).toHaveBeenLastCalledWith(
      "/api/langgraph/dear/memory",
      {
        action: "accept",
        expected_revision: 8,
        fact_id: "cand-002",
        replace_fact_id: "fact-old-1",
      },
      { headers: { "x-project-id": "proj-1" } },
    );

    await rejectMemoryCandidate("proj-1", 9, "cand-003");
    expect(platformHttpClient.post).toHaveBeenLastCalledWith(
      "/api/langgraph/dear/memory",
      {
        action: "reject",
        expected_revision: 9,
        fact_id: "cand-003",
      },
      { headers: { "x-project-id": "proj-1" } },
    );
  });

  it("updateMemorySettings 与 restoreMemoryFacts 发送正确指令，且支持解析嵌套 error.code", async () => {
    (platformHttpClient.post as any).mockResolvedValueOnce({ data: createMockMemoryView() });
    await updateMemorySettings("proj-1", 10, true);
    expect(platformHttpClient.post).toHaveBeenLastCalledWith(
      "/api/langgraph/dear/memory",
      {
        action: "settings",
        expected_revision: 10,
        automatic_candidates: true,
      },
      { headers: { "x-project-id": "proj-1" } },
    );

    const restorePayload = [{ text: "使用 Python 3.12", category: "fact" as const, expires_at: null }];
    (platformHttpClient.post as any).mockResolvedValueOnce({
      data: createMockMemoryView({
        mutation: { action: "restore", changed: true, added: 1, updated: 0, removed: 0, skipped: 2 },
      }),
    });
    const res = await restoreMemoryFacts("proj-1", 11, restorePayload);
    expect(res.mutation).toEqual({
      action: "restore",
      changed: true,
      added: 1,
      updated: 0,
      removed: 0,
      skipped: 2,
    });

    // 验证 Platform 真实嵌套错误包解析
    const mockNestedError = {
      response: {
        status: 409,
        data: {
          request_id: "req-conflict-99",
          error: {
            code: "memory_revision_conflict",
            message: "Memory has changed. Reload before saving.",
            details: [{ loc: ["body", "expected_revision"], message: "Conflict", type: "conflict" }],
          },
        },
      },
    };
    const parsedErr = extractPlatformHttpError(mockNestedError);
    expect(parsedErr.status).toBe(409);
    expect(parsedErr.code).toBe("memory_revision_conflict");
    expect(parsedErr.requestId).toBe("req-conflict-99");
    expect(parsedErr.details?.[0]?.loc).toEqual(["body", "expected_revision"]);
  });
});

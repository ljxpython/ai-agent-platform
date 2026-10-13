import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { useKnowledgeJobTracker } from "./useKnowledgeJobTracker";
import type { KnowledgeJob } from "@/services/knowledge/knowledge.service";

vi.mock("@/services/knowledge/knowledge.service", () => ({
  getKnowledgeJob: vi.fn(),
  isValidJobId: (id: string) => typeof id === "string" && id.length >= 8,
}));

describe("useKnowledgeJobTracker", () => {
  const tracker = useKnowledgeJobTracker();

  beforeEach(() => {
    vi.useFakeTimers();
    tracker.reset();
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  it("tracks an active job and ceases polling when reaching ready status", async () => {
    const job: KnowledgeJob = {
      version: 1,
      job_id: "job-00000001",
      document_id: "doc-00000001",
      file_name: "guide.md",
      status: "parsing",
      searchable: false,
      error_code: null,
      created_at: "2026-10-12T10:00:00Z",
      updated_at: "2026-10-12T10:00:00Z",
    };

    const callback = vi.fn();
    const unsubscribe = tracker.trackJob(
      "proj-1",
      "job-00000001",
      job,
      callback,
    );

    expect(tracker.getJob("job-00000001")?.status).toBe("parsing");
    expect(callback).toHaveBeenCalledWith(job);

    // 当任务状态变更为 ready 终态
    const readyJob: KnowledgeJob = {
      ...job,
      status: "ready",
      searchable: true,
    };
    tracker.trackJob("proj-1", "job-00000001", readyJob, callback);

    expect(tracker.getJob("job-00000001")?.status).toBe("ready");
    expect(callback).toHaveBeenCalledWith(readyJob);
    unsubscribe();
  });

  it("resets all active jobs and timers on project switch or logout", () => {
    const job: KnowledgeJob = {
      version: 1,
      job_id: "job-00000002",
      document_id: "doc-00000002",
      file_name: "spec.md",
      status: "indexing",
      searchable: false,
      error_code: null,
      created_at: "2026-10-12T10:00:00Z",
      updated_at: "2026-10-12T10:00:00Z",
    };

    tracker.trackJob("proj-1", "job-00000002", job);
    expect(tracker.getJob("job-00000002")).toBeDefined();

    tracker.reset();
    expect(tracker.getJob("job-00000002")).toBeUndefined();
  });

  it("prevents terminal status ready from regressing to queued", () => {
    const readyJob: KnowledgeJob = {
      version: 1,
      job_id: "job-00000003",
      document_id: "doc-00000003",
      file_name: "test.pdf",
      status: "ready",
      searchable: true,
      error_code: null,
      created_at: "2026-10-12T10:00:00Z",
      updated_at: "2026-10-12T10:00:00Z",
    };
    tracker.trackJob("proj-1", "job-00000003", readyJob);
    expect(tracker.getJob("job-00000003")?.status).toBe("ready");

    // 后到的旧 queued 数据试图降级
    const staleQueuedJob: KnowledgeJob = {
      ...readyJob,
      status: "queued",
      searchable: false,
    };
    tracker.trackJob("proj-1", "job-00000003", staleQueuedJob);
    expect(tracker.getJob("job-00000003")?.status).toBe("ready");
    expect(tracker.getJob("job-00000003")?.searchable).toBe(true);
  });
});

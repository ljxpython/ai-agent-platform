import { describe, expect, it, vi, beforeEach } from "vitest";
import {
  buildEvalFlowDashboardUrl,
  buildLangfuseTraceUrl,
  buildMlflowTraceUrl,
  buildTraceUrl,
  isTracingEnabled,
  getProjectExperimentId,
  setProjectExperimentId,
  clearProjectExperimentCache,
  fetchProjectExperimentId,
} from "./langfuse-url";
import { env } from "@/config/env";

describe("buildLangfuseTraceUrl", () => {
  it("returns empty string if traceId is empty", () => {
    expect(buildLangfuseTraceUrl("")).toBe("");
    expect(buildLangfuseTraceUrl("   ")).toBe("");
  });

  it("builds project search URL when projectId is configured", () => {
    const url = buildLangfuseTraceUrl("f878c122-0323-4828-a377-3a111b508f20", {
      projectId: "cmt2gj4cq001fad0dffy9vu9v",
      baseUrl: "https://jp.cloud.langfuse.com",
    });

    expect(url).toContain(
      "https://jp.cloud.langfuse.com/project/cmt2gj4cq001fad0dffy9vu9v/traces?",
    );
    expect(url).toContain("filter=isRootObservation%3Bboolean%3B%3B%3D%3Btrue");
    expect(url).toContain("searchType=id");
    expect(url).toContain("searchType=content");
    expect(url).toContain("traceTab=attributes");
    expect(url).toContain("search=f878c122-0323-4828-a377-3a111b508f20");
  });

  it("builds custom template URL when template is provided", () => {
    const url = buildLangfuseTraceUrl("f878c122", {
      template: "https://my-langfuse.internal/traces/{traceId}?view=tree",
    });
    expect(url).toBe("https://my-langfuse.internal/traces/f878c122?view=tree");
  });

  it("falls back to default /trace/{id} when no projectId and no template", () => {
    const originalProjectId = env.langfuseProjectId;
    const originalTemplate = env.langfuseTraceUrlTemplate;
    env.langfuseProjectId = "";
    env.langfuseTraceUrlTemplate = "";

    try {
      const url = buildLangfuseTraceUrl("f878c122", {
        baseUrl: "https://jp.cloud.langfuse.com",
        projectId: "",
        template: "",
      });
      expect(url).toBe("https://jp.cloud.langfuse.com/trace/f878c122");
    } finally {
      env.langfuseProjectId = originalProjectId;
      env.langfuseTraceUrlTemplate = originalTemplate;
    }
  });
});

describe("buildMlflowTraceUrl", () => {
  it("returns empty string if both traceId and threadId are empty", () => {
    expect(buildMlflowTraceUrl("")).toBe("");
    expect(buildMlflowTraceUrl("  ", { threadId: "  " })).toBe("");
  });

  it("builds session filtered URL when threadId is present", () => {
    const url = buildMlflowTraceUrl("trace-123", {
      baseUrl: "http://127.0.0.1:5001",
      experimentId: "0",
      threadId: "th_test_session_1",
    });
    expect(url).toBe(
      "http://127.0.0.1:5001/#/experiments/0/traces?search=session_id%20%3D%20'th_test_session_1'",
    );
  });

  it("builds trace search URL when threadId is absent", () => {
    const url = buildMlflowTraceUrl("trace-123", {
      baseUrl: "http://127.0.0.1:5001",
      experimentId: "0",
    });
    expect(url).toBe(
      "http://127.0.0.1:5001/#/experiments/0/traces?search=trace-123",
    );
  });

  it("supports custom template for mlflow", () => {
    const url = buildMlflowTraceUrl("trace-123", {
      template: "http://custom-mlflow/#/experiments/0/traces/{traceId}",
    });
    expect(url).toBe("http://custom-mlflow/#/experiments/0/traces/trace-123");
  });
  it("supports sessions view for mlflow", () => {
    const url = buildMlflowTraceUrl("", {
      baseUrl: "http://127.0.0.1:9128",
      experimentId: "6",
      threadId: "th_test_session_1",
      view: "sessions",
    });
    expect(url).toBe(
      "http://127.0.0.1:9128/#/experiments/6/chat-sessions/th_test_session_1",
    );
  });

  it("builds direct trace detail URL when id starts with tr-", () => {
    const url = buildMlflowTraceUrl("tr-27af92ff7f89c56a9c03e375c64c2cfc", {
      baseUrl: "http://127.0.0.1:9128",
      experimentId: "9",
    });
    expect(url).toBe(
      "http://127.0.0.1:9128/#/experiments/9/traces/tr-27af92ff7f89c56a9c03e375c64c2cfc",
    );
  });

  it("dynamically resolves experimentId from projectId cache", () => {
    setProjectExperimentId("proj-xyz", "99");
    const url = buildMlflowTraceUrl("", {
      baseUrl: "http://127.0.0.1:9128",
      projectId: "proj-xyz",
      threadId: "session-123",
    });
    expect(url).toContain("/#/experiments/99/traces?search=");
    clearProjectExperimentCache();
  });
});

describe("fetchProjectExperimentId", () => {
  beforeEach(() => {
    clearProjectExperimentCache();
    vi.restoreAllMocks();
  });

  it("returns cached experimentId directly without network call", async () => {
    setProjectExperimentId("proj-cached", "42");
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const res = await fetchProjectExperimentId("proj-cached");
    expect(res).toBe("42");
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("fetches from MLflow API and caches the result", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => ({ experiment: { experiment_id: "88" } }),
    } as any);

    const res = await fetchProjectExperimentId("proj-remote");
    expect(res).toBe("88");
    expect(getProjectExperimentId("proj-remote")).toBe("88");
    expect(fetchSpy).toHaveBeenCalledWith(
      expect.stringContaining("project-proj-remote"),
      expect.any(Object),
    );
  });
});

describe("buildTraceUrl", () => {
  it("returns empty string when provider is none", () => {
    const url = buildTraceUrl("trace-123", {
      provider: "none",
    });
    expect(url).toBe("");
  });

  it("delegates to MLflow when provider is mlflow", () => {
    const url = buildTraceUrl("trace-123", {
      provider: "mlflow",
      baseUrl: "http://127.0.0.1:9128",
      experimentId: "6",
      threadId: "session-abc",
    });
    expect(url).toContain("http://127.0.0.1:9128/#/experiments/6/traces");
    expect(url).toContain("session_id");
  });

  it("delegates to Langfuse when provider is langfuse", () => {
    const url = buildTraceUrl("trace-123", {
      provider: "langfuse",
      baseUrl: "https://jp.cloud.langfuse.com",
    });
    expect(url).toContain("https://jp.cloud.langfuse.com");
  });
});

describe("buildEvalFlowDashboardUrl", () => {
  it("returns base url stripped of trailing slash", () => {
    expect(buildEvalFlowDashboardUrl("http://127.0.0.1:9128/")).toBe(
      "http://127.0.0.1:9128",
    );
  });
});

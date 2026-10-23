import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount } from "@vue/test-utils";
import DiagnosticDetailModal from "./DiagnosticDetailModal.vue";
import * as diagnosticPacketModule from "@/services/observability/diagnostic-packet";
import { errorRingBuffer } from "@/services/observability/error-buffer";

describe("DiagnosticDetailModal.vue", () => {
  beforeEach(() => {
    errorRingBuffer.clear();
    vi.restoreAllMocks();
  });

  it("当 show 为 false 时不渲染弹窗 DOM", () => {
    const wrapper = mount(DiagnosticDetailModal, {
      props: {
        show: false,
      },
    });

    expect(wrapper.find('[role="dialog"]').exists()).toBe(false);
  });

  it("当 show 为 true 时正确渲染模态窗、原因码、恢复建议和 Request ID", () => {
    const wrapper = mount(DiagnosticDetailModal, {
      props: {
        show: true,
        projectId: "proj-101",
        threadId: "thread-202",
        runId: "run-303",
        requestId: "req-trace-404",
        errorCode: "context_too_long",
        error: "Conversation context exceeded maximum model limit",
      },
    });

    expect(wrapper.find('[role="dialog"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="diagnostic-reason-code"]').text()).toBe(
      "context_too_long",
    );
    expect(
      wrapper.find('[data-testid="diagnostic-follow-up"]').text(),
    ).toContain("建议点击左侧新建会话");
    expect(wrapper.find('[data-testid="diagnostic-request-id"]').text()).toBe(
      "req-trace-404",
    );
  });

  it("点击关闭按钮时应当触发 update:show 和 close 事件", async () => {
    const wrapper = mount(DiagnosticDetailModal, {
      props: {
        show: true,
      },
    });

    const closeBtn = wrapper.find('button[aria-label="关闭"]');
    await closeBtn.trigger("click");

    expect(wrapper.emitted("update:show")?.[0]).toEqual([false]);
    expect(wrapper.emitted("close")).toBeTruthy();
  });

  it("点击【前往完整轨迹诊断】应当触发 open-trajectory 事件并关闭弹窗", async () => {
    const wrapper = mount(DiagnosticDetailModal, {
      props: {
        show: true,
        canViewTrajectory: true,
      },
    });

    const trajectoryBtn = wrapper.find('[data-testid="go-to-trajectory-btn"]');
    expect(trajectoryBtn.exists()).toBe(true);
    await trajectoryBtn.trigger("click");

    expect(wrapper.emitted("open-trajectory")).toBeTruthy();
    expect(wrapper.emitted("update:show")?.[0]).toEqual([false]);
  });

  it("点击【复制排障诊断包】应当调用底层复制函数并提供视觉反馈", async () => {
    const copySpy = vi
      .spyOn(diagnosticPacketModule, "copyDiagnosticPacket")
      .mockResolvedValue({
        success: true,
        markdown: "Mock Markdown",
      });

    const wrapper = mount(DiagnosticDetailModal, {
      props: {
        show: true,
        requestId: "req-999",
        errorCode: "provider_timeout",
      },
    });

    const copyBtn = wrapper.find('[data-testid="copy-diagnostic-packet-btn"]');
    await copyBtn.trigger("click");

    expect(copySpy).toHaveBeenCalled();
    expect(copyBtn.text()).toContain("排障信息已复制");
  });

  it("当前端无可用错误但后端有诊断时，异步拉取诊断并展示 Trace URL 与后端失败原因", async () => {
    const diagnosticsService =
      await import("@/services/threads/diagnostics.service");
    const getSpy = vi
      .spyOn(diagnosticsService, "getRunDiagnostics")
      .mockResolvedValue({
        version: 1,
        availability: "available",
        correlation: {
          execution_request_id: "backend-exec-req-777",
          platform_trace_id: "backend-platform-trace-888",
        },
        trace: {
          provider: "langfuse",
          trace_id: "langfuse-trace-999",
        },
        graph_executions: [],
        model_errors: [
          {
            observation_id: "obs-1",
            scope: "primary",
            namespace: [],
            code: "provider_overloaded" as any,
            provider_status: 503,
            error_type: "OverloadedError",
            duration_ms: 120,
          },
        ],
        workspace_executions: [],
        startup: null,
        preparations: [],
        retries: [],
        loop_detections: [],
        truncated: false,
        thread_id: "thread-mock-1",
        run_id: "run-mock-1",
        run_status: "error",
        request_id: "diag-req-123",
      });

    const wrapper = mount(DiagnosticDetailModal, {
      props: {
        show: true,
        projectId: "proj-1",
        threadId: "thread-mock-1",
        runId: "run-mock-1",
        // error 与 requestId 均为空，模拟流异常中断且前端未捕获到显式消息的情形
        error: "",
        requestId: "",
      },
    });

    // 等待异步调用完成
    await vi.waitFor(() => {
      expect(getSpy).toHaveBeenCalledWith("thread-mock-1", "run-mock-1", {
        projectId: "proj-1",
      });
    });

    // 验证回填的 Request ID 为后端的 execution_request_id
    expect(wrapper.find('[data-testid="diagnostic-request-id"]').text()).toBe(
      "backend-exec-req-777",
    );

    // 验证展示了 Langfuse Trace ID 与 Open Trace 按钮
    expect(wrapper.find('[data-testid="diagnostic-trace-id"]').text()).toBe(
      "langfuse-trace-999",
    );
    const openTraceLink = wrapper.find(
      '[data-testid="diagnostic-open-trace-btn"]',
    );
    expect(openTraceLink.exists()).toBe(true);
    expect(openTraceLink.attributes("href")).toContain("langfuse-trace-999");
    expect(openTraceLink.attributes("href")).toMatch(
      /^https:\/\/jp\.cloud\.langfuse\.com\//,
    );

    // 验证从后端的 model_errors 自动解析了错误消息与原因码
    expect(wrapper.find('[data-testid="diagnostic-reason-code"]').text()).toBe(
      "provider_overloaded",
    );
    expect(wrapper.text()).toContain(
      "[Model Failure] Code: provider_overloaded",
    );
    expect(wrapper.text()).toContain("HTTP: 503");
  });
});

import { describe, it, expect, vi, beforeEach } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import DiagnosticDetailModal from "./DiagnosticDetailModal.vue";
import * as diagnosticPacketModule from "@/services/observability/diagnostic-packet";
import { errorRingBuffer } from "@/services/observability/error-buffer";
import { usePlatformAssistantStore } from "@/modules/platform-assistant/stores/usePlatformAssistantStore";
import { getRunDiagnostics } from "@/services/threads/diagnostics.service";

describe("DiagnosticDetailModal.vue", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
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

  it("切换目标后丢弃旧请求晚到的诊断；已恢复运行显示成功说明", async () => {
    const service = await import("@/services/threads/diagnostics.service");
    let completeOld!: (
      value: Awaited<ReturnType<typeof getRunDiagnostics>>,
    ) => void;
    const old = new Promise<Awaited<ReturnType<typeof getRunDiagnostics>>>(
      (resolve) => {
        completeOld = resolve;
      },
    );
    const diagnostics = (
      requestId: string,
      runId: string,
      status = "error",
    ) => ({
      version: 1 as const,
      availability: "available" as const,
      correlation: { execution_request_id: requestId },
      trace: null,
      thread_id: "thread",
      run_id: runId,
      run_status: status,
      request_id: requestId,
      model_errors: [],
      graph_executions: [],
      startup: null,
      truncated: false,
    });
    vi.spyOn(service, "getRunDiagnostics")
      .mockReturnValueOnce(old)
      .mockResolvedValueOnce(diagnostics("current-request", "new", "success"));
    const wrapper = mount(DiagnosticDetailModal, {
      props: {
        show: true,
        projectId: "project",
        threadId: "thread",
        runId: "old",
      },
    });
    await wrapper.setProps({ runId: "new" });
    await flushPromises();
    completeOld(diagnostics("stale-request", "old"));
    await flushPromises();
    expect(wrapper.text()).toContain("current-request");
    expect(wrapper.text()).not.toContain("stale-request");
    expect(wrapper.text()).toContain("运行最终成功");
    await wrapper.setProps({ threadId: undefined, runId: null });
    expect(wrapper.text()).not.toContain("current-request");
  });

  it("复制与求助使用相同解析编号和明确错误码；助手故障不影响复制", async () => {
    const store = usePlatformAssistantStore();
    vi.spyOn(store, "ensureBootstrap").mockResolvedValue({
      project_id: "p",
      personal_project: false,
      assistant_id: "platform_assistant",
      agent_id: "a",
      model_id: "m",
      history: true,
    });
    const open = vi.spyOn(store, "openWithDiagnostic");
    const copy = vi
      .spyOn(diagnosticPacketModule, "copyDiagnosticPacket")
      .mockResolvedValue({ success: true, markdown: "packet" });
    const wrapper = mount(DiagnosticDetailModal, {
      props: {
        show: true,
        requestId: "target",
        errorCode: "model_unavailable",
        error: "no model",
      },
    });
    await wrapper
      .find('[data-testid="copy-diagnostic-packet-btn"]')
      .trigger("click");
    await wrapper
      .find('[data-testid="ask-platform-assistant-btn"]')
      .trigger("click");
    expect(copy.mock.calls[0][0]).toMatchObject({
      requestId: "target",
      errorCode: "model_unavailable",
      error: "no model",
    });
    expect(open.mock.calls[0][0].diagnosticMarkdown).toContain(
      "关联 Request ID: `target`",
    );
    expect(open.mock.calls[0][0].diagnosticMarkdown).toContain(
      "机器代码: `model_unavailable`",
    );
    expect(open.mock.calls[0][0].diagnosticMarkdown).toContain(
      "原始错误: no model",
    );
  });

  it("无请求编号的前端错误不认领最近请求，求助保留原始现场", async () => {
    const store = usePlatformAssistantStore();
    const open = vi
      .spyOn(store, "openWithDiagnostic")
      .mockImplementation(() => {});
    errorRingBuffer.push({
      type: "http",
      requestId: "unrelated-request",
      code: "provider_rate_limited",
      message: "unrelated 429",
    });
    const wrapper = mount(DiagnosticDetailModal, {
      props: { show: true, error: "UI Render Crash", canViewTrajectory: false },
    });
    expect(
      wrapper.find('[data-testid="diagnostic-request-id"]').text(),
    ).toContain("未关联");
    await wrapper
      .find('[data-testid="ask-platform-assistant-btn"]')
      .trigger("click");
    const packet = open.mock.calls[0][0].diagnosticMarkdown;
    const target = packet.split("- **其他近期异常")[0];
    expect(target).toContain("关联 Request ID: `未关联`");
    expect(target).toContain("原始错误: UI Render Crash");
    expect(target).not.toContain("unrelated-request");
    expect(target).not.toContain("provider_rate_limited");
  });
});

import { describe, expect, it, vi } from "vitest";
import { mount } from "@vue/test-utils";
import RunDiagnostics from "./RunDiagnostics.vue";
import type { RunDiagnosticsV1 } from "../../diagnostics/types";
import { ref } from "vue";

// Mock composable
const mockData = ref<RunDiagnosticsV1 | null>(null);
const mockLoading = ref(false);
const mockError = ref<Error | null>(null);
const mockRefresh = vi.fn();

vi.mock("../../composables/useRunDiagnostics", () => ({
  useRunDiagnostics: () => ({
    data: mockData,
    loading: mockLoading,
    isRefreshing: ref(false),
    error: mockError,
    refresh: mockRefresh,
  }),
}));

describe("RunDiagnostics.vue", () => {
  const baseDiagnostic: RunDiagnosticsV1 = {
    version: 1,
    thread_id: "thread-123",
    run_id: "run-456",
    run_status: "success",
    request_id: "req-789",
    availability: "available",
    unavailable_reason: null,
    correlation: {
      execution_request_id: "exec-1",
      platform_trace_id: "trace-1",
    },
    trace: { provider: "langfuse", trace_id: "lf-trace-1", url: null },
    graph_executions: [],
    model_errors: [
      {
        observation_id: "obs-1",
        scope: "primary",
        namespace: [],
        code: "provider_rate_limited",
        error_type: "RateLimitError",
        provider_status: 429,
        duration_ms: 100,
      },
    ],
    startup: {
      duration_ms: 50,
      phases: [
        {
          name: "factory.model_connection",
          ordinal: 0,
          outcome: "completed",
          started_at: null,
          ended_at: null,
          duration_ms: 50,
          error_code: null,
        },
      ],
    },
    truncated: false,
  };

  it("当未指定 runId 时展示空态", () => {
    mockData.value = null;
    const wrapper = mount(RunDiagnostics, {
      props: {
        threadId: "thread-123",
        runId: null,
      },
    });

    expect(wrapper.text()).toContain("未选择运行目标");
  });

  it("渲染诊断数据：当 run_status 为 success 时模型错误为 Amber 警示", () => {
    mockData.value = { ...baseDiagnostic, run_status: "success" };
    mockLoading.value = false;
    mockError.value = null;

    const wrapper = mount(RunDiagnostics, {
      props: {
        threadId: "thread-123",
        runId: "run-456",
      },
    });

    expect(wrapper.text()).toContain("运行诊断");
    expect(wrapper.text()).toContain("已完成");
    expect(wrapper.text()).toContain("模型服务限流");
    expect(wrapper.text()).toContain("已通过重试或备选模型恢复");
    // 不应出现致命红色大横幅
    expect(wrapper.find(".text-red-700").exists()).toBe(false);
  });

  it("当 run_status 为 error 时模型错误以 error 呈现", () => {
    mockData.value = { ...baseDiagnostic, run_status: "error" };

    const wrapper = mount(RunDiagnostics, {
      props: {
        threadId: "thread-123",
        runId: "run-456",
      },
    });

    expect(wrapper.text()).toContain("执行失败");
    expect(wrapper.text()).toContain("模型服务限流");
  });

  it("展示启动阶段流水及耗时", () => {
    mockData.value = baseDiagnostic;

    const wrapper = mount(RunDiagnostics, {
      props: {
        threadId: "thread-123",
        runId: "run-456",
      },
    });

    expect(wrapper.text()).toContain("factory.model_connection");
    expect(wrapper.text()).toContain("50 ms");
    expect(wrapper.text()).toContain("已完成");
  });

  it("切换 Run 选项时 emit select-run 事件", async () => {
    mockData.value = baseDiagnostic;

    const wrapper = mount(RunDiagnostics, {
      props: {
        threadId: "thread-123",
        runId: "run-456",
        runs: [
          { run_id: "run-456", status: "success" },
          { run_id: "run-789", status: "error" },
        ],
      },
    });

    const select = wrapper.find("select");
    expect(select.exists()).toBe(true);
    await select.setValue("run-789");

    expect(wrapper.emitted("select-run")?.[0]).toEqual(["run-789"]);
  });
});

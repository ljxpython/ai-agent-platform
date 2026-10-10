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

vi.mock("../../composables/useRunCompletion", () => ({
  useRunCompletion: () => ({
    data: ref(null),
    loading: ref(false),
    completion: ref(null),
    failurePresentation: ref(null),
    refresh: vi.fn(),
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
    preparations: [],
    retries: [],
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

  it("当 preparations 和 retries 为空时隐藏两子区域，不显示任何空态占位", () => {
    mockData.value = {
      ...baseDiagnostic,
      preparations: [],
      retries: [],
    };

    const wrapper = mount(RunDiagnostics, {
      props: {
        threadId: "thread-123",
        runId: "run-456",
      },
    });

    expect(
      wrapper.find('[data-testid="run-preparations-section"]').exists(),
    ).toBe(false);
    expect(wrapper.find('[data-testid="run-retries-section"]').exists()).toBe(
      false,
    );
    expect(wrapper.text()).not.toContain("运行准备记录");
    expect(wrapper.text()).not.toContain("调用尝试与重试");
  });

  it("当 preparations 和 retries 包含数据时正确挂载并渲染对应子组件", () => {
    mockData.value = {
      ...baseDiagnostic,
      preparations: [
        {
          observation_id: "prep-1",
          scope: "primary",
          namespace: [],
          component: "workspace",
          outcome: "prepared",
          duration_ms: 10,
          error_code: null,
        },
      ],
      retries: [
        {
          observation_id: "retry-1",
          scope: "primary",
          namespace: [],
          unit: "model",
          role: null,
          attempts: 2,
          outcome: "success",
          code: "provider_rate_limited",
          duration_ms: 800,
        },
      ],
    };

    const wrapper = mount(RunDiagnostics, {
      props: {
        threadId: "thread-123",
        runId: "run-456",
      },
    });

    expect(
      wrapper.find('[data-testid="run-preparations-section"]').exists(),
    ).toBe(true);
    expect(wrapper.find('[data-testid="run-retries-section"]').exists()).toBe(
      true,
    );
    expect(wrapper.text()).toContain("运行准备记录");
    expect(wrapper.text()).toContain("调用尝试与重试");
    expect(wrapper.text()).toContain("重试 1 次");
  });
});

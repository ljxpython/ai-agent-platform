import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import RunEvidenceDetail from "@/modules/evaluation/components/RunEvidenceDetail.vue";
import RunLogTerminalDialog from "@/modules/evaluation/components/RunLogTerminalDialog.vue";
import RunResultsPanel from "@/modules/evaluation/components/RunResultsPanel.vue";
import SuiteHistoryMetricsDialog from "@/modules/evaluation/components/SuiteHistoryMetricsDialog.vue";
import type {
  EvalRunCaseItem,
  EvalRunItem,
  EvalSuiteItem,
} from "@/services/evaluation/studio";

vi.mock("echarts", () => ({
  init: () => ({
    setOption: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
    isDisposed: () => false,
    getWidth: () => 500,
  }),
}));

const mockSuites: EvalSuiteItem[] = [
  {
    id: "suite-1",
    name: "核心客服黄金集",
    description: "desc",
    suite_type: "golden",
    owner_project_id: "p1",
    source_project_id: null,
    default_graph_id: "dearflow_agent",
    created_by: "u1",
    archived_at: null,
    created_at: "2026-11-28T00:00:00Z",
    updated_at: "2026-11-28T00:00:00Z",
  },
];

const runningRun: EvalRunItem = {
  id: "run-running-1111",
  suite_id: "suite-1",
  suite_name: "核心客服黄金集",
  version_id: "ver-1",
  version_num: 2,
  owner_project_id: "p1",
  target_project_id: "p-target",
  target_project_name: "隔离靶场",
  target_graph_id: "dearflow_agent",
  target_agent_id: "ag-1",
  target_model_id: "m-1",
  target_model_name: "DeepSeek-V4",
  judge_model_id: "m-2",
  embedding_model_id: null,
  matrix_group_id: null,
  mode: "regression",
  concurrency: 3,
  repeat_k: 1,
  status: "running",
  gate_exit_code: null,
  summary_metrics: {
    total_cases: 3,
    progress: {
      total: 3,
      active_total: 3,
      done: 1,
      completed: 1,
      failed: 0,
      error: 0,
      running: 1,
      pending: 1,
      paused: 0,
      cancelled: 0,
      skipped_incompatible: 0,
      percent: 33,
    },
    recent_logs: [
      "[22:10:01] [INFO] [CASE-02 #1] 第 1 轮响应完成 · TTFT=920ms",
    ],
  },
  created_by: "u1",
  created_at: "2026-11-28T10:00:00Z",
  finished_at: null,
};

const historyRun1: EvalRunItem = {
  ...runningRun,
  id: "run-hist-1111",
  status: "failed",
  gate_exit_code: 1,
  created_at: "2026-11-28T08:00:00Z",
  finished_at: "2026-11-28T08:02:00Z",
  summary_metrics: {
    total_cases: 3,
    overall_score: 0.65,
    tsr_pass_at_1: 0.67,
    l1_pass_rate: 0.67,
    loop_rate: 0.33,
    ttft_ms: { p50: 1500, p95: 2400, p99: 2600 },
    duration_ms: { avg: 5200, p50: 5000, p95: 7000, p99: 7200 },
    token_usage: { total_tokens: 2100 },
    total_cost_usd: 0.0021,
    metrics_breakdown: {
      completion: {
        layer: "L1",
        avg_score: 0.67,
        pass_rate: 0.67,
        sample_count: 3,
      },
      faithfulness: {
        layer: "L2",
        avg_score: 0.63,
        pass_rate: 0.67,
        sample_count: 3,
      },
    },
  },
};

const historyRun2: EvalRunItem = {
  ...runningRun,
  id: "run-hist-2222",
  status: "completed",
  gate_exit_code: 0,
  created_at: "2026-11-28T09:00:00Z",
  finished_at: "2026-11-28T09:02:00Z",
  summary_metrics: {
    total_cases: 3,
    overall_score: 0.92,
    tsr_pass_at_1: 1.0,
    l1_pass_rate: 1.0,
    loop_rate: 0.0,
    ttft_ms: { p50: 980, p95: 1400, p99: 1600 },
    duration_ms: { avg: 3400, p50: 3200, p95: 4500, p99: 4800 },
    token_usage: { total_tokens: 1500 },
    total_cost_usd: 0.0014,
    metrics_breakdown: {
      completion: {
        layer: "L1",
        avg_score: 1.0,
        pass_rate: 1.0,
        sample_count: 3,
      },
      faithfulness: {
        layer: "L2",
        avg_score: 0.88,
        pass_rate: 1.0,
        sample_count: 3,
      },
    },
  },
};

const mockRunCases: EvalRunCaseItem[] = [
  {
    id: "rc-1",
    run_id: runningRun.id,
    case_key: "CASE-01",
    attempt_idx: 1,
    status: "completed",
    thread_id: "th-1",
    trace_ids: [],
    rule_passed: true,
    overall_score: 1.0,
    duration_ms: 2100,
    ttft_ms: 800,
    token_usage: {},
    cost_usd: 0.001,
    error_category: "none",
    evidence_path: null,
    results: { final_answer: "ok", metrics: [] },
  },
  {
    id: "rc-2",
    run_id: runningRun.id,
    case_key: "CASE-02",
    attempt_idx: 1,
    status: "running",
    thread_id: null,
    trace_ids: [],
    rule_passed: null,
    overall_score: null,
    duration_ms: null,
    ttft_ms: null,
    token_usage: {},
    cost_usd: null,
    error_category: null,
    evidence_path: null,
    results: {},
  },
  {
    id: "rc-3",
    run_id: runningRun.id,
    case_key: "CASE-03",
    attempt_idx: 1,
    status: "pending",
    thread_id: null,
    trace_ids: [],
    rule_passed: null,
    overall_score: null,
    duration_ms: null,
    ttft_ms: null,
    token_usage: {},
    cost_usd: null,
    error_category: null,
    evidence_path: null,
    results: {},
  },
];

const commonStubs = {
  BaseButton: {
    props: ["disabled", "variant", "size"],
    template:
      '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
  },
  BaseInput: {
    props: ["modelValue", "placeholder"],
    template:
      '<input :value="modelValue" :placeholder="placeholder" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  BaseSelect: {
    props: ["modelValue", "options"],
    template: '<div class="base-select-stub" />',
  },
  BaseDialog: {
    props: ["show", "title", "width"],
    template:
      '<div v-if="show"><div class="dialog-title">{{ title }}</div><slot /></div>',
  },
  SurfaceCard: { template: "<div><slot /></div>" },
  MetricCard: {
    props: ["label", "value", "hint"],
    template: "<div><span>{{ label }}</span><span>{{ value }}</span></div>",
  },
  StatusPill: { template: "<span><slot /></span>" },
  EmptyState: { template: "<div>empty</div>" },
};

describe("Task Hall Optimization Components", () => {
  it("renders in-flight queue with progress and emits deleteRun / openLogs / openSuiteHistory", async () => {
    const wrapper = mount(RunResultsPanel, {
      props: {
        runs: [runningRun, historyRun2, historyRun1],
        suites: mockSuites,
        activeRun: runningRun,
        runCases: mockRunCases,
      },
      global: { stubs: commonStubs },
    });

    expect(wrapper.text()).toContain("正在进行的打擂队列 (1)");
    expect(wrapper.text()).toContain("已完成 1/3 题 · 执行中 1 · 待执行 1");
    expect(wrapper.text()).toContain("[CASE-02 #1] 第 1 轮响应完成");

    const logBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("实时日志"));
    expect(logBtn).toBeDefined();
    await logBtn!.trigger("click");
    expect(wrapper.emitted("openLogs")![0]).toEqual([runningRun]);

    const historyBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("历史指标对比"));
    expect(historyBtn).toBeDefined();
    await historyBtn!.trigger("click");
    expect(wrapper.emitted("openSuiteHistory")).toBeTruthy();

    const delBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("🗑 删除"));
    expect(delBtn).toBeDefined();
    await delBtn!.trigger("click");
    expect(wrapper.emitted("deleteRun")).toBeTruthy();
  });

  it("filters run cases by execution status in RunEvidenceDetail", async () => {
    const wrapper = mount(RunEvidenceDetail, {
      props: {
        activeRun: runningRun,
        runCases: mockRunCases,
      },
      global: { stubs: commonStubs },
    });

    expect(wrapper.text()).toContain("1/3 已收口 · 1 执行中 · 1 未开始");
    expect(wrapper.text()).toContain("CASE-01");
    expect(wrapper.text()).toContain("CASE-02");
    expect(wrapper.text()).toContain("CASE-03");

    const runningTab = wrapper
      .findAll("button")
      .find((b) => b.text().includes("运行中 (1)"));
    await runningTab!.trigger("click");
    expect(wrapper.text()).toContain("CASE-02");
    expect(wrapper.text()).not.toContain("CASE-01");
    expect(wrapper.text()).not.toContain("CASE-03");

    const pendingTab = wrapper
      .findAll("button")
      .find((b) => b.text().includes("待执行 (1)"));
    await pendingTab!.trigger("click");
    expect(wrapper.text()).toContain("CASE-03");
    expect(wrapper.text()).not.toContain("CASE-02");
  });

  it("pulls and filters logs in RunLogTerminalDialog", async () => {
    const fetchLogs = vi.fn().mockResolvedValue({
      run_id: runningRun.id,
      status: "completed",
      progress: runningRun.summary_metrics.progress,
      logs: [
        {
          seq: 1,
          level: "INFO",
          case_key: null,
          message: "[批次] 开始执行评测",
          created_at: "2026-11-28T10:00:00Z",
        },
        {
          seq: 2,
          level: "ERROR",
          case_key: "CASE-02",
          message: "[CASE-02 #1] 模型超时",
          created_at: "2026-11-28T10:00:05Z",
        },
      ],
      last_seq: 2,
    });

    const wrapper = mount(RunLogTerminalDialog, {
      props: {
        show: true,
        run: runningRun,
        fetchLogs,
      },
      global: { stubs: commonStubs },
    });

    await flushPromises();
    expect(fetchLogs).toHaveBeenCalledWith(runningRun.id, {
      after_seq: 0,
      limit: 300,
    });
    expect(wrapper.text()).toContain("[批次] 开始执行评测");
    expect(wrapper.text()).toContain("[CASE-02 #1] 模型超时");

    const filterInput = wrapper.find("input");
    await filterInput.setValue("CASE-02");
    expect(wrapper.text()).toContain("模型超时");
    expect(wrapper.text()).not.toContain("开始执行评测");
  });

  it("renders multi-run metrics matrix and triggers PK in SuiteHistoryMetricsDialog", async () => {
    const wrapper = mount(SuiteHistoryMetricsDialog, {
      props: {
        show: true,
        suiteName: "核心客服黄金集",
        runs: [historyRun1, historyRun2],
      },
      global: { stubs: commonStubs },
    });

    expect(wrapper.text()).toContain(
      "同评测集历史各指标对比与趋势 · 核心客服黄金集",
    );
    expect(wrapper.text()).toContain("子指标 · completion");
    expect(wrapper.text()).toContain("子指标 · faithfulness");
    expect(wrapper.text()).toContain("+25%");
    expect(wrapper.text()).toContain("🏆");

    const pkBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("对比最近两场逐题 PK"));
    expect(pkBtn).toBeDefined();
    await pkBtn!.trigger("click");
    expect(wrapper.emitted("compareTwo")![0]).toEqual([
      historyRun1.id,
      historyRun2.id,
    ]);
  });

  it("displays summary_metrics.error banner in RunEvidenceDetail and RunLogTerminalDialog", async () => {
    const errRun: EvalRunItem = {
      ...runningRun,
      id: "run-err-9999",
      status: "error",
      summary_metrics: {
        error: "1 validation error for Case: turns.1.role",
      },
    };
    const detailWrapper = mount(RunEvidenceDetail, {
      props: { activeRun: errRun, runCases: [] },
      global: { stubs: commonStubs },
    });
    expect(detailWrapper.text()).toContain("批次执行异常原因");
    expect(detailWrapper.text()).toContain("turns.1.role");

    const logWrapper = mount(RunLogTerminalDialog, {
      props: {
        show: true,
        run: errRun,
        fetchLogs: vi.fn().mockResolvedValue({
          run_id: errRun.id,
          status: "error",
          progress: {
            total: 1,
            done: 0,
            completed: 0,
            failed: 0,
            error: 0,
            running: 0,
            pending: 1,
            paused: 0,
            cancelled: 0,
            skipped_incompatible: 0,
            percent: 0,
          },
          logs: [],
          last_seq: 0,
        }),
      },
      global: { stubs: commonStubs },
    });
    await flushPromises();
    expect(logWrapper.text()).toContain("批次级错误摘要");
    expect(logWrapper.text()).toContain("turns.1.role");
  });
});

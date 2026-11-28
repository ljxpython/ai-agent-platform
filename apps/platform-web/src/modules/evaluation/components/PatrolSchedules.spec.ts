import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import PatrolScheduleModal from "@/modules/evaluation/components/PatrolScheduleModal.vue";
import PatrolSchedulesPanel from "@/modules/evaluation/components/PatrolSchedulesPanel.vue";
import RunResultsPanel from "@/modules/evaluation/components/RunResultsPanel.vue";
import type {
  EvalRunItem,
  EvalSuiteItem,
  PatrolScheduleItem,
} from "@/services/evaluation/studio";

vi.mock("@/services/evaluation/studio", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/services/evaluation/studio")>();
  return {
    ...actual,
    getSuiteDetail: vi.fn().mockResolvedValue({
      suite: { id: "suite-1", name: "黄金集" },
      cases: [
        {
          id: "c1",
          suite_id: "suite-1",
          case_key: "smoke_01",
          split: "dev",
          schema_version: "3",
          required_capabilities: [],
          turns: [{ role: "user", content: "ping" }],
          simulation: null,
          expectations: {},
          metrics: ["completion"],
          metadata: {},
          updated_at: null,
        },
      ],
      versions: [
        {
          id: "ver-1",
          suite_id: "suite-1",
          version_num: 1,
          content_hash: "abcdef123456",
          case_count: 1,
          published_by: "u1",
          published_at: null,
        },
      ],
    }),
  };
});

const samplePatrol: PatrolScheduleItem = {
  id: "patrol-1",
  name: "凌晨核心冒烟巡检",
  suite_id: "suite-1",
  suite_name: "黄金回归集",
  version_id: null,
  version_policy: "latest_published",
  owner_project_id: "proj-1",
  target_project_id: "proj-1",
  target_project_name: "隔离靶场",
  target_graph_id: "dearflow_agent",
  target_agent_id: "agent-1",
  target_agent_name: "Dear Agent",
  target_model_id: "model-1",
  target_model_name: "DeepSeek V4 Flash",
  judge_model_id: "model-1",
  judge_model_name: "DeepSeek V4 Flash",
  embedding_model_id: null,
  case_keys: ["smoke_01"],
  concurrency: 2,
  repeat_k: 1,
  skip_incompatible: true,
  confirm_non_sandbox: true,
  cron_expr: "0 3 * * *",
  timezone: "Asia/Shanghai",
  enabled: true,
  concurrency_policy: "forbid",
  gate_config: { min_tsr: 0.7, regression_drop_threshold: 0.05 },
  notify_channels: [],
  notify_on_recovery: true,
  next_run_at: "2026-11-29T03:00:00+08:00",
  last_triggered_at: "2026-11-28T03:00:00+08:00",
  last_status: "degraded",
  last_message: "TSR 从 100% 跌至 80%",
  consecutive_failures: 1,
  last_run_id: "run-patrol-1",
  last_run_status: "completed",
  last_run_gate_exit_code: 0,
  last_run_score: 0.8,
  created_by: "u1",
  created_at: null,
  updated_at: null,
};

describe("PatrolSchedules components", () => {
  it("renders patrol schedule cards and emits trigger/toggle/viewRun actions", async () => {
    const wrapper = mount(PatrolSchedulesPanel, {
      props: {
        patrols: [samplePatrol],
        runs: [
          {
            id: "run-patrol-1",
            suite_id: "suite-1",
            version_id: "ver-1",
            owner_project_id: "proj-1",
            target_project_id: "proj-1",
            target_graph_id: "dearflow_agent",
            target_agent_id: "agent-1",
            target_model_id: "model-1",
            judge_model_id: null,
            embedding_model_id: null,
            matrix_group_id: null,
            trigger_type: "patrol",
            patrol_schedule_id: "patrol-1",
            patrol_name: "凌晨核心冒烟巡检",
            mode: "regression",
            concurrency: 2,
            repeat_k: 1,
            status: "completed",
            gate_exit_code: 0,
            summary_metrics: { overall_score: 0.8 },
            created_by: "u1",
            created_at: null,
            finished_at: null,
          } satisfies EvalRunItem,
        ],
        canManage: true,
      },
      global: {
        stubs: {
          MetricCard: {
            template: "<div class='metric'>{{ label }}:{{ value }}</div>",
            props: ["label", "value", "hint", "icon", "tone"],
          },
        },
      },
    });

    expect(wrapper.text()).toContain("凌晨核心冒烟巡检");
    expect(wrapper.text()).toContain("质量退化预警");
    expect(wrapper.text()).toContain("连续异常 1 次");
    expect(wrapper.text()).toContain("0 3 * * *");

    const buttons = wrapper.findAll("button");
    const triggerBtn = buttons.find((b) => b.text().includes("立即试跑"));
    await triggerBtn?.trigger("click");
    expect(wrapper.emitted("triggerNow")?.[0]?.[0]).toMatchObject({
      id: "patrol-1",
    });

    const viewBtn = buttons.find((b) => b.text().includes("最近结果"));
    await viewBtn?.trigger("click");
    expect(wrapper.emitted("viewRun")?.[0]).toEqual(["run-patrol-1"]);
  });

  it("previews cron next runs and submits create payload in PatrolScheduleModal", async () => {
    const previewCron = vi.fn().mockResolvedValue({
      cron_expr: "0 3 * * *",
      timezone: "Asia/Shanghai",
      next_runs: ["2026-11-29T03:00:00+08:00", "2026-11-30T03:00:00+08:00"],
      next_runs_utc: [],
    });
    const wrapper = mount(PatrolScheduleModal, {
      props: {
        show: false,
        projectId: "proj-1",
        editingPatrol: null,
        suites: [
          {
            id: "suite-1",
            name: "黄金回归集",
            description: "",
            suite_type: "golden",
            owner_project_id: "proj-1",
            source_project_id: null,
            default_graph_id: "dearflow_agent",
            created_by: "u1",
            archived_at: null,
            created_at: null,
            updated_at: null,
          } satisfies EvalSuiteItem,
        ],
        projectOptions: [{ label: "隔离靶场", value: "proj-1" }],
        agentOptions: [{ label: "Dear Agent", value: "agent-1" }],
        modelOptions: [{ label: "DeepSeek V4", value: "model-1" }],
        defaultModelId: "model-1",
        previewCron,
      },
      global: {
        stubs: {
          BaseDialog: {
            template: "<div v-if='show'><slot /></div>",
            props: ["show", "title", "width"],
          },
          BaseSelect: {
            template: "<select :value='modelValue' />",
            props: ["modelValue", "options", "disabled"],
          },
        },
      },
    });

    await wrapper.setProps({ show: true });
    await flushPromises();

    expect(previewCron).toHaveBeenCalledWith("0 3 * * *", "Asia/Shanghai");
    expect(wrapper.text()).toContain("未来 5 次执行");
    expect(wrapper.text()).toContain("smoke_01");

    const nameInput = wrapper.find("input[type='text']");
    await nameInput.setValue("每日夜间巡检");
    const submitBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("创建巡检规则"));
    await submitBtn?.trigger("click");

    const saved = wrapper.emitted("save");
    expect(saved).toBeTruthy();
    expect(saved?.[0]?.[0]).toMatchObject({
      name: "每日夜间巡检",
      suite_id: "suite-1",
      version_policy: "latest_published",
      cron_expr: "0 3 * * *",
    });
  });

  it("filters patrol runs in RunResultsPanel", async () => {
    const baseRun: EvalRunItem = {
      id: "run-manual",
      suite_id: "suite-1",
      version_id: "ver-1",
      owner_project_id: "proj-1",
      target_project_id: "proj-1",
      target_graph_id: "dearflow_agent",
      target_agent_id: "agent-1",
      target_model_id: "model-1",
      judge_model_id: null,
      embedding_model_id: null,
      matrix_group_id: null,
      trigger_type: "manual",
      mode: "regression",
      concurrency: 2,
      repeat_k: 1,
      status: "completed",
      gate_exit_code: 0,
      summary_metrics: { overall_score: 0.9 },
      created_by: "u1",
      created_at: "2026-11-28T01:00:00Z",
      finished_at: "2026-11-28T01:02:00Z",
    };
    const patrolRun: EvalRunItem = {
      ...baseRun,
      id: "run-patrol",
      trigger_type: "patrol",
      patrol_schedule_id: "patrol-1",
      patrol_name: "凌晨巡检",
    };

    const wrapper = mount(RunResultsPanel, {
      props: {
        runs: [baseRun, patrolRun],
        suites: [],
        activeRun: null,
        runCases: [],
      },
      global: {
        stubs: {
          MetricCard: { template: "<div />", props: ["label", "value"] },
        },
      },
    });

    expect(wrapper.text()).toContain("定时巡检 · 凌晨巡检");
    const patrolFilterBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("定时巡检 (1)"));
    await patrolFilterBtn?.trigger("click");
    expect(wrapper.text()).toContain("run-patr");
    expect(wrapper.text()).not.toContain("run-manu");
  });
});

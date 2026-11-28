import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import CaseEditorPanel from "@/modules/evaluation/components/CaseEditorPanel.vue";
import LaunchRunModal from "@/modules/evaluation/components/LaunchRunModal.vue";
import type {
  EvalCaseItem,
  EvalSuiteItem,
  EvalSuiteVersionSummary,
  ReadinessResult,
} from "@/services/evaluation/studio";

const mockSuite: EvalSuiteItem = {
  id: "suite-1",
  name: "测试题库",
  description: "desc",
  suite_type: "golden",
  owner_project_id: "p-1",
  source_project_id: null,
  default_graph_id: "dearflow_agent",
  created_by: "u1",
  archived_at: null,
  created_at: null,
  updated_at: null,
  case_count: 2,
  runs_count: 0,
  best_score: null,
  sample_cases: [],
  latest_version: null,
};

const mockCases: EvalCaseItem[] = [
  {
    id: "case-1-id",
    suite_id: "suite-1",
    case_key: "case_001",
    split: "dev",
    schema_version: "3",
    required_capabilities: [],
    turns: [{ role: "user", content: "第一题问题" }],
    simulation: null,
    expectations: { expected_answer: "第一题参考答案" },
    metrics: [{ name: "completion" }],
    metadata: {},
    updated_at: null,
  },
  {
    id: "case-2-id",
    suite_id: "suite-1",
    case_key: "case_002",
    split: "holdout",
    schema_version: "3",
    required_capabilities: [],
    turns: [{ role: "user", content: "第二题问题" }],
    simulation: null,
    expectations: { expected_answer: "第二题参考答案" },
    metrics: [{ name: "completion" }],
    metadata: {},
    updated_at: null,
  },
];

const mockVersions: EvalSuiteVersionSummary[] = [
  {
    id: "ver-1",
    version_num: 1,
    content_hash: "abcdef123456",
    case_count: 2,
    created_at: "2026-11-28",
  },
];

describe("Selective Evaluation Components", () => {
  describe("CaseEditorPanel", () => {
    it("renders row checkboxes and emits update:selectedCaseKeys on toggle", async () => {
      const wrapper = mount(CaseEditorPanel, {
        props: {
          suites: [mockSuite],
          suite: mockSuite,
          cases: mockCases,
          versions: mockVersions,
          selectedCaseKeys: [],
        },
        global: {
          stubs: {
            BaseButton: {
              template: "<button @click=\"$emit('click')\"><slot /></button>",
            },
            BaseInput: { template: "<input />" },
            BaseSelect: { template: "<div />" },
            SurfaceCard: { template: "<div><slot /></div>" },
            StatusPill: { template: "<span><slot /></span>" },
            EmptyState: { template: "<div />" },
            CaseAdvancedDrawer: { template: "<div />" },
          },
        },
      });

      const rowCheckboxes = wrapper.findAll('tbody input[type="checkbox"]');
      expect(rowCheckboxes.length).toBe(2);

      // 勾选第一行
      await rowCheckboxes[0].setValue(true);
      expect(wrapper.emitted("update:selectedCaseKeys")).toBeTruthy();
      expect(wrapper.emitted("update:selectedCaseKeys")![0]).toEqual([
        ["case_001"],
      ]);
    });

    it("handles select all, invert and clear selection", async () => {
      const wrapper = mount(CaseEditorPanel, {
        props: {
          suites: [mockSuite],
          suite: mockSuite,
          cases: mockCases,
          versions: mockVersions,
          selectedCaseKeys: ["case_001"],
        },
        global: {
          stubs: {
            BaseButton: {
              template: "<button @click=\"$emit('click')\"><slot /></button>",
            },
            BaseInput: { template: "<input />" },
            BaseSelect: { template: "<div />" },
            SurfaceCard: { template: "<div><slot /></div>" },
            StatusPill: { template: "<span><slot /></span>" },
            EmptyState: { template: "<div />" },
            CaseAdvancedDrawer: { template: "<div />" },
          },
        },
      });

      // 验证提示与按钮文案联动
      expect(wrapper.text()).toContain("已勾选 1 道考题用于局部评测打擂");
      expect(wrapper.text()).toContain("发起评测打擂 (1 题) →");

      // 反选测试
      const invertBtn = wrapper
        .findAll("button")
        .find((b) => b.text().includes("反选"));
      expect(invertBtn).toBeDefined();
      await invertBtn!.trigger("click");
      expect(wrapper.emitted("update:selectedCaseKeys")).toBeTruthy();
      const emittedKeys = wrapper.emitted(
        "update:selectedCaseKeys",
      )![0][0] as string[];
      expect(emittedKeys).toEqual(["case_002"]);

      // 清空测试
      const clearBtn = wrapper
        .findAll("button")
        .find((b) => b.text().includes("清空选择"));
      expect(clearBtn).toBeDefined();
      await clearBtn!.trigger("click");
      expect(wrapper.emitted("update:selectedCaseKeys")![1]).toEqual([[]]);
    });
  });

  describe("LaunchRunModal", () => {
    const mockReadiness: ReadinessResult = {
      pass: true,
      suite_id: "suite-1",
      target_project_id: "p-target",
      agent_id: "agent-1",
      model_id: "model-1",
      judge_model_id: "model-1",
      embedding_model_id: null,
      is_sandbox: true,
      incompatible_cases: [],
      target_project_name: "靶场项目",
      agent_graph_id: "dearflow_agent",
      eval_contract: {
        package_digest: "pkg-123",
        git_commit: "abc",
        available: true,
      },
    };

    it("displays selected cases info card and passes case_keys to readiness and launch", async () => {
      const wrapper = mount(LaunchRunModal, {
        props: {
          show: false,
          suite: mockSuite,
          versions: mockVersions,
          projectOptions: [{ label: "靶场项目", value: "p-target" }],
          agentOptions: [
            { label: "Dear Agent (dearflow_agent)", value: "agent-1" },
          ],
          modelOptions: [{ label: "Model 1", value: "model-1" }],
          defaultModelId: "model-1",
          readiness: mockReadiness,
          selectedCaseKeys: ["case_001"],
        },
        global: {
          stubs: {
            BaseButton: {
              template: "<button @click=\"$emit('click')\"><slot /></button>",
            },
            BaseDialog: {
              template: '<div v-if="show"><slot /></div>',
              props: ["show"],
            },
            BaseSelect: { template: "<div />" },
            StateBanner: { template: "<div><slot /></div>" },
          },
        },
      });

      // 打开弹窗触发初始化与 readiness
      await wrapper.setProps({ show: true });

      // 验证局部打擂提示
      expect(wrapper.text()).toContain("已选局部打擂用例：");
      expect(wrapper.text()).toContain("case_001");
      expect(wrapper.text()).toContain("仅运行勾选题目");

      // 验证 checkReadiness 是否透传了 case_keys
      expect(wrapper.emitted("checkReadiness")).toBeTruthy();
      const lastCheck = wrapper.emitted("checkReadiness")!.slice(-1)[0][0] as {
        case_keys?: string[];
      };
      expect(lastCheck.case_keys).toEqual(["case_001"]);

      // 触发开考
      const launchBtn = wrapper
        .findAll("button")
        .find((b) => b.text().includes("开始并发评测"));
      expect(launchBtn).toBeDefined();
      await launchBtn!.trigger("click");

      expect(wrapper.emitted("launch")).toBeTruthy();
      const launchPayload = wrapper.emitted("launch")![0][0] as {
        case_keys?: string[];
      };
      expect(launchPayload.case_keys).toEqual(["case_001"]);
    });
  });
});

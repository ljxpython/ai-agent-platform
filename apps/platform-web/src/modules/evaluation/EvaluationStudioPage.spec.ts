import { mount } from "@vue/test-utils";
import { ref } from "vue";
import { describe, expect, it, vi } from "vitest";
import EvaluationStudioPage from "@/modules/evaluation/EvaluationStudioPage.vue";
import { useEvalExpertChat } from "@/modules/evaluation/composables/useEvalExpertChat";
import { pickPreferredDeepSeekModelId } from "@/services/evaluation/studio";
import type { RuntimeModelItem } from "@/types/management";

vi.mock("vue-router", () => ({
  useRoute: () => ({
    params: { projectId: "proj-1", itemId: "" },
    meta: { evalTab: "panorama" },
  }),
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/services/projects/projects.service", () => ({
  listRuntimeProjects: vi
    .fn()
    .mockResolvedValue([{ id: "proj-1", name: "测试隔离靶场" }]),
}));

vi.mock("@/services/agents/agents.service", () => ({
  listAgents: vi.fn().mockResolvedValue({
    items: [{ id: "agent-1", name: "Dear Agent", graph_id: "dearflow_agent" }],
  }),
}));

vi.mock("@/services/runtime/runtime.service", () => ({
  listRuntimeModels: vi.fn().mockResolvedValue({
    count: 2,
    models: [
      {
        id: "broken-1",
        display_name: "🔥 故障测试主模型",
        provider: "openai",
        model: "broken-primary-model",
        enabled: true,
      },
      {
        id: "xiaok-ds",
        display_name: "deepseek-v4.1-flash",
        provider: "xiaok",
        model: "deepseek-v4.1-flash",
        enabled: true,
      },
    ],
  }),
}));

vi.mock("@/services/evaluation/studio", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/services/evaluation/studio")>();
  return {
    ...actual,
    listSuites: vi.fn().mockResolvedValue([
      {
        id: "suite-1",
        name: "多图回归黄金集",
        description: "测试多 Agent 与 TTFT",
        suite_type: "golden",
        owner_project_id: "proj-1",
        source_project_id: null,
        default_graph_id: "dearflow_agent",
        created_by: "u1",
        archived_at: null,
        created_at: null,
        updated_at: null,
        case_count: 3,
        runs_count: 1,
        best_score: 0.92,
        sample_cases: [
          {
            id: "sc-1",
            case_key: "case_001",
            split: "dev",
            mode: "fixed",
            question: "如何核对成本？",
            ground_truth: "按窗口核算",
            metrics_count: 1,
          },
        ],
        latest_version: null,
      },
    ]),
    listRuns: vi.fn().mockResolvedValue([]),
    listPatrols: vi.fn().mockResolvedValue([]),
    createSuite: vi.fn(),
    getSuiteDetail: vi.fn(),
    upsertCase: vi.fn(),
    deleteCase: vi.fn(),
    publishSuiteVersion: vi.fn(),
    checkReadiness: vi.fn(),
    createRun: vi.fn(),
    getRunDetail: vi.fn(),
    controlRun: vi.fn(),
    compareRuns: vi.fn(),
    submitHumanReview: vi.fn(),
  };
});

describe("EvaluationStudioPage", () => {
  it("prioritizes enabled xiaok DeepSeek model over fault-injection test models", () => {
    const models = [
      {
        id: "broken-id",
        display_name: "🔥 故障测试主模型 (模拟宕机/断网)",
        provider: "openai",
        base_url: "http://invalid",
        protocol: "openai-compatible",
        model: "broken-primary-model",
        enabled: true,
        credential_configured: true,
      },
      {
        id: "qwen-id",
        display_name: "qwen3.8-flash",
        provider: "maomaoai",
        base_url: "http://x",
        protocol: "openai-compatible",
        model: "qwen3.8-flash",
        enabled: true,
        credential_configured: true,
      },
      {
        id: "xiaok-ds-id",
        display_name: "deepseek-v4.1-flash",
        provider: "xiaok",
        base_url: "http://xiaok",
        protocol: "openai-compatible",
        model: "deepseek-v4.1-flash",
        enabled: true,
        credential_configured: true,
      },
    ] satisfies RuntimeModelItem[];

    expect(pickPreferredDeepSeekModelId(models)).toBe("xiaok-ds-id");
  });

  it("renders LightRAG-style panorama cards and metrics", async () => {
    const wrapper = mount(EvaluationStudioPage, {
      global: {
        stubs: {
          PageHeader: {
            template: "<div><h1>{{ title }}</h1><slot name='actions' /></div>",
            props: ["title", "description", "eyebrow"],
          },
          MetricCard: {
            template: "<div class='metric'>{{ label }}: {{ value }}</div>",
            props: ["label", "value", "hint", "icon", "tone"],
          },
          BaseSelect: {
            template: "<div class='base-select' />",
            props: ["modelValue", "options", "placeholder"],
          },
          BaseDialog: {
            template: "<div v-if='show'><slot /></div>",
            props: ["show", "title", "width"],
          },
          BaseDrawer: {
            template: "<div v-if='show'><slot /></div>",
            props: ["show", "title", "width"],
          },
          BaseButton: {
            template: "<button @click=\"$emit('click')\"><slot /></button>",
          },
          BaseInput: { template: "<input />" },
          SurfaceCard: { template: "<div><slot /></div>" },
          StatusPill: { template: "<span><slot /></span>", props: ["tone"] },
          StateBanner: {
            template: "<div>{{ title }}</div>",
            props: ["title", "description", "variant"],
          },
          EmptyState: {
            template: "<div>{{ title }}</div>",
            props: ["title", "description"],
          },
          MarkdownContent: {
            template: "<div>{{ content }}</div>",
            props: ["content"],
          },
          PickSessionMaterials: { template: "<div />" },
        },
      },
    });
    await new Promise((resolve) => setTimeout(resolve, 10));
    expect(wrapper.text()).toContain("独立评测工坊与白盒诊断平台");
    expect(wrapper.text()).toContain("多图回归黄金集");
    expect(wrapper.text()).toContain("如何核对成本？");
  });

  it("supports queuing multiple mixed reference files and deduplicating by filename", () => {
    const chat = useEvalExpertChat(
      ref("proj-1"),
      ref("eval_copilot"),
      ref("model-1"),
    );
    const md = new File(["# rule"], "rule.md", { type: "text/markdown" });
    const csv = new File(["a,b\n1,2\n"], "sample.csv", { type: "text/csv" });
    const dup = new File(["# dup"], "rule.md", { type: "text/markdown" });
    chat.addPendingFiles([md, csv, dup]);
    expect(chat.pendingFiles.value.map((f) => f.name)).toEqual([
      "rule.md",
      "sample.csv",
    ]);
    chat.removePendingFile("rule.md");
    expect(chat.pendingFiles.value.map((f) => f.name)).toEqual(["sample.csv"]);
    chat.reset();
    expect(chat.pendingFiles.value).toEqual([]);
  });

  it("loads expert thread history and restores messages when selecting a thread", async () => {
    const studioMod = await import("@/services/evaluation/studio");
    vi.spyOn(studioMod, "listExpertThreads").mockResolvedValueOnce([
      {
        thread_id: "th-1",
        title: "历史多轮题讨论",
        status: "idle",
      },
    ]);
    vi.spyOn(studioMod, "getExpertThreadState").mockResolvedValueOnce({
      thread_id: "th-1",
      status: "idle",
      interrupts: [],
      messages: [
        { id: "u1", role: "user", content: "生成一道退款多轮题" },
        { id: "a1", role: "assistant", content: "已落库 COP-NL-01" },
      ],
    });
    const chat = useEvalExpertChat(
      ref("proj-1"),
      ref("eval_copilot"),
      ref("model-1"),
    );
    await chat.initForContext("suite-1");
    expect(chat.threads.value).toHaveLength(1);
    await chat.selectThread("th-1", "suite-1");
    expect(chat.threadId.value).toBe("th-1");
    expect(chat.messages.value).toHaveLength(2);
    expect(chat.messages.value[1]?.content).toBe("已落库 COP-NL-01");
  });
});

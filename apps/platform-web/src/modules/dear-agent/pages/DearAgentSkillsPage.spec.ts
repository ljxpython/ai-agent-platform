import { describe, expect, it, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { ref } from "vue";
import DearAgentSkillsPage from "./DearAgentSkillsPage.vue";
import * as skillsService from "@/services/dear-agent/skills.service";

const mockActiveProjectId = ref("proj-1");
const mockActiveThreadId = ref("th-1");
const mockHasThreads = ref(true);
const mockThreads = ref([{ thread_id: "th-1", metadata: { title: "会话1", graph_id: "dearflow_agent" } }]);
const mockCreateInitialThread = vi.fn();
const mockCanWrite = ref(true);

vi.mock("@/composables/useAuthorization", () => ({
  useAuthorization: () => ({
    can: () => mockCanWrite.value,
  }),
}));

vi.mock("../composables/useDearGovernanceContext", () => ({
  useDearGovernanceContext: () => ({
    activeProject: ref({ id: "proj-1", name: "测试项目" }),
    activeProjectId: mockActiveProjectId,
    threads: mockThreads,
    activeThreadId: mockActiveThreadId,
    hasThreads: mockHasThreads,
    loading: ref(false),
    isCreatingThread: ref(false),
    switchThread: vi.fn(),
    createInitialThread: mockCreateInitialThread,
  }),
}));

vi.mock("@/services/dear-agent/skills.service", async () => {
  const actual = await vi.importActual<typeof skillsService>("@/services/dear-agent/skills.service");
  return {
    ...actual,
    listCustomSkills: vi.fn(),
    uploadCandidateSkillPackage: vi.fn(),
    activateSkillVersion: vi.fn(),
    revokeSkillVersion: vi.fn(),
  };
});

describe("DearAgentSkillsPage.vue", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCanWrite.value = true;
    mockHasThreads.value = true;
    mockActiveThreadId.value = "th-1";
  });

  it("默认展示 8 大官方平台公共技能卡片", async () => {
    (skillsService.listCustomSkills as any).mockResolvedValueOnce([]);

    const wrapper = mount(DearAgentSkillsPage);
    await flushPromises();

    expect(wrapper.text()).toContain("Skills 技能版本治理");
    expect(wrapper.text()).toContain("平台公共技能");
    expect(wrapper.text()).toContain("深度研究 (Deep Research)");
    expect(wrapper.text()).toContain("学术论文审查 (Academic Paper Review)");
    expect(wrapper.text()).toContain("已通过验收");
  });

  it("切换到自定义技能专区并展开文件清单", async () => {
    (skillsService.listCustomSkills as any).mockResolvedValue([
      {
        slug: "custom-sql-tool",
        description: "自定义 SQL 审查工具",
        digest: "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9",
        revision: 1,
        status: "candidate",
        warnings: [],
        manifest: [
          { path: "SKILL.md", sha256: "hash123456789012" },
          { path: "scripts/run.py", sha256: "hash987654321012" },
        ],
        review: { passed: true },
        evaluation: { passed: true },
      },
    ]);

    const wrapper = mount(DearAgentSkillsPage);
    await flushPromises();

    // 切换到自定义专区
    const customTabBtn = wrapper.findAll("button").find((b) => b.text().includes("自定义版本治理"));
    expect(customTabBtn).toBeDefined();
    await customTabBtn!.trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("custom-sql-tool");
    expect(wrapper.text()).toContain("待定候选 (Candidate)");
    expect(wrapper.text()).toContain("✓ 通过");

    // 点击文件清单
    const manifestBtn = wrapper.findAll("button").find((b) => b.text().includes("文件清单"));
    expect(manifestBtn).toBeDefined();
    await manifestBtn!.trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("Package Manifest 文件列表");
    expect(wrapper.text()).toContain("SKILL.md");
    expect(wrapper.text()).toContain("scripts/run.py");
  });

  it("当 review 和 evaluation 均通过时允许点击启用版本", async () => {
    (skillsService.listCustomSkills as any).mockResolvedValue([
      {
        slug: "custom-sql-tool",
        description: "自定义 SQL 审查工具",
        digest: "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9",
        revision: 1,
        status: "candidate",
        warnings: [],
        manifest: [],
        review: { passed: true },
        evaluation: { passed: true },
      },
    ]);
    (skillsService.activateSkillVersion as any).mockResolvedValueOnce({
      slug: "custom-sql-tool",
      status: "active",
      revision: 2,
    });

    const wrapper = mount(DearAgentSkillsPage);
    await flushPromises();

    const customTabBtn = wrapper.findAll("button").find((b) => b.text().includes("自定义版本治理"));
    await customTabBtn!.trigger("click");
    await flushPromises();

    const activateBtn = wrapper.findAll("button").find((b) => b.text().includes("启用版本"));
    expect(activateBtn).toBeDefined();
    expect(activateBtn!.attributes("disabled")).toBeUndefined();

    await activateBtn!.trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("启用技能版本确认");
    const confirmBtn = wrapper.findAll("button").find((b) => b.text().includes("确认启用"));
    expect(confirmBtn).toBeDefined();
    await confirmBtn!.trigger("click");
    await flushPromises();

    expect(skillsService.activateSkillVersion).toHaveBeenCalledWith(
      "proj-1",
      "th-1",
      "custom-sql-tool",
      "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9",
      1
    );
  });

  it("无写权限时展示只读提示并禁用上传按钮", async () => {
    mockCanWrite.value = false;
    (skillsService.listCustomSkills as any).mockResolvedValueOnce([]);

    const wrapper = mount(DearAgentSkillsPage);
    await flushPromises();

    expect(wrapper.text()).toContain("当前项目处于只读模式（缺少 project.runtime.write 权限）");
    const uploadBtn = wrapper.findAll("button").find((b) => b.text().includes("导入候选 ZIP"));
    expect(uploadBtn?.attributes("disabled")).toBeDefined();
  });
});

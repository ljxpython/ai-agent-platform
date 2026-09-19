import { describe, expect, it, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { ref } from "vue";
import DearAgentSkillsPage from "./DearAgentSkillsPage.vue";
import * as skillsService from "@/services/dear-agent/skills.service";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const mockActiveProjectId = ref("proj-1");
const mockActiveProject = ref({ id: "proj-1", name: "测试项目" });
const mockCanWrite = ref(true);

vi.mock("@/composables/useAuthorization", () => ({
  useAuthorization: () => ({
    can: () => mockCanWrite.value,
  }),
}));

vi.mock("@/composables/useWorkspaceProjectContext", () => ({
  useWorkspaceProjectContext: () => ({
    activeProject: mockActiveProject,
    activeProjectId: mockActiveProjectId,
  }),
}));

vi.mock("@/services/dear-agent/skills.service", async () => {
  const actual = await vi.importActual<typeof skillsService>("@/services/dear-agent/skills.service");
  return {
    ...actual,
    getDearSkills: vi.fn(),
    getDearSkillDetail: vi.fn(),
    getDearSkillContent: vi.fn(),
    createCustomSkill: vi.fn(),
    updateCustomSkill: vi.fn(),
    toggleCustomSkill: vi.fn(),
    deleteCustomSkill: vi.fn(),
  };
});

describe("DearAgentSkillsPage.vue (去会话化与全新管理)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCanWrite.value = true;
    mockActiveProjectId.value = "proj-1";
    mockActiveProject.value = { id: "proj-1", name: "测试项目" };
  });

  function getMockSkillsList(): skillsService.DearSkillsListResponse {
    return {
      items: [
        {
          source: "public",
          slug: "deep-research",
          name: "深度研究 (Deep Research)",
          description: "多步规划与深度研究",
          revision: "rev-pub-1",
          updated_at: null,
          backend_verified: true,
          recommendable: true,
        },
        {
          source: "custom",
          slug: "custom-sql-tool",
          name: "自定义 SQL 审查工具",
          description: "自定义 SQL 检查与清洗",
          digest: "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9",
          revision: "rev-cus-1",
          origin: "explicit-management",
          warnings: [],
          enabled: true,
          updated_at: "2026-09-19T08:00:00Z",
        },
      ],
      capabilities: {
        can_read: true,
        can_write: true,
        custom_management_enabled: true,
      },
      limits: {
        package_bytes: 1048576,
        unpacked_bytes: 1048576,
        file_bytes: 262144,
        entries: 100,
        custom_skills: 50,
      },
    };
  }

  it("默认加载并展示公共技能卡片，且无会话下拉框", async () => {
    (skillsService.getDearSkills as any).mockResolvedValueOnce(getMockSkillsList());

    const wrapper = mount(DearAgentSkillsPage);
    await flushPromises();

    expect(wrapper.text()).toContain("Skills 技能管理");
    expect(wrapper.text()).toContain("测试项目");
    // 不应存在老旧的“治理上下文”
    expect(wrapper.text()).not.toContain("治理上下文");
    // 渲染公共技能卡片
    expect(wrapper.text()).toContain("深度研究 (Deep Research)");
    expect(wrapper.text()).toContain("已通过验收");
  });

  it("切换到自定义技能专区并展示自定义卡片与状态", async () => {
    (skillsService.getDearSkills as any).mockResolvedValueOnce(getMockSkillsList());

    const wrapper = mount(DearAgentSkillsPage);
    await flushPromises();

    const customTabBtn = wrapper.findAll("button").find((b) => b.text().includes("自定义技能管理"));
    expect(customTabBtn).toBeDefined();
    await customTabBtn!.trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("自定义 SQL 审查工具");
    expect(wrapper.text()).toContain("启用中 (Active)");
    expect(wrapper.text()).toContain("b94d27b9934d");
  });

  it("启停 Switch 操作正确调用 toggleCustomSkill", async () => {
    const mockList = getMockSkillsList();
    (skillsService.getDearSkills as any).mockResolvedValueOnce(mockList);
    const toggledSkill: skillsService.SkillDetail = {
      ...mockList.items[1] as skillsService.CustomSkillItem,
      enabled: false,
      revision: "rev-cus-2",
      manifest: [{ path: "SKILL.md", size: 100, readable: true }],
    };
    (skillsService.toggleCustomSkill as any).mockResolvedValueOnce(toggledSkill);

    const wrapper = mount(DearAgentSkillsPage);
    await flushPromises();

    // 切换到自定义专区
    const customTabBtn = wrapper.findAll("button").find((b) => b.text().includes("自定义技能管理"));
    await customTabBtn!.trigger("click");
    await flushPromises();

    // 找到 switch 开关
    const switchBtn = wrapper.find('button[role="switch"]');
    expect(switchBtn.exists()).toBe(true);
    await switchBtn.trigger("click");
    await flushPromises();

    expect(skillsService.toggleCustomSkill).toHaveBeenCalledWith(
      "proj-1",
      "custom-sql-tool",
      false, // 从 true 变为 false
      "rev-cus-1",
    );
  });

  it("点击查看详情打开 BaseDrawer 并默认加载 SKILL.md", async () => {
    const mockList = getMockSkillsList();
    (skillsService.getDearSkills as any).mockResolvedValueOnce(mockList);
    const mockDetail: skillsService.SkillDetail = {
      ...mockList.items[0] as skillsService.PublicSkillItem,
      manifest: [
        { path: "SKILL.md", size: 50, readable: true },
        { path: "run.py", size: 200, readable: true },
      ],
    };
    (skillsService.getDearSkillDetail as any).mockResolvedValueOnce(mockDetail);
    (skillsService.getDearSkillContent as any).mockResolvedValueOnce({
      path: "SKILL.md",
      content: "# Deep Research Guide",
      revision: "rev-pub-1",
    });

    const wrapper = mount(DearAgentSkillsPage);
    await flushPromises();

    const detailBtn = wrapper.findAll("button").find((b) => b.text().includes("查看详情"));
    expect(detailBtn).toBeDefined();
    await detailBtn!.trigger("click");
    await flushPromises();

    expect(skillsService.getDearSkillDetail).toHaveBeenCalledWith(
      "proj-1",
      "public",
      "deep-research",
    );
    expect(skillsService.getDearSkillContent).toHaveBeenCalledWith(
      "proj-1",
      "public",
      "deep-research",
      "SKILL.md",
      "rev-pub-1",
    );

    // 测试侧边栏收起与展开（BaseDrawer teleport 到了 body）
    const collapseBtn = document.body.querySelector<HTMLButtonElement>("button[title='收起文件清单']");
    expect(collapseBtn).toBeTruthy();
    collapseBtn!.click();
    await flushPromises();

    // 收起后应展示展开按钮
    const expandBtn = document.body.querySelector<HTMLButtonElement>("button[title='展开文件清单']");
    expect(expandBtn).toBeTruthy();
    expandBtn!.click();
    await flushPromises();

    expect(document.body.querySelector("button[title='收起文件清单']")).toBeTruthy();
    wrapper.unmount();
  });

  it("点击删除按钮弹出二次确认框，确认后调用 deleteCustomSkill", async () => {
    const mockList = getMockSkillsList();
    (skillsService.getDearSkills as any).mockResolvedValueOnce(mockList);
    (skillsService.deleteCustomSkill as any).mockResolvedValueOnce(undefined);
    (skillsService.getDearSkills as any).mockResolvedValueOnce({
      ...mockList,
      items: [mockList.items[0]],
    });

    const wrapper = mount(DearAgentSkillsPage, { attachTo: document.body });
    await flushPromises();

    // 切换到自定义
    const customTabBtn = wrapper.findAll("button").find((b) => b.text().includes("自定义技能管理"));
    await customTabBtn!.trigger("click");
    await flushPromises();

    const deleteBtn = wrapper.findAll("button").find((b) => b.text().includes("删除"));
    expect(deleteBtn).toBeDefined();
    await deleteBtn!.trigger("click");
    await flushPromises();

    // 确认弹窗应该处于可见状态 (Teleport 到 document.body)
    expect(document.body.textContent).toContain("彻底删除自定义技能确认");

    // 触发删除确认
    const confirmBtn = [...document.querySelectorAll("button")].find((b) => b.textContent?.includes("确认删除"));
    expect(confirmBtn).toBeDefined();
    confirmBtn!.click();
    await flushPromises();

    expect(skillsService.deleteCustomSkill).toHaveBeenCalledWith(
      "proj-1",
      "custom-sql-tool",
      "rev-cus-1",
    );
    wrapper.unmount();
  });

  it("只读用户下展示只读横幅且禁用操作按钮", async () => {
    mockCanWrite.value = false;
    const mockList = getMockSkillsList();
    (skillsService.getDearSkills as any).mockResolvedValueOnce({
      ...mockList,
      capabilities: {
        can_read: true,
        can_write: false,
        custom_management_enabled: true,
      },
    });

    const wrapper = mount(DearAgentSkillsPage);
    await flushPromises();

    expect(wrapper.text()).toContain("当前项目处于只读模式");
    const importBtn = wrapper.findAll("button").find((b) => b.text().includes("导入技能包"));
    expect(importBtn?.attributes("disabled")).toBeDefined();
  });
});

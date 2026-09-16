import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import DearAgentArtifactsPage from "./DearAgentArtifactsPage.vue";

const activeProjectIdRef = ref("proj-1");

vi.mock("vue-router", () => ({
  useRoute: () => ({ params: { projectId: "proj-1" }, query: { threadId: "th-1" }, path: "/workspace/projects/proj-1/dear-agent-artifacts" }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

vi.mock("@/composables/useWorkspaceProjectContext", () => ({
  useWorkspaceProjectContext: () => ({
    activeProjectId: activeProjectIdRef,
    activeProject: ref({ id: "proj-1", name: "测试项目" }),
  }),
}));

vi.mock("@/composables/useAuthorization", () => ({
  useAuthorization: () => ({ can: () => true }),
}));

const mockHistoryData = [
  {
    checkpoint_id: "cp-1",
    values: {
      messages: [
        {
          id: "msg-1",
          type: "ai",
          content: "已生成报告和附件，请查收：/workspace/outputs/analysis_report.md",
          contentBlocks: [
            {
              type: "text",
              text: "已生成文件",
              extras: {
                runtime_file: {
                  version: 1,
                  path: "/workspace/outputs/sales_data.xlsx",
                  file_name: "sales_data.xlsx",
                  mime_type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                  size_bytes: 4096,
                  sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                },
              },
            },
            {
              type: "text",
              text: "幻灯片交付",
              extras: {
                runtime_file: {
                  version: 1,
                  path: "/workspace/outputs/presentation.pptx",
                  file_name: "presentation.pptx",
                  mime_type: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                  size_bytes: 10240,
                  sha256: "abc1234567890123456789012345678901234567890123456789012345678901",
                },
              },
            },
          ],
        },
      ],
    },
    metadata: { step: 3 },
  },
];

vi.mock("@/services/threads/session.service", () => ({
  createSessionService: () => ({
    list: vi.fn().mockResolvedValue([
      {
        thread_id: "th-1",
        updated_at: "2026-09-14T08:00:00Z",
        status: "idle",
        metadata: { title: "数据分析任务", graph_id: "dearflow_agent" },
      },
    ]),
    history: vi.fn().mockResolvedValue(mockHistoryData),
  }),
}));

vi.mock("@/services/langgraph/client", () => ({
  createLanggraphAuthorizedFetch: () => vi.fn(),
}));

describe("DearAgentArtifactsPage", () => {
  it("mounts and loads session list and artifacts", async () => {
    const wrapper = mount(DearAgentArtifactsPage, {
      global: {
        stubs: {
          BaseIcon: true,
          BaseInput: true,
          BaseButton: true,
          RouterLink: true,
        },
      },
    });

    await flushPromises();

    // 验证会话标题
    expect(wrapper.text()).toContain("数据分析任务");
    expect(wrapper.text()).toContain("会话成果浏览器");

    // 验证成果提取：Markdown 报告、Excel 表格、PPTX 演示文稿
    expect(wrapper.text()).toContain("analysis_report.md");
    expect(wrapper.text()).toContain("sales_data.xlsx");
    expect(wrapper.text()).toContain("presentation.pptx");

    // 验证 PPTX 专属标记
    expect(wrapper.text()).toContain("图片型 PPTX");
    // 验证二进制产物标记
    expect(wrapper.text()).toContain("二进制产物");
  });
});

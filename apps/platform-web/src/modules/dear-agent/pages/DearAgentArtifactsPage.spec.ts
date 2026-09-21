import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick, ref } from "vue";
import type { ArtifactRef } from "@/types/workspace";

const activeProjectIdRef = ref("proj-1");
const routeQueryRef = ref<Record<string, string>>({});

vi.mock("vue-router", () => ({
  useRoute: () => ({
    params: { projectId: "proj-1" },
    query: routeQueryRef.value,
    path: "/workspace/projects/proj-1/dear-agent-artifacts",
  }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

vi.mock("@/composables/useWorkspaceProjectContext", () => ({
  useWorkspaceProjectContext: () => ({
    activeProjectId: activeProjectIdRef,
    activeProject: ref({ id: "proj-1", name: "测试项目" }),
  }),
}));

const mockSessionService = {
  list: vi.fn(),
  get: vi.fn(),
  history: vi.fn(),
};

const createSessionServiceMock = vi.fn(() => mockSessionService);

vi.mock("@/services/threads/session.service", () => ({
  createSessionService: (...args: unknown[]) => createSessionServiceMock(...args),
}));

vi.mock("@/services/langgraph/client", () => ({
  createLanggraphAuthorizedFetch: () => vi.fn(),
}));

const { workspaceServiceMock } = vi.hoisted(() => ({
  workspaceServiceMock: {
    getArtifacts: vi.fn(),
    getWorkspacePreview: vi.fn(),
    getWorkspaceContentBlob: vi.fn(),
    triggerBlobDownload: vi.fn(),
  },
}));

vi.mock("@/services/threads/workspace.service", () => workspaceServiceMock);

import DearAgentArtifactsPage from "./DearAgentArtifactsPage.vue";

describe("DearAgentArtifactsPage", () => {
  const mockArtifactDoc: ArtifactRef = {
    version: 1,
    artifact_id: "art-doc-1",
    path: "/workspace/outputs/analysis_report.md",
    file_name: "analysis_report.md",
    mime_type: "text/markdown",
    size_bytes: 1024,
    sha256: "sha256-report-123456",
    kind: "document",
    preview_kind: "markdown",
  };

  const mockArtifactPpt: ArtifactRef = {
    version: 1,
    artifact_id: "art-ppt-2",
    path: "/workspace/outputs/presentation.pptx",
    file_name: "presentation.pptx",
    mime_type: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    size_bytes: 20480,
    sha256: "sha256-ppt-654321",
    kind: "presentation",
    preview_kind: "download",
  };

  beforeEach(() => {
    vi.clearAllMocks();
    routeQueryRef.value = {};
    mockSessionService.list.mockResolvedValue([
      {
        thread_id: "th-1",
        updated_at: "2026-09-20T10:00:00Z",
        status: "idle",
        metadata: { title: "数据分析任务", graph_id: "dearflow_agent" },
      },
    ]);
    workspaceServiceMock.getArtifacts.mockResolvedValue({
      items: [mockArtifactDoc, mockArtifactPpt],
      next_cursor: null,
    });
  });

  it("mounts and loads session list and artifacts via standard contract", async () => {
    const wrapper = mount(DearAgentArtifactsPage, {
      global: {
        stubs: {
          BaseIcon: true,
          BaseInput: true,
          BaseButton: true,
          RouterLink: true,
          WorkspacePreview: true,
        },
      },
    });

    await flushPromises();

    // 1. 验证工厂正确注入了 projectId，且带有项目隔离
    expect(createSessionServiceMock).toHaveBeenCalledWith(
      expect.anything(),
      "proj-1",
    );

    // 2. 验证调用了 list 接口，绝对未调用 history() 扫描
    expect(mockSessionService.list).toHaveBeenCalledWith(
      expect.objectContaining({
        offset: 0,
        metadata: { graph_id: "dearflow_agent" },
      }),
    );
    expect(mockSessionService.history).not.toHaveBeenCalled();

    // 3. 验证成果列表从 getArtifacts 读取并成功渲染
    expect(workspaceServiceMock.getArtifacts).toHaveBeenCalledWith(
      "proj-1",
      "th-1",
      expect.anything(),
      expect.anything(),
    );
    expect(wrapper.text()).toContain("数据分析任务");
    expect(wrapper.text()).toContain("analysis_report.md");
    expect(wrapper.text()).toContain("presentation.pptx");
    expect(wrapper.text()).toContain("幻灯片");
  });

  it("handles deep link for non-first-page thread correctly", async () => {
    routeQueryRef.value = { threadId: "th-deep-99" };
    mockSessionService.get.mockResolvedValueOnce({
      thread_id: "th-deep-99",
      updated_at: "2026-09-19T08:00:00Z",
      status: "idle",
      metadata: { title: "深链旧会话", graph_id: "dearflow_agent" },
    });

    const wrapper = mount(DearAgentArtifactsPage, {
      global: {
        stubs: {
          BaseIcon: true,
          BaseInput: true,
          BaseButton: true,
          RouterLink: true,
          WorkspacePreview: true,
        },
      },
    });

    await flushPromises();

    // 验证调用了 service.get 并将深链会话置顶插入
    expect(mockSessionService.get).toHaveBeenCalledWith("th-deep-99");
    expect(wrapper.text()).toContain("深链旧会话");
    expect(workspaceServiceMock.getArtifacts).toHaveBeenCalledWith(
      "proj-1",
      "th-deep-99",
      expect.anything(),
      expect.anything(),
    );
  });

  it("opens slide-over drawer when clicking artifact card", async () => {
    const wrapper = mount(DearAgentArtifactsPage, {
      global: {
        stubs: {
          BaseIcon: true,
          BaseInput: true,
          BaseButton: true,
          RouterLink: true,
          WorkspacePreview: true,
        },
      },
    });

    await flushPromises();

    // 初始抽屉未打开
    expect(wrapper.text()).not.toContain("成果预览");

    // 点击第一个成果卡片
    const cards = wrapper.findAll("article");
    expect(cards.length).toBe(2);
    await cards[0].trigger("click");
    await nextTick();

    // 抽屉应滑出展示
    expect(wrapper.text()).toContain("成果预览");
  });
});

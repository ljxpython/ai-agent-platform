import { mount } from "@vue/test-utils";
import { describe, expect, it, vi, beforeEach } from "vitest";
import ProjectKnowledgePanel from "./ProjectKnowledgePanel.vue";
import * as knowledgeService from "@/services/knowledge/knowledge.service";

vi.mock("@/services/knowledge/knowledge.service", () => ({
  getKnowledgeCapabilities: vi.fn(),
  listKnowledgeDocuments: vi.fn(),
  listKnowledgeJobs: vi.fn(),
}));

describe("ProjectKnowledgePanel.vue", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders capabilities warning banner when knowledge is disabled", async () => {
    vi.mocked(knowledgeService.getKnowledgeCapabilities).mockResolvedValue({
      version: 1,
      read_enabled: false,
      upload_enabled: false,
      supported_mime_types: [],
      max_file_bytes: 20971520,
      disabled_reason: "knowledge_not_configured",
    });
    vi.mocked(knowledgeService.listKnowledgeDocuments).mockResolvedValue({
      items: [],
      total: 0,
    });
    vi.mocked(knowledgeService.listKnowledgeJobs).mockResolvedValue({
      items: [],
      total: 0,
    });

    const wrapper = mount(ProjectKnowledgePanel, {
      props: { projectId: "test-proj-1" },
    });

    await new Promise((r) => setTimeout(r, 50));
    expect(wrapper.text()).toContain("项目知识库管理");
    expect(wrapper.text()).toContain("当前项目未启用知识库检索能力");
  });

  it("renders document items and searchable badge when active", async () => {
    vi.mocked(knowledgeService.getKnowledgeCapabilities).mockResolvedValue({
      version: 1,
      read_enabled: true,
      upload_enabled: true,
      supported_mime_types: ["text/markdown"],
      max_file_bytes: 20971520,
      disabled_reason: null,
    });
    vi.mocked(knowledgeService.listKnowledgeDocuments).mockResolvedValue({
      items: [
        {
          document_id: "doc-1",
          file_name: "test_guidelines.md",
          mime_type: "text/markdown",
          size_bytes: 4096,
          status: "ready",
          searchable: true,
          published_at: "2026-10-12T10:00:00Z",
        },
      ],
      total: 1,
    });
    vi.mocked(knowledgeService.listKnowledgeJobs).mockResolvedValue({
      items: [],
      total: 0,
    });

    const wrapper = mount(ProjectKnowledgePanel, {
      props: { projectId: "test-proj-2" },
    });

    await new Promise((r) => setTimeout(r, 50));
    expect(wrapper.text()).toContain("test_guidelines.md");
    expect(wrapper.text()).toContain("当前可检索");
    expect(wrapper.text()).toContain("已发布资料 (1)");
  });
});

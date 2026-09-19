import { describe, expect, it, vi, beforeEach } from "vitest";
import { platformHttpClient } from "@/services/http/client";
import {
  getDearSkills,
  getDearSkillDetail,
  getDearSkillContent,
  createCustomSkill,
  updateCustomSkill,
  toggleCustomSkill,
  deleteCustomSkill,
  type DearSkillsListResponse,
  type SkillDetail,
  type SkillContentResponse,
} from "./skills.service";

vi.mock("@/services/http/client", () => ({
  platformHttpClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

describe("skills.service (新版无会话接口)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("getDearSkills 正确请求技能全量列表并附加项目头", async () => {
    const mockResponse: DearSkillsListResponse = {
      items: [
        {
          source: "public",
          slug: "deep-research",
          name: "Deep Research",
          description: "深度研究",
          revision: "rev-pub-1",
          updated_at: null,
          backend_verified: true,
          recommendable: true,
        },
        {
          source: "custom",
          slug: "custom-tool",
          name: "custom-tool",
          description: "自定义工具",
          revision: "rev-cus-1",
          digest: "sha256-111",
          origin: "explicit-management",
          warnings: [],
          enabled: true,
          updated_at: "2026-09-19T00:00:00Z",
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
    (platformHttpClient.get as any).mockResolvedValueOnce({ data: mockResponse });

    const result = await getDearSkills("proj-1");
    expect(platformHttpClient.get).toHaveBeenCalledWith(
      "/api/langgraph/dear/skills",
      {
        headers: { "x-project-id": "proj-1" },
        signal: undefined,
      },
    );
    expect(result).toEqual(mockResponse);
  });

  it("getDearSkillDetail 正确获取指定 source 与 slug 的技能详情", async () => {
    const mockDetail: SkillDetail = {
      source: "public",
      slug: "code-documentation",
      name: "Code Documentation",
      description: "生成代码文档",
      revision: "rev-detail-1",
      updated_at: null,
      backend_verified: true,
      recommendable: true,
      manifest: [
        { path: "SKILL.md", size: 1024, readable: true },
        { path: "large.bin", size: 300000, readable: false, reason: "file_too_large" },
      ],
    };
    (platformHttpClient.get as any).mockResolvedValueOnce({ data: mockDetail });

    const result = await getDearSkillDetail("proj-1", "public", "code-documentation");
    expect(platformHttpClient.get).toHaveBeenCalledWith(
      "/api/langgraph/dear/skills/public/code-documentation",
      {
        headers: { "x-project-id": "proj-1" },
        signal: undefined,
      },
    );
    expect(result).toEqual(mockDetail);
  });

  it("getDearSkillContent 正确获取单个文本文件的内容并带 query 参数", async () => {
    const mockContent: SkillContentResponse = {
      path: "SKILL.md",
      content: "# Skill Documentation",
      revision: "rev-content-1",
    };
    (platformHttpClient.get as any).mockResolvedValueOnce({ data: mockContent });

    const result = await getDearSkillContent("proj-1", "custom", "my-skill", "SKILL.md", "rev-content-1");
    expect(platformHttpClient.get).toHaveBeenCalledWith(
      "/api/langgraph/dear/skills/custom/my-skill/content",
      {
        headers: { "x-project-id": "proj-1" },
        params: { path: "SKILL.md", revision: "rev-content-1" },
        signal: undefined,
      },
    );
    expect(result).toEqual(mockContent);
  });

  it("createCustomSkill 上传新技能包并返回完整详情", async () => {
    const mockCreated: SkillDetail = {
      source: "custom",
      slug: "new-tool",
      name: "new-tool",
      description: "新增工具",
      revision: "rev-created-1",
      digest: "sha256-created",
      origin: "explicit-management",
      warnings: [],
      enabled: true,
      updated_at: "2026-09-19T00:00:00Z",
      manifest: [{ path: "SKILL.md", size: 100, readable: true }],
    };
    (platformHttpClient.post as any).mockResolvedValueOnce({ data: mockCreated });

    const result = await createCustomSkill("proj-1", "BASE64_ZIP_STRING");
    expect(platformHttpClient.post).toHaveBeenCalledWith(
      "/api/langgraph/dear/skills/custom",
      { package_base64: "BASE64_ZIP_STRING" },
      { headers: { "x-project-id": "proj-1" } },
    );
    expect(result).toEqual(mockCreated);
  });

  it("updateCustomSkill 显式覆盖更新已有技能包", async () => {
    const mockUpdated: SkillDetail = {
      source: "custom",
      slug: "my-tool",
      name: "my-tool",
      description: "更新后的工具",
      revision: "rev-updated-2",
      digest: "sha256-updated",
      origin: "explicit-management",
      warnings: [],
      enabled: false, // 保留原有停用状态
      updated_at: "2026-09-19T01:00:00Z",
      manifest: [{ path: "SKILL.md", size: 120, readable: true }],
    };
    (platformHttpClient.put as any).mockResolvedValueOnce({ data: mockUpdated });

    const result = await updateCustomSkill("proj-1", "my-tool", "NEW_BASE64_ZIP", "rev-updated-1");
    expect(platformHttpClient.put).toHaveBeenCalledWith(
      "/api/langgraph/dear/skills/custom/my-tool",
      {
        package_base64: "NEW_BASE64_ZIP",
        expected_revision: "rev-updated-1",
      },
      { headers: { "x-project-id": "proj-1" } },
    );
    expect(result).toEqual(mockUpdated);
  });

  it("toggleCustomSkill 启停技能并返回更新后详情", async () => {
    const mockToggled: SkillDetail = {
      source: "custom",
      slug: "my-tool",
      name: "my-tool",
      description: "工具",
      revision: "rev-toggled-3",
      digest: "sha256-updated",
      origin: "explicit-management",
      warnings: [],
      enabled: false,
      updated_at: "2026-09-19T02:00:00Z",
      manifest: [{ path: "SKILL.md", size: 120, readable: true }],
    };
    (platformHttpClient.patch as any).mockResolvedValueOnce({ data: mockToggled });

    const result = await toggleCustomSkill("proj-1", "my-tool", false, "rev-toggled-2");
    expect(platformHttpClient.patch).toHaveBeenCalledWith(
      "/api/langgraph/dear/skills/custom/my-tool",
      {
        enabled: false,
        expected_revision: "rev-toggled-2",
      },
      { headers: { "x-project-id": "proj-1" } },
    );
    expect(result).toEqual(mockToggled);
  });

  it("deleteCustomSkill 彻底删除技能并通过 params 传递 expected_revision", async () => {
    (platformHttpClient.delete as any).mockResolvedValueOnce({ status: 204 });

    await deleteCustomSkill("proj-1", "my-tool", "rev-del-1");
    expect(platformHttpClient.delete).toHaveBeenCalledWith(
      "/api/langgraph/dear/skills/custom/my-tool",
      {
        headers: { "x-project-id": "proj-1" },
        params: { expected_revision: "rev-del-1" },
      },
    );
  });
});

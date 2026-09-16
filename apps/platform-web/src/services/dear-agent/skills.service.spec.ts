import { describe, expect, it, vi, beforeEach } from "vitest";
import { platformHttpClient } from "@/services/http/client";
import {
  listCustomSkills,
  uploadCandidateSkillPackage,
  activateSkillVersion,
  revokeSkillVersion,
  OFFICIAL_PUBLIC_SKILLS,
} from "./skills.service";

vi.mock("@/services/http/client", () => ({
  platformHttpClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

describe("skills.service", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("OFFICIAL_PUBLIC_SKILLS 包含完整的 8 个推荐公共技能", () => {
    expect(OFFICIAL_PUBLIC_SKILLS).toHaveLength(8);
    expect(OFFICIAL_PUBLIC_SKILLS.every((s) => s.backend_verified && s.recommendable)).toBe(true);
    expect(OFFICIAL_PUBLIC_SKILLS.map((s) => s.slug)).toEqual([
      "deep-research",
      "academic-paper-review",
      "code-documentation",
      "newsletter-generation",
      "data-analysis",
      "frontend-design",
      "web-design-guidelines",
      "ppt-generation",
    ]);
  });

  it("listCustomSkills 正确请求自定义技能版本列表", async () => {
    const mockVersions = [
      {
        slug: "custom-demo",
        description: "自定义技能",
        digest: "sha256-abc",
        revision: 1,
        status: "candidate",
        warnings: [],
        manifest: [{ path: "SKILL.md", sha256: "hash1" }],
      },
    ];
    (platformHttpClient.get as any).mockResolvedValueOnce({
      data: { versions: mockVersions },
    });

    const result = await listCustomSkills("proj-1", "th-1");
    expect(platformHttpClient.get).toHaveBeenCalledWith(
      "/api/langgraph/threads/th-1/dear/skills",
      {
        headers: { "x-project-id": "proj-1" },
        signal: undefined,
      },
    );
    expect(result).toEqual(mockVersions);
  });

  it("uploadCandidateSkillPackage 上传 Base64 编码的 candidate 技能包", async () => {
    const mockCreated = {
      slug: "custom-tool",
      digest: "sha256-123",
      revision: 1,
      status: "candidate",
    };
    (platformHttpClient.post as any).mockResolvedValueOnce({ data: mockCreated });

    const result = await uploadCandidateSkillPackage("proj-1", "th-1", "UEsDBBQAAAAIA...");
    expect(platformHttpClient.post).toHaveBeenCalledWith(
      "/api/langgraph/threads/th-1/dear/skills",
      {
        action: "candidate",
        package_base64: "UEsDBBQAAAAIA...",
      },
      {
        headers: { "x-project-id": "proj-1" },
      },
    );
    expect(result).toEqual(mockCreated);
  });

  it("activateSkillVersion 发起激活/回退请求", async () => {
    (platformHttpClient.post as any).mockResolvedValueOnce({
      data: { slug: "tool", status: "active", revision: 2 },
    });

    await activateSkillVersion("proj-1", "th-1", "tool", "sha256-123", 1);
    expect(platformHttpClient.post).toHaveBeenCalledWith(
      "/api/langgraph/threads/th-1/dear/skills",
      {
        action: "activate",
        slug: "tool",
        digest: "sha256-123",
        expected_revision: 1,
      },
      {
        headers: { "x-project-id": "proj-1" },
      },
    );
  });

  it("revokeSkillVersion 发起撤销请求", async () => {
    (platformHttpClient.post as any).mockResolvedValueOnce({
      data: { slug: "tool", status: "revoked", revision: 2 },
    });

    await revokeSkillVersion("proj-1", "th-1", "tool", "sha256-123", 1);
    expect(platformHttpClient.post).toHaveBeenCalledWith(
      "/api/langgraph/threads/th-1/dear/skills",
      {
        action: "revoke",
        slug: "tool",
        digest: "sha256-123",
        expected_revision: 1,
      },
      {
        headers: { "x-project-id": "proj-1" },
      },
    );
  });
});

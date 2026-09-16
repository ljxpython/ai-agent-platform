import { platformHttpClient } from "@/services/http/client";

export interface SkillManifestItem {
  path: string;
  sha256: string;
}

export interface SkillVersion {
  slug: string;
  description: string;
  digest: string;
  revision: number;
  status: "candidate" | "active" | "inactive" | "revoked";
  warnings: string[];
  manifest: SkillManifestItem[];
  review?: { passed?: boolean; [key: string]: unknown } | null;
  evaluation?: { passed?: boolean; [key: string]: unknown } | null;
  source?: string;
}

export interface PublicSkillItem {
  slug: string;
  name: string;
  description: string;
  path: string;
  backend_verified: boolean;
  recommendable: boolean;
  category: string;
}

export interface SkillCommandPayload {
  action: "candidate" | "activate" | "revoke";
  slug?: string;
  digest?: string;
  expected_revision?: number;
  package_base64?: string;
}

/**
 * 平台内置官方公共技能目录（通过后端验收并支持推荐）
 */
export const OFFICIAL_PUBLIC_SKILLS: PublicSkillItem[] = [
  {
    slug: "deep-research",
    name: "深度研究 (Deep Research)",
    description: "多步规划、并发检索与跨文档交叉比对研究，产出全面深入的研究报告。",
    path: "/skills/deep-research/SKILL.md",
    backend_verified: true,
    recommendable: true,
    category: "研究分析",
  },
  {
    slug: "academic-paper-review",
    name: "学术论文审查 (Academic Paper Review)",
    description: "学术论文结构化提炼、方法论评估与创新点对比，支持 arXiv 深度检索。",
    path: "/skills/academic-paper-review/SKILL.md",
    backend_verified: true,
    recommendable: true,
    category: "学术科研",
  },
  {
    slug: "code-documentation",
    name: "代码工程文档 (Code Documentation)",
    description: "分析代码库结构、生成模块 API 文档、架构说明与开发指引。",
    path: "/skills/code-documentation/SKILL.md",
    backend_verified: true,
    recommendable: true,
    category: "研发工程",
  },
  {
    slug: "newsletter-generation",
    name: "行业资讯简报 (Newsletter Generation)",
    description: "抓取整理最新行业资讯与趋势要闻，生成排版优美的结构化周报简报。",
    path: "/skills/newsletter-generation/SKILL.md",
    backend_verified: true,
    recommendable: true,
    category: "内容创作",
  },
  {
    slug: "data-analysis",
    name: "沙箱数据分析 (Data Analysis)",
    description: "利用沙箱环境对 CSV/Excel 复杂表格进行 SQL 查询、清洗与统计建模。",
    path: "/skills/data-analysis/SKILL.md",
    backend_verified: true,
    recommendable: true,
    category: "数据洞察",
  },
  {
    slug: "frontend-design",
    name: "前端界面设计 (Frontend Design)",
    description: "生成现代化 UI 视觉规范、设计系统令牌以及高质量 Tailwind 组件草案。",
    path: "/skills/frontend-design/SKILL.md",
    backend_verified: true,
    recommendable: true,
    category: "设计交互",
  },
  {
    slug: "web-design-guidelines",
    name: "网页设计规范 (Web Design Guidelines)",
    description: "提供无障碍访问 (a11y)、响应式排版与界面易用性设计标准与审查建议。",
    path: "/skills/web-design-guidelines/SKILL.md",
    backend_verified: true,
    recommendable: true,
    category: "设计交互",
  },
  {
    slug: "ppt-generation",
    name: "幻灯片演示文稿 (PPT Generation)",
    description: "提炼演示文稿大纲，生成演讲备注与图片型演示文稿幻灯片成果。",
    path: "/skills/ppt-generation/SKILL.md",
    backend_verified: true,
    recommendable: true,
    category: "办公演示",
  },
];

/**
 * 获取自定义技能版本列表
 */
export async function listCustomSkills(
  projectId: string,
  threadId: string,
  signal?: AbortSignal,
): Promise<SkillVersion[]> {
  const { data } = await platformHttpClient.get<{ versions: SkillVersion[] }>(
    `/api/langgraph/threads/${encodeURIComponent(threadId)}/dear/skills`,
    {
      headers: { "x-project-id": projectId },
      signal,
    },
  );
  return data.versions || [];
}

/**
 * 导入自定义技能候选 ZIP 包 (必须包含根目录 SKILL.md，大小 <= 1MiB)
 */
export async function uploadCandidateSkillPackage(
  projectId: string,
  threadId: string,
  base64Zip: string,
): Promise<SkillVersion> {
  const { data } = await platformHttpClient.post<SkillVersion>(
    `/api/langgraph/threads/${encodeURIComponent(threadId)}/dear/skills`,
    {
      action: "candidate",
      package_base64: base64Zip,
    },
    {
      headers: { "x-project-id": projectId },
    },
  );
  return data;
}

/**
 * 启用或回退指定版本的技能（要求 review 与 evaluation 均 passed 且无 warnings）
 */
export async function activateSkillVersion(
  projectId: string,
  threadId: string,
  slug: string,
  digest: string,
  expectedRevision: number,
): Promise<SkillVersion> {
  const { data } = await platformHttpClient.post<SkillVersion>(
    `/api/langgraph/threads/${encodeURIComponent(threadId)}/dear/skills`,
    {
      action: "activate",
      slug,
      digest,
      expected_revision: expectedRevision,
    },
    {
      headers: { "x-project-id": projectId },
    },
  );
  return data;
}

/**
 * 撤销指定版本的技能（永久撤销且不可重新激活；旧线程绑定该版本将无法继续恢复）
 */
export async function revokeSkillVersion(
  projectId: string,
  threadId: string,
  slug: string,
  digest: string,
  expectedRevision: number,
): Promise<SkillVersion> {
  const { data } = await platformHttpClient.post<SkillVersion>(
    `/api/langgraph/threads/${encodeURIComponent(threadId)}/dear/skills`,
    {
      action: "revoke",
      slug,
      digest,
      expected_revision: expectedRevision,
    },
    {
      headers: { "x-project-id": projectId },
    },
  );
  return data;
}

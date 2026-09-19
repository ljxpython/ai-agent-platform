import { platformHttpClient } from "@/services/http/client";

export interface SkillManifestItem {
  path: string;
  size: number;
  readable: boolean;
  reason?: "not_utf8_text" | "file_too_large" | string;
}

export interface BaseSkillItem {
  source: "public" | "custom";
  slug: string;
  name: string;
  description: string;
  revision: string;
  updated_at: string | null;
}

export interface PublicSkillItem extends BaseSkillItem {
  source: "public";
  updated_at: null;
  backend_verified: boolean;
  recommendable: boolean;
}

export interface CustomSkillItem extends BaseSkillItem {
  source: "custom";
  enabled: boolean;
  digest: string;
  origin: string;
  warnings: string[];
  updated_at: string;
}

export type SkillItem = PublicSkillItem | CustomSkillItem;

export type SkillDetail = SkillItem & {
  manifest: SkillManifestItem[];
};

export interface SkillContentResponse {
  path: string;
  content: string;
  revision: string;
}

export interface DearSkillsCapabilities {
  can_read: boolean;
  can_write: boolean;
  custom_management_enabled: boolean;
}

export interface DearSkillsLimits {
  package_bytes: number;
  unpacked_bytes: number;
  file_bytes: number;
  entries: number;
  custom_skills: number;
}

export interface DearSkillsListResponse {
  items: SkillItem[];
  capabilities: DearSkillsCapabilities;
  limits: DearSkillsLimits;
}

/**
 * 获取技能列表（平台公共技能 + 用户自定义技能，剥离 manifest 字段）
 */
export async function getDearSkills(
  projectId: string,
  signal?: AbortSignal,
): Promise<DearSkillsListResponse> {
  const { data } = await platformHttpClient.get<DearSkillsListResponse>(
    "/api/langgraph/dear/skills",
    {
      headers: { "x-project-id": projectId },
      signal,
    },
  );
  return data;
}

/**
 * 获取单个技能的完整元数据与文件清单（manifest）
 */
export async function getDearSkillDetail(
  projectId: string,
  source: "public" | "custom",
  slug: string,
  signal?: AbortSignal,
): Promise<SkillDetail> {
  const { data } = await platformHttpClient.get<SkillDetail>(
    `/api/langgraph/dear/skills/${encodeURIComponent(source)}/${encodeURIComponent(slug)}`,
    {
      headers: { "x-project-id": projectId },
      signal,
    },
  );
  return data;
}

/**
 * 获取技能单个文件的文本内容（需提供当前最新 revision 保证一致性）
 */
export async function getDearSkillContent(
  projectId: string,
  source: "public" | "custom",
  slug: string,
  path: string,
  revision: string,
  signal?: AbortSignal,
): Promise<SkillContentResponse> {
  const { data } = await platformHttpClient.get<SkillContentResponse>(
    `/api/langgraph/dear/skills/${encodeURIComponent(source)}/${encodeURIComponent(slug)}/content`,
    {
      headers: { "x-project-id": projectId },
      params: { path, revision },
      signal,
    },
  );
  return data;
}

/**
 * 上传创建新的自定义技能（默认启用，成功返回完整详情与 manifest）
 */
export async function createCustomSkill(
  projectId: string,
  packageBase64: string,
): Promise<SkillDetail> {
  const { data } = await platformHttpClient.post<SkillDetail>(
    "/api/langgraph/dear/skills/custom",
    {
      package_base64: packageBase64,
    },
    {
      headers: { "x-project-id": projectId },
    },
  );
  return data;
}

/**
 * 显式覆盖更新已有的自定义技能（保留原启用/停用状态，需提供 expected_revision）
 */
export async function updateCustomSkill(
  projectId: string,
  slug: string,
  packageBase64: string,
  expectedRevision: string,
): Promise<SkillDetail> {
  const { data } = await platformHttpClient.put<SkillDetail>(
    `/api/langgraph/dear/skills/custom/${encodeURIComponent(slug)}`,
    {
      package_base64: packageBase64,
      expected_revision: expectedRevision,
    },
    {
      headers: { "x-project-id": projectId },
    },
  );
  return data;
}

/**
 * 启停自定义技能（返回完整更新后的技能对象）
 */
export async function toggleCustomSkill(
  projectId: string,
  slug: string,
  enabled: boolean,
  expectedRevision: string,
): Promise<SkillDetail> {
  const { data } = await platformHttpClient.patch<SkillDetail>(
    `/api/langgraph/dear/skills/custom/${encodeURIComponent(slug)}`,
    {
      enabled,
      expected_revision: expectedRevision,
    },
    {
      headers: { "x-project-id": projectId },
    },
  );
  return data;
}

/**
 * 彻底删除自定义技能（expected_revision 必须作为 Query 参数传递）
 */
export async function deleteCustomSkill(
  projectId: string,
  slug: string,
  expectedRevision: string,
): Promise<void> {
  await platformHttpClient.delete(
    `/api/langgraph/dear/skills/custom/${encodeURIComponent(slug)}`,
    {
      headers: { "x-project-id": projectId },
      params: { expected_revision: expectedRevision },
    },
  );
}

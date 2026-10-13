import { platformHttpClient } from "@/services/http/client";

export type KnowledgeStatus =
  | "queued"
  | "parsing"
  | "indexing"
  | "publishing"
  | "ready"
  | "failed";

export interface KnowledgeCapabilities {
  version: 1;
  read_enabled: boolean;
  upload_enabled: boolean;
  supported_mime_types: string[];
  max_file_bytes: number;
  disabled_reason: string | null;
}

export interface KnowledgeDocument {
  document_id: string;
  file_name: string;
  mime_type: string;
  size_bytes: number;
  status: "ready";
  searchable: true;
  published_at: string;
}

export interface KnowledgeDocumentPage {
  items: KnowledgeDocument[];
  total: number;
}

export interface KnowledgeJob {
  version: 1;
  job_id: string;
  document_id: string;
  file_name: string;
  status: KnowledgeStatus;
  searchable: boolean;
  error_code: string | null;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeJobPage {
  items: KnowledgeJob[];
  total: number;
}

export interface KnowledgeSubmission {
  version: 1;
  job_id: string | null;
  document_id: string;
  file_name: string;
  status: KnowledgeStatus;
  searchable: boolean;
  error_code: string | null;
  reused: boolean;
  created_at: string;
  updated_at: string;
}

/**
 * 校验 Job ID 格式：kj_ + 32 位小写 16 进制
 */
export function isValidJobId(jobId: string): boolean {
  return /^kj_[0-9a-f]{32}$/.test(jobId);
}

/**
 * 获取项目知识库能力配置 (GET /capabilities)
 * 警告：后端严格禁止任何 query 参数，违者直接 400 invalid_knowledge_query
 */
export async function getKnowledgeCapabilities(
  projectId: string,
  signal?: AbortSignal,
): Promise<KnowledgeCapabilities> {
  const response = await platformHttpClient.get<KnowledgeCapabilities>(
    `/api/projects/${encodeURIComponent(projectId)}/knowledge/capabilities`,
    {
      headers: { "x-project-id": projectId },
      signal,
    },
  );
  return response.data;
}

/**
 * 分页获取项目知识库资料列表 (GET /documents)
 * 警告：Query 参数仅允许 limit 与 offset，严禁传递任何未知字段
 */
export async function listKnowledgeDocuments(
  projectId: string,
  options?: { limit?: number; offset?: number },
  signal?: AbortSignal,
): Promise<KnowledgeDocumentPage> {
  const limit = Math.min(Math.max(options?.limit ?? 20, 1), 100);
  const offset = Math.max(options?.offset ?? 0, 0);

  const response = await platformHttpClient.get<KnowledgeDocumentPage>(
    `/api/projects/${encodeURIComponent(projectId)}/knowledge/documents`,
    {
      params: {
        limit,
        offset,
      },
      headers: { "x-project-id": projectId },
      signal,
    },
  );
  return response.data;
}

/**
 * 分页获取项目知识库入库任务列表 (GET /jobs)
 * 警告：Query 参数仅允许 limit 与 offset，严禁传递任何未知字段
 */
export async function listKnowledgeJobs(
  projectId: string,
  options?: { limit?: number; offset?: number },
  signal?: AbortSignal,
): Promise<KnowledgeJobPage> {
  const limit = Math.min(Math.max(options?.limit ?? 20, 1), 100);
  const offset = Math.max(options?.offset ?? 0, 0);

  const response = await platformHttpClient.get<KnowledgeJobPage>(
    `/api/projects/${encodeURIComponent(projectId)}/knowledge/jobs`,
    {
      params: {
        limit,
        offset,
      },
      headers: { "x-project-id": projectId },
      signal,
    },
  );
  return response.data;
}

/**
 * 获取单个入库任务详情 (GET /jobs/{job_id})
 * 警告：严禁携带任何 query 参数
 */
export async function getKnowledgeJob(
  projectId: string,
  jobId: string,
  signal?: AbortSignal,
): Promise<KnowledgeJob> {
  if (!isValidJobId(jobId)) {
    throw new Error(`非法的任务 ID 格式: ${jobId}`);
  }

  const response = await platformHttpClient.get<KnowledgeJob>(
    `/api/projects/${encodeURIComponent(projectId)}/knowledge/jobs/${encodeURIComponent(jobId)}`,
    {
      headers: { "x-project-id": projectId },
      signal,
    },
  );
  return response.data;
}

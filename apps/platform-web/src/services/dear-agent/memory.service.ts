import { platformHttpClient } from "@/services/http/client";

export interface FactItem {
  id: string;
  text: string;
  category: "preference" | "fact";
  origin: "user" | "confirmed" | "inferred";
  source_thread_id?: string;
  source_message_id?: string;
  revision: number;
  created_at: string;
  updated_at: string;
  expires_at?: string | null;
}

export interface MemoryDocument {
  schema_version: number;
  revision: number;
  epoch: number;
  automatic_candidates: boolean;
  facts: FactItem[];
  candidates: FactItem[];
}

export interface FactInput {
  text: string;
  category?: "preference" | "fact";
  expires_at?: string | null;
}

export interface MemoryCommandPayload {
  action: "save" | "delete" | "clear" | "accept" | "reject" | "settings" | "restore";
  expected_revision: number;
  fact_id?: string;
  fact?: FactInput;
  automatic_candidates?: boolean;
  facts?: FactInput[];
}

/**
 * 读取当前 Dear 会话关联的长期记忆与候选
 */
export async function readMemory(
  projectId: string,
  threadId: string,
  query = "",
  signal?: AbortSignal,
): Promise<MemoryDocument> {
  const params = query.trim() ? { query: query.trim() } : undefined;
  const { data } = await platformHttpClient.get<MemoryDocument>(
    `/api/langgraph/threads/${encodeURIComponent(threadId)}/dear/memory`,
    {
      headers: { "x-project-id": projectId },
      params,
      signal,
    },
  );
  return data;
}

/**
 * 提交记忆变更指令（带 CAS expected_revision 防并发冲突）
 */
export async function changeMemory(
  projectId: string,
  threadId: string,
  payload: MemoryCommandPayload,
): Promise<MemoryDocument> {
  const { data } = await platformHttpClient.post<MemoryDocument>(
    `/api/langgraph/threads/${encodeURIComponent(threadId)}/dear/memory`,
    payload,
    {
      headers: { "x-project-id": projectId },
    },
  );
  return data;
}

/**
 * 保存或修改单条记忆事实
 */
export async function saveMemoryFact(
  projectId: string,
  threadId: string,
  expectedRevision: number,
  fact: FactInput,
  factId?: string,
): Promise<MemoryDocument> {
  return changeMemory(projectId, threadId, {
    action: "save",
    expected_revision: expectedRevision,
    fact,
    fact_id: factId,
  });
}

/**
 * 删除单条记忆事实
 */
export async function deleteMemoryFact(
  projectId: string,
  threadId: string,
  expectedRevision: number,
  factId: string,
): Promise<MemoryDocument> {
  return changeMemory(projectId, threadId, {
    action: "delete",
    expected_revision: expectedRevision,
    fact_id: factId,
  });
}

/**
 * 清空当前用户在当前项目下的记忆事实
 */
export async function clearMemory(
  projectId: string,
  threadId: string,
  expectedRevision: number,
): Promise<MemoryDocument> {
  return changeMemory(projectId, threadId, {
    action: "clear",
    expected_revision: expectedRevision,
  });
}

/**
 * 确认采纳推断候选为正式事实
 */
export async function acceptMemoryCandidate(
  projectId: string,
  threadId: string,
  expectedRevision: number,
  factId: string,
): Promise<MemoryDocument> {
  return changeMemory(projectId, threadId, {
    action: "accept",
    expected_revision: expectedRevision,
    fact_id: factId,
  });
}

/**
 * 拒绝并丢弃候选推断（记录指纹防再次推断）
 */
export async function rejectMemoryCandidate(
  projectId: string,
  threadId: string,
  expectedRevision: number,
  factId: string,
): Promise<MemoryDocument> {
  return changeMemory(projectId, threadId, {
    action: "reject",
    expected_revision: expectedRevision,
    fact_id: factId,
  });
}

/**
 * 更新自动候选设置（默认关闭）
 */
export async function updateMemorySettings(
  projectId: string,
  threadId: string,
  expectedRevision: number,
  automaticCandidates: boolean,
): Promise<MemoryDocument> {
  return changeMemory(projectId, threadId, {
    action: "settings",
    expected_revision: expectedRevision,
    automatic_candidates: automaticCandidates,
  });
}

/**
 * 追加恢复记忆事实列表（最多 100 条）
 */
export async function restoreMemoryFacts(
  projectId: string,
  threadId: string,
  expectedRevision: number,
  facts: FactInput[],
): Promise<MemoryDocument> {
  return changeMemory(projectId, threadId, {
    action: "restore",
    expected_revision: expectedRevision,
    facts,
  });
}

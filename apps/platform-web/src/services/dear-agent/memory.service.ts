import { platformHttpClient } from "@/services/http/client";

export type FactCategory = "preference" | "fact";
export type FactOrigin = "user" | "confirmed" | "inferred";
export type FactSourceKind = "management" | "user_message" | "tool" | "legacy";

export interface FactInput {
  text: string;
  category?: FactCategory;
  expires_at?: string | null;
}

export interface MemoryFact {
  id: string;
  text: string;
  category: FactCategory;
  expires_at: string | null;
  origin: FactOrigin;
  revision: number;
  created_at: string;
  updated_at: string;
  source_kind: FactSourceKind;
  source_thread_id: string | null;
  source_message_id: string | null;
  source_call_id: string | null;
  quote: string | null;
}

/** @deprecated 兼容旧别名，等同于 MemoryFact */
export type FactItem = MemoryFact;

export interface MemoryDocument {
  schema_version: number;
  revision: number;
  epoch: number;
  automatic_candidates: boolean;
  facts: MemoryFact[];
  candidates: MemoryFact[];
}

export type ExtractionStatusKind =
  | "never"
  | "running"
  | "succeeded"
  | "no_candidates"
  | "failed"
  | "skipped"
  | "interrupted";

export type ExtractionPauseReason =
  | "source_limit"
  | "tombstone_limit"
  | "candidate_limit";

export interface ExtractionStatus {
  status: ExtractionStatusKind;
  updated_at: string | null;
  source_thread_id: string | null;
  candidate_count: number;
  error_code: string | null;
  pause_reason: ExtractionPauseReason | string | null;
}

export interface MemoryMutation {
  action: string;
  changed: boolean;
  added: number;
  updated: number;
  removed: number;
  skipped: number;
}

export interface MemoryScope {
  kind: "project_user" | string;
  project_id: string;
  user_id: string;
}

export interface MemoryCapabilities {
  memory_enabled: boolean;
  can_read: boolean;
  can_write: boolean;
}

export interface MemoryLimits {
  fact_text_chars: number;
  facts: number;
  candidates: number;
  restore_items: number;
  request_bytes: number;
}

export interface MemoryCounts {
  facts: number;
  candidates: number;
}

export interface MemoryView {
  status: "ready" | "disabled";
  scope: MemoryScope;
  capabilities: MemoryCapabilities;
  limits: MemoryLimits;
  document: MemoryDocument | null;
  counts: MemoryCounts | null;
  extraction: ExtractionStatus | null;
  mutation: MemoryMutation | null;
}

export interface MemoryCommandPayload {
  action: "save" | "delete" | "clear" | "accept" | "reject" | "settings" | "restore";
  expected_revision: number;
  fact_id?: string;
  replace_fact_id?: string;
  fact?: FactInput;
  automatic_candidates?: boolean;
  facts?: FactInput[];
}

/**
 * 读取当前登录用户在指定项目下的无线程长期记忆视图 (MemoryView)
 */
export async function readMemory(
  projectId: string,
  signal?: AbortSignal,
): Promise<MemoryView> {
  const { data } = await platformHttpClient.get<MemoryView>(
    "/api/langgraph/dear/memory",
    {
      headers: { "x-project-id": projectId },
      signal,
    },
  );
  return data;
}

/**
 * 提交无线程长期记忆变更命令（带 CAS expected_revision 防并发冲突）
 */
export async function changeMemory(
  projectId: string,
  payload: MemoryCommandPayload,
): Promise<MemoryView> {
  const { data } = await platformHttpClient.post<MemoryView>(
    "/api/langgraph/dear/memory",
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
  expectedRevision: number,
  fact: FactInput,
  factId?: string,
): Promise<MemoryView> {
  const payload: MemoryCommandPayload = {
    action: "save",
    expected_revision: expectedRevision,
    fact,
  };
  if (factId) {
    payload.fact_id = factId;
  }
  return changeMemory(projectId, payload);
}

/**
 * 删除单条记忆事实
 */
export async function deleteMemoryFact(
  projectId: string,
  expectedRevision: number,
  factId: string,
): Promise<MemoryView> {
  return changeMemory(projectId, {
    action: "delete",
    expected_revision: expectedRevision,
    fact_id: factId,
  });
}

/**
 * 清空当前用户在当前项目下的全部记忆事实与候选并关闭自动候选
 */
export async function clearMemory(
  projectId: string,
  expectedRevision: number,
): Promise<MemoryView> {
  return changeMemory(projectId, {
    action: "clear",
    expected_revision: expectedRevision,
  });
}

/**
 * 确认采纳推断候选为正式事实（可选传入 replaceFactId 原子替换已有事实）
 */
export async function acceptMemoryCandidate(
  projectId: string,
  expectedRevision: number,
  factId: string,
  replaceFactId?: string,
): Promise<MemoryView> {
  const payload: MemoryCommandPayload = {
    action: "accept",
    expected_revision: expectedRevision,
    fact_id: factId,
  };
  if (replaceFactId) {
    payload.replace_fact_id = replaceFactId;
  }
  return changeMemory(projectId, payload);
}

/**
 * 拒绝并丢弃候选推断（记录指纹防再次推断）
 */
export async function rejectMemoryCandidate(
  projectId: string,
  expectedRevision: number,
  factId: string,
): Promise<MemoryView> {
  return changeMemory(projectId, {
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
  expectedRevision: number,
  automaticCandidates: boolean,
): Promise<MemoryView> {
  return changeMemory(projectId, {
    action: "settings",
    expected_revision: expectedRevision,
    automatic_candidates: automaticCandidates,
  });
}

/**
 * 追加恢复记忆事实列表（单次 1..100 条）
 */
export async function restoreMemoryFacts(
  projectId: string,
  expectedRevision: number,
  facts: FactInput[],
): Promise<MemoryView> {
  return changeMemory(projectId, {
    action: "restore",
    expected_revision: expectedRevision,
    facts,
  });
}

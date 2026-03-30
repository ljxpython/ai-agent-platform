import { createManagementApiClient, type ManagementDownload } from "./client";

export type TestcaseOverview = {
  project_id: string;
  documents_total: number;
  parsed_documents_total: number;
  failed_documents_total: number;
  test_cases_total: number;
  latest_batch_id?: string | null;
  latest_activity_at?: string | null;
};

export type TestcaseBatchSummary = {
  batch_id: string;
  documents_count: number;
  test_cases_count: number;
  latest_created_at?: string | null;
  parse_status_summary: Record<string, number>;
};

export type TestcaseDocument = {
  id: string;
  project_id: string;
  batch_id?: string | null;
  filename: string;
  content_type: string;
  storage_path?: string | null;
  source_kind: string;
  parse_status: string;
  summary_for_model: string;
  parsed_text?: string | null;
  structured_data?: Record<string, unknown> | null;
  provenance: Record<string, unknown>;
  confidence?: number | null;
  error?: Record<string, unknown> | null;
  created_at: string;
};

export type TestcaseCase = {
  id: string;
  project_id: string;
  batch_id?: string | null;
  case_id?: string | null;
  title: string;
  description: string;
  status: string;
  module_name?: string | null;
  priority?: string | null;
  source_document_ids: string[];
  content_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

type BatchListResponse = {
  items: TestcaseBatchSummary[];
  total: number;
};

type DocumentListResponse = {
  items: TestcaseDocument[];
  total: number;
};

type CaseListResponse = {
  items: TestcaseCase[];
  total: number;
};

function createClient(projectId: string) {
  return createManagementApiClient({
    requireAuth: false,
    headers: projectId ? { "x-project-id": projectId } : {},
  });
}

export async function getTestcaseOverview(projectId: string): Promise<TestcaseOverview> {
  const client = createClient(projectId);
  if (!client || !projectId) {
    throw new Error("management_api_unavailable");
  }
  return client.get<TestcaseOverview>(`/_management/projects/${projectId}/testcase/overview`);
}

export async function listTestcaseBatches(
  projectId: string,
  options?: { limit?: number; offset?: number },
): Promise<BatchListResponse> {
  const client = createClient(projectId);
  if (!client || !projectId) {
    return { items: [], total: 0 };
  }
  const params = new URLSearchParams();
  params.set("limit", String(options?.limit ?? 50));
  params.set("offset", String(options?.offset ?? 0));
  return client.get<BatchListResponse>(`/_management/projects/${projectId}/testcase/batches?${params.toString()}`);
}

export async function listTestcaseDocuments(
  projectId: string,
  options?: {
    batch_id?: string;
    parse_status?: string;
    query?: string;
    limit?: number;
    offset?: number;
  },
): Promise<DocumentListResponse> {
  const client = createClient(projectId);
  if (!client || !projectId) {
    return { items: [], total: 0 };
  }
  const params = new URLSearchParams();
  params.set("limit", String(options?.limit ?? 20));
  params.set("offset", String(options?.offset ?? 0));
  if (options?.batch_id?.trim()) {
    params.set("batch_id", options.batch_id.trim());
  }
  if (options?.parse_status?.trim()) {
    params.set("parse_status", options.parse_status.trim());
  }
  if (options?.query?.trim()) {
    params.set("query", options.query.trim());
  }
  return client.get<DocumentListResponse>(`/_management/projects/${projectId}/testcase/documents?${params.toString()}`);
}

export async function getTestcaseDocument(projectId: string, documentId: string): Promise<TestcaseDocument> {
  const client = createClient(projectId);
  if (!client || !projectId) {
    throw new Error("management_api_unavailable");
  }
  return client.get<TestcaseDocument>(`/_management/projects/${projectId}/testcase/documents/${documentId}`);
}

export async function listTestcaseCases(
  projectId: string,
  options?: {
    batch_id?: string;
    status?: string;
    query?: string;
    limit?: number;
    offset?: number;
  },
): Promise<CaseListResponse> {
  const client = createClient(projectId);
  if (!client || !projectId) {
    return { items: [], total: 0 };
  }
  const params = new URLSearchParams();
  params.set("limit", String(options?.limit ?? 20));
  params.set("offset", String(options?.offset ?? 0));
  if (options?.batch_id?.trim()) {
    params.set("batch_id", options.batch_id.trim());
  }
  if (options?.status?.trim()) {
    params.set("status", options.status.trim());
  }
  if (options?.query?.trim()) {
    params.set("query", options.query.trim());
  }
  return client.get<CaseListResponse>(`/_management/projects/${projectId}/testcase/cases?${params.toString()}`);
}

export async function getTestcaseCase(projectId: string, caseId: string): Promise<TestcaseCase> {
  const client = createClient(projectId);
  if (!client || !projectId) {
    throw new Error("management_api_unavailable");
  }
  return client.get<TestcaseCase>(`/_management/projects/${projectId}/testcase/cases/${caseId}`);
}

export async function exportTestcaseCasesExcel(
  projectId: string,
  options?: {
    batch_id?: string;
    status?: string;
    query?: string;
  },
): Promise<ManagementDownload> {
  const client = createClient(projectId);
  if (!client || !projectId) {
    throw new Error("management_api_unavailable");
  }
  const params = new URLSearchParams();
  if (options?.batch_id?.trim()) {
    params.set("batch_id", options.batch_id.trim());
  }
  if (options?.status?.trim()) {
    params.set("status", options.status.trim());
  }
  if (options?.query?.trim()) {
    params.set("query", options.query.trim());
  }
  const suffix = params.toString();
  return client.download(
    `/_management/projects/${projectId}/testcase/cases/export${suffix ? `?${suffix}` : ""}`,
  );
}

export async function createTestcaseCase(
  projectId: string,
  payload: {
    batch_id?: string;
    case_id?: string;
    title: string;
    description?: string;
    status?: string;
    module_name?: string;
    priority?: string;
    source_document_ids?: string[];
    content_json?: Record<string, unknown>;
  },
): Promise<TestcaseCase> {
  const client = createClient(projectId);
  if (!client || !projectId) {
    throw new Error("management_api_unavailable");
  }
  return client.post<TestcaseCase>(`/_management/projects/${projectId}/testcase/cases`, payload);
}

export async function updateTestcaseCase(
  projectId: string,
  caseId: string,
  payload: {
    title?: string;
    description?: string;
    status?: string;
    module_name?: string;
    priority?: string;
    source_document_ids?: string[];
    content_json?: Record<string, unknown>;
  },
): Promise<TestcaseCase> {
  const client = createClient(projectId);
  if (!client || !projectId) {
    throw new Error("management_api_unavailable");
  }
  return client.patch<TestcaseCase>(`/_management/projects/${projectId}/testcase/cases/${caseId}`, payload);
}

export async function deleteTestcaseCase(projectId: string, caseId: string): Promise<{ ok: boolean }> {
  const client = createClient(projectId);
  if (!client || !projectId) {
    throw new Error("management_api_unavailable");
  }
  return client.del<{ ok: boolean }>(`/_management/projects/${projectId}/testcase/cases/${caseId}`);
}

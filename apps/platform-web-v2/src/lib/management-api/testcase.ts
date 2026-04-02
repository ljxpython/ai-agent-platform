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

export type TestcaseBatchDetailCase = {
  id: string;
  case_id?: string | null;
  title: string;
  status: string;
  batch_id?: string | null;
  module_name?: string | null;
  priority?: string | null;
  updated_at?: string | null;
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

export type TestcaseDocumentRelationCase = {
  id: string;
  case_id?: string | null;
  title: string;
  status: string;
  batch_id?: string | null;
};

export type TestcaseDocumentRelations = {
  document: TestcaseDocument;
  runtime_meta: Record<string, unknown>;
  related_cases: TestcaseDocumentRelationCase[];
  related_cases_count: number;
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
  source_documents?: TestcaseDocument[];
  missing_source_document_ids?: string[];
  content_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type TestcaseBatchDetail = {
  batch: TestcaseBatchSummary;
  documents: {
    items: TestcaseDocument[];
    total: number;
  };
  test_cases: {
    items: TestcaseBatchDetailCase[];
    total: number;
  };
};

export type TestcaseRole = {
  project_id: string;
  role: "admin" | "editor" | "executor";
  can_write_testcase: boolean;
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

export async function getTestcaseRole(projectId: string): Promise<TestcaseRole> {
  const client = createClient(projectId);
  if (!client || !projectId) {
    throw new Error("management_api_unavailable");
  }
  return client.get<TestcaseRole>(`/_management/projects/${projectId}/testcase/role`);
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

export async function getTestcaseDocumentRelations(
  projectId: string,
  documentId: string,
): Promise<TestcaseDocumentRelations> {
  const client = createClient(projectId);
  if (!client || !projectId) {
    throw new Error("management_api_unavailable");
  }
  return client.get<TestcaseDocumentRelations>(
    `/_management/projects/${projectId}/testcase/documents/${documentId}/relations`,
  );
}

export async function getTestcaseBatchDetail(
  projectId: string,
  batchId: string,
  options?: {
    document_limit?: number;
    document_offset?: number;
    case_limit?: number;
    case_offset?: number;
  },
): Promise<TestcaseBatchDetail> {
  const client = createClient(projectId);
  if (!client || !projectId) {
    throw new Error("management_api_unavailable");
  }
  const params = new URLSearchParams();
  params.set("document_limit", String(options?.document_limit ?? 100));
  params.set("document_offset", String(options?.document_offset ?? 0));
  params.set("case_limit", String(options?.case_limit ?? 50));
  params.set("case_offset", String(options?.case_offset ?? 0));
  return client.get<TestcaseBatchDetail>(
    `/_management/projects/${projectId}/testcase/batches/${encodeURIComponent(batchId)}?${params.toString()}`,
  );
}

export async function exportTestcaseDocumentsExcel(
  projectId: string,
  options?: {
    batch_id?: string;
    parse_status?: string;
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
  if (options?.parse_status?.trim()) {
    params.set("parse_status", options.parse_status.trim());
  }
  if (options?.query?.trim()) {
    params.set("query", options.query.trim());
  }
  const suffix = params.toString();
  return client.download(
    `/_management/projects/${projectId}/testcase/documents/export${suffix ? `?${suffix}` : ""}`,
  );
}

export async function previewTestcaseDocument(
  projectId: string,
  documentId: string,
): Promise<ManagementDownload> {
  const client = createClient(projectId);
  if (!client || !projectId) {
    throw new Error("management_api_unavailable");
  }
  return client.download(`/_management/projects/${projectId}/testcase/documents/${documentId}/preview`);
}

export async function downloadTestcaseDocument(
  projectId: string,
  documentId: string,
): Promise<ManagementDownload> {
  const client = createClient(projectId);
  if (!client || !projectId) {
    throw new Error("management_api_unavailable");
  }
  return client.download(`/_management/projects/${projectId}/testcase/documents/${documentId}/download`);
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
    columns?: string[];
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
  if (Array.isArray(options?.columns) && options.columns.length > 0) {
    params.set("columns", options.columns.join(","));
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
    batch_id?: string;
    case_id?: string;
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

import { platformHttpClient } from '@/services/http/client'
import {
  downloadOperationArtifact,
  submitOperation,
  waitForOperationTerminalState
} from '@/services/operations/operations.service'
import type {
  TestcaseBatchDetail,
  ManagementDownload,
  ManagementOperation,
  TestcaseBatchSummary,
  TestcaseCase,
  TestcaseDocument,
  TestcaseDocumentRelations,
  TestcaseOverview,
  TestcaseRole
} from '@/types/management'

type BatchListResponse = {
  items: TestcaseBatchSummary[]
  total: number
}

type DocumentListResponse = {
  items: TestcaseDocument[]
  total: number
}

type CaseListResponse = {
  items: TestcaseCase[]
  total: number
}

function buildHeaders(projectId: string) {
  return {
    'x-project-id': projectId
  }
}

function resolveEndpoint(projectId: string, suffix: string) {
  const normalizedSuffix = suffix.startsWith('/') ? suffix : `/${suffix}`
  return {
    client: platformHttpClient,
    path: `/api/projects/${projectId}/testcase${normalizedSuffix}`
  }
}

function parseContentDispositionFilename(header: string | null): string | null {
  if (!header) {
    return null
  }
  const utf8Match = header.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1])
    } catch {
      return utf8Match[1]
    }
  }
  const plainMatch = header.match(/filename="?([^";]+)"?/i)
  return plainMatch?.[1] ?? null
}

async function downloadFrom(
  projectId: string,
  suffix: string,
  params?: Record<string, string | number | undefined>
): Promise<ManagementDownload> {
  const { client, path } = resolveEndpoint(projectId, suffix)
  const response = await client.get(path, {
    headers: buildHeaders(projectId),
    responseType: 'blob',
    params
  })

  return {
    blob: response.data as Blob,
    filename: parseContentDispositionFilename(String(response.headers['content-disposition'] || '')),
    contentType: String(response.headers['content-type'] || '')
  }
}

export async function getTestcaseOverview(
  projectId: string
): Promise<TestcaseOverview> {
  const { client, path } = resolveEndpoint(projectId, '/overview')
  const response = await client.get(path, {
    headers: buildHeaders(projectId)
  })
  return response.data as TestcaseOverview
}

export async function getTestcaseRole(
  projectId: string
): Promise<TestcaseRole> {
  const { client, path } = resolveEndpoint(projectId, '/role')
  const response = await client.get(path, {
    headers: buildHeaders(projectId)
  })
  return response.data as TestcaseRole
}

export async function listTestcaseBatches(
  projectId: string,
  options?: { limit?: number; offset?: number }
): Promise<BatchListResponse> {
  const { client, path } = resolveEndpoint(projectId, '/batches')
  const response = await client.get(path, {
    headers: buildHeaders(projectId),
    params: {
      limit: options?.limit ?? 50,
      offset: options?.offset ?? 0
    }
  })
  return response.data as BatchListResponse
}

export async function listTestcaseDocuments(
  projectId: string,
  options?: {
    batch_id?: string
    parse_status?: string
    query?: string
    limit?: number
    offset?: number
  }
): Promise<DocumentListResponse> {
  const { client, path } = resolveEndpoint(projectId, '/documents')
  const response = await client.get(path, {
    headers: buildHeaders(projectId),
    params: {
      limit: options?.limit ?? 20,
      offset: options?.offset ?? 0,
      batch_id: options?.batch_id?.trim() || undefined,
      parse_status: options?.parse_status?.trim() || undefined,
      query: options?.query?.trim() || undefined
    }
  })
  return response.data as DocumentListResponse
}

export async function getTestcaseDocumentRelations(
  projectId: string,
  documentId: string
): Promise<TestcaseDocumentRelations> {
  const { client, path } = resolveEndpoint(projectId, `/documents/${documentId}/relations`)
  const response = await client.get(path, {
    headers: buildHeaders(projectId)
  })
  return response.data as TestcaseDocumentRelations
}

export async function exportTestcaseDocuments(
  projectId: string,
  options?: {
    batch_id?: string
    parse_status?: string
    query?: string
  }
): Promise<ManagementDownload> {
  return downloadFrom(projectId, '/documents/export', {
    batch_id: options?.batch_id?.trim() || undefined,
    parse_status: options?.parse_status?.trim() || undefined,
    query: options?.query?.trim() || undefined
  })
}

export async function exportTestcaseDocumentsByOperation(
  projectId: string,
  options?: {
    batch_id?: string
    parse_status?: string
    query?: string
    idempotencyKey?: string
  }
): Promise<{
  operation: ManagementOperation
  download: ManagementDownload
}> {
  const submitted = await submitOperation({
    kind: 'testcase.documents.export',
    project_id: projectId,
    idempotency_key: options?.idempotencyKey,
    input_payload: {
      batch_id: options?.batch_id?.trim() || undefined,
      parse_status: options?.parse_status?.trim() || undefined,
      query: options?.query?.trim() || undefined
    }
  })
  const operation = await waitForOperationTerminalState(submitted.id, {
    pollMs: 1000,
    timeoutMs: 120000
  })
  const download = await downloadOperationArtifact(operation.id)
  return {
    operation,
    download
  }
}

export async function getTestcaseDocument(
  projectId: string,
  documentId: string
): Promise<TestcaseDocument> {
  const { client, path } = resolveEndpoint(projectId, `/documents/${documentId}`)
  const response = await client.get(path, {
    headers: buildHeaders(projectId)
  })
  return response.data as TestcaseDocument
}

export async function previewTestcaseDocument(
  projectId: string,
  documentId: string
): Promise<ManagementDownload> {
  return downloadFrom(projectId, `/documents/${documentId}/preview`)
}

export async function downloadTestcaseDocument(
  projectId: string,
  documentId: string
): Promise<ManagementDownload> {
  return downloadFrom(projectId, `/documents/${documentId}/download`)
}

export async function listTestcaseCases(
  projectId: string,
  options?: {
    batch_id?: string
    status?: string
    query?: string
    limit?: number
    offset?: number
  }
): Promise<CaseListResponse> {
  const { client, path } = resolveEndpoint(projectId, '/cases')
  const response = await client.get(path, {
    headers: buildHeaders(projectId),
    params: {
      limit: options?.limit ?? 20,
      offset: options?.offset ?? 0,
      batch_id: options?.batch_id?.trim() || undefined,
      status: options?.status?.trim() || undefined,
      query: options?.query?.trim() || undefined
    }
  })
  return response.data as CaseListResponse
}

export async function exportTestcaseCases(
  projectId: string,
  options?: {
    batch_id?: string
    status?: string
    query?: string
    columns?: string[]
  }
): Promise<ManagementDownload> {
  return downloadFrom(projectId, '/cases/export', {
    batch_id: options?.batch_id?.trim() || undefined,
    status: options?.status?.trim() || undefined,
    query: options?.query?.trim() || undefined,
    columns: options?.columns?.filter((item) => item.trim()).join(',') || undefined
  })
}

export async function exportTestcaseCasesByOperation(
  projectId: string,
  options?: {
    batch_id?: string
    status?: string
    query?: string
    columns?: string[]
    idempotencyKey?: string
  }
): Promise<{
  operation: ManagementOperation
  download: ManagementDownload
}> {
  const submitted = await submitOperation({
    kind: 'testcase.cases.export',
    project_id: projectId,
    idempotency_key: options?.idempotencyKey,
    input_payload: {
      batch_id: options?.batch_id?.trim() || undefined,
      status: options?.status?.trim() || undefined,
      query: options?.query?.trim() || undefined,
      columns: options?.columns?.filter((item) => item.trim()) || undefined
    }
  })
  const operation = await waitForOperationTerminalState(submitted.id, {
    pollMs: 1000,
    timeoutMs: 120000
  })
  const download = await downloadOperationArtifact(operation.id)
  return {
    operation,
    download
  }
}

export async function getTestcaseCase(
  projectId: string,
  caseId: string
): Promise<TestcaseCase> {
  const { client, path } = resolveEndpoint(projectId, `/cases/${caseId}`)
  const response = await client.get(path, {
    headers: buildHeaders(projectId)
  })
  return response.data as TestcaseCase
}

export type UpsertTestcaseCasePayload = {
  batch_id?: string | null
  case_id?: string | null
  title?: string
  description?: string | null
  status?: string | null
  module_name?: string | null
  priority?: string | null
  source_document_ids?: string[] | null
  content_json?: Record<string, unknown> | null
}

export async function createTestcaseCase(
  projectId: string,
  payload: Required<Pick<UpsertTestcaseCasePayload, 'title'>> & UpsertTestcaseCasePayload
): Promise<TestcaseCase> {
  const { client, path } = resolveEndpoint(projectId, '/cases')
  const response = await client.post(path, payload, {
    headers: buildHeaders(projectId)
  })
  return response.data as TestcaseCase
}

export async function updateTestcaseCase(
  projectId: string,
  caseId: string,
  payload: UpsertTestcaseCasePayload
): Promise<TestcaseCase> {
  const { client, path } = resolveEndpoint(projectId, `/cases/${caseId}`)
  const response = await client.patch(path, payload, {
    headers: buildHeaders(projectId)
  })
  return response.data as TestcaseCase
}

export async function deleteTestcaseCase(
  projectId: string,
  caseId: string
): Promise<void> {
  const { client, path } = resolveEndpoint(projectId, `/cases/${caseId}`)
  await client.delete(path, {
    headers: buildHeaders(projectId)
  })
}

export async function getTestcaseBatchDetail(
  projectId: string,
  batchId: string,
  options?: {
    document_limit?: number
    document_offset?: number
    case_limit?: number
    case_offset?: number
  }
): Promise<TestcaseBatchDetail> {
  const { client, path } = resolveEndpoint(projectId, `/batches/${batchId}`)
  const response = await client.get(path, {
    headers: buildHeaders(projectId),
    params: {
      document_limit: options?.document_limit ?? 100,
      document_offset: options?.document_offset ?? 0,
      case_limit: options?.case_limit ?? 50,
      case_offset: options?.case_offset ?? 0
    }
  })
  return response.data as TestcaseBatchDetail
}

import { httpClient } from '@/services/http/client'
import type {
  ManagementDownload,
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

async function downloadFrom(path: string, projectId: string): Promise<ManagementDownload> {
  const response = await httpClient.get(path, {
    headers: {
      'x-project-id': projectId
    },
    responseType: 'blob'
  })

  return {
    blob: response.data as Blob,
    filename: parseContentDispositionFilename(String(response.headers['content-disposition'] || '')),
    contentType: String(response.headers['content-type'] || '')
  }
}

export async function getTestcaseOverview(projectId: string): Promise<TestcaseOverview> {
  const response = await httpClient.get(`/_management/projects/${projectId}/testcase/overview`, {
    headers: {
      'x-project-id': projectId
    }
  })
  return response.data as TestcaseOverview
}

export async function getTestcaseRole(projectId: string): Promise<TestcaseRole> {
  const response = await httpClient.get(`/_management/projects/${projectId}/testcase/role`, {
    headers: {
      'x-project-id': projectId
    }
  })
  return response.data as TestcaseRole
}

export async function listTestcaseBatches(
  projectId: string,
  options?: { limit?: number; offset?: number }
): Promise<BatchListResponse> {
  const response = await httpClient.get(`/_management/projects/${projectId}/testcase/batches`, {
    headers: {
      'x-project-id': projectId
    },
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
  const response = await httpClient.get(`/_management/projects/${projectId}/testcase/documents`, {
    headers: {
      'x-project-id': projectId
    },
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
  const response = await httpClient.get(
    `/_management/projects/${projectId}/testcase/documents/${documentId}/relations`,
    {
      headers: {
        'x-project-id': projectId
      }
    }
  )
  return response.data as TestcaseDocumentRelations
}

export async function previewTestcaseDocument(
  projectId: string,
  documentId: string
): Promise<ManagementDownload> {
  return downloadFrom(`/_management/projects/${projectId}/testcase/documents/${documentId}/preview`, projectId)
}

export async function downloadTestcaseDocument(
  projectId: string,
  documentId: string
): Promise<ManagementDownload> {
  return downloadFrom(`/_management/projects/${projectId}/testcase/documents/${documentId}/download`, projectId)
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
  const response = await httpClient.get(`/_management/projects/${projectId}/testcase/cases`, {
    headers: {
      'x-project-id': projectId
    },
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

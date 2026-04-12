import { platformHttpClient } from '@/services/http/client'
import type {
  KnowledgeDocumentsPage,
  KnowledgePipelineStatus,
  KnowledgeQueryResult,
  KnowledgeTrackStatus,
  ManagementOperation,
  ProjectKnowledgeSpace
} from '@/types/management'

function buildHeaders(projectId: string) {
  return {
    'x-project-id': projectId
  }
}

function resolveEndpoint(projectId: string, suffix: string) {
  const normalizedSuffix = suffix ? (suffix.startsWith('/') ? suffix : `/${suffix}`) : ''
  return `/api/projects/${projectId}/knowledge${normalizedSuffix}`
}

export async function getProjectKnowledgeSpace(projectId: string): Promise<ProjectKnowledgeSpace> {
  const response = await platformHttpClient.get(resolveEndpoint(projectId, ''), {
    headers: buildHeaders(projectId)
  })
  return response.data as ProjectKnowledgeSpace
}

export async function refreshProjectKnowledgeSpace(projectId: string): Promise<ProjectKnowledgeSpace> {
  const response = await platformHttpClient.post(resolveEndpoint(projectId, '/refresh'), undefined, {
    headers: buildHeaders(projectId)
  })
  return response.data as ProjectKnowledgeSpace
}

export async function uploadProjectKnowledgeDocument(
  projectId: string,
  file: File
): Promise<Record<string, unknown>> {
  const response = await platformHttpClient.post(resolveEndpoint(projectId, '/documents/upload'), file, {
    headers: {
      ...buildHeaders(projectId),
      'content-type': file.type || 'application/octet-stream',
      'x-knowledge-filename': encodeURIComponent(file.name)
    }
  })
  return response.data as Record<string, unknown>
}

export async function startProjectKnowledgeScan(projectId: string): Promise<ManagementOperation> {
  const response = await platformHttpClient.post(resolveEndpoint(projectId, '/documents/scan'), undefined, {
    headers: buildHeaders(projectId)
  })
  return response.data as ManagementOperation
}

export async function clearProjectKnowledgeDocuments(projectId: string): Promise<ManagementOperation> {
  const response = await platformHttpClient.delete(resolveEndpoint(projectId, '/documents'), {
    headers: buildHeaders(projectId)
  })
  return response.data as ManagementOperation
}

export async function listProjectKnowledgeDocuments(
  projectId: string,
  options?: {
    page?: number
    page_size?: number
    status_filter?: string
    sort_field?: string
    sort_direction?: 'asc' | 'desc'
  }
): Promise<KnowledgeDocumentsPage> {
  const response = await platformHttpClient.post(
    resolveEndpoint(projectId, '/documents/paginated'),
    {
      page: options?.page ?? 1,
      page_size: options?.page_size ?? 20,
      status_filter: options?.status_filter?.trim() || undefined,
      sort_field: options?.sort_field ?? 'updated_at',
      sort_direction: options?.sort_direction ?? 'desc'
    },
    {
      headers: buildHeaders(projectId)
    }
  )
  return response.data as KnowledgeDocumentsPage
}

export async function getProjectKnowledgeTrackStatus(
  projectId: string,
  trackId: string
): Promise<KnowledgeTrackStatus> {
  const response = await platformHttpClient.get(
    resolveEndpoint(projectId, `/documents/track-status/${encodeURIComponent(trackId)}`),
    {
      headers: buildHeaders(projectId)
    }
  )
  return response.data as KnowledgeTrackStatus
}

export async function getProjectKnowledgePipelineStatus(
  projectId: string
): Promise<KnowledgePipelineStatus> {
  const response = await platformHttpClient.get(resolveEndpoint(projectId, '/documents/pipeline-status'), {
    headers: buildHeaders(projectId)
  })
  return response.data as KnowledgePipelineStatus
}

export async function deleteProjectKnowledgeDocument(
  projectId: string,
  documentId: string
): Promise<Record<string, unknown>> {
  const response = await platformHttpClient.delete(
    resolveEndpoint(projectId, `/documents/${encodeURIComponent(documentId)}`),
    {
      headers: buildHeaders(projectId)
    }
  )
  return response.data as Record<string, unknown>
}

export async function queryProjectKnowledge(
  projectId: string,
  payload: {
    query: string
    mode?: string
    include_references?: boolean
    include_chunk_content?: boolean
  }
): Promise<KnowledgeQueryResult> {
  const response = await platformHttpClient.post(resolveEndpoint(projectId, '/query'), payload, {
    headers: buildHeaders(projectId)
  })
  return response.data as KnowledgeQueryResult
}

export async function listProjectKnowledgeGraphLabels(projectId: string): Promise<string[]> {
  const response = await platformHttpClient.get(resolveEndpoint(projectId, '/graph/label/list'), {
    headers: buildHeaders(projectId)
  })
  return response.data as string[]
}

export async function searchProjectKnowledgeGraphLabels(
  projectId: string,
  query: string,
  limit = 50
): Promise<string[]> {
  const response = await platformHttpClient.get(resolveEndpoint(projectId, '/graph/label/search'), {
    headers: buildHeaders(projectId),
    params: {
      q: query.trim(),
      limit
    }
  })
  return response.data as string[]
}

export async function getProjectKnowledgeGraph(
  projectId: string,
  options: {
    label: string
    max_depth?: number
    max_nodes?: number
  }
): Promise<Record<string, unknown>> {
  const response = await platformHttpClient.get(resolveEndpoint(projectId, '/graphs'), {
    headers: buildHeaders(projectId),
    params: {
      label: options.label,
      max_depth: options.max_depth ?? 3,
      max_nodes: options.max_nodes ?? 200
    }
  })
  return response.data as Record<string, unknown>
}

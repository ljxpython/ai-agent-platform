import {
  platformApiBaseUrl,
  platformHttpClient,
  resolveAuthorizedAccessToken,
} from '@/services/http/client'
import type {
  KnowledgeDocumentsPage,
  KnowledgeDocumentsScanProgress,
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

export async function getProjectKnowledgeScanProgress(
  projectId: string
): Promise<KnowledgeDocumentsScanProgress> {
  const response = await platformHttpClient.get(resolveEndpoint(projectId, '/documents/scan-progress'), {
    headers: buildHeaders(projectId)
  })
  return response.data as KnowledgeDocumentsScanProgress
}

export async function reprocessFailedProjectKnowledgeDocuments(
  projectId: string
): Promise<Record<string, unknown>> {
  const response = await platformHttpClient.post(
    resolveEndpoint(projectId, '/documents/reprocess-failed'),
    undefined,
    {
      headers: buildHeaders(projectId)
    }
  )
  return response.data as Record<string, unknown>
}

export async function cancelProjectKnowledgePipeline(
  projectId: string
): Promise<Record<string, unknown>> {
  const response = await platformHttpClient.post(
    resolveEndpoint(projectId, '/documents/cancel-pipeline'),
    undefined,
    {
      headers: buildHeaders(projectId)
    }
  )
  return response.data as Record<string, unknown>
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

export async function getProjectKnowledgeDocumentDetail(
  projectId: string,
  documentId: string
): Promise<Record<string, unknown>> {
  const response = await platformHttpClient.get(
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
    only_need_context?: boolean
    only_need_prompt?: boolean
    response_type?: string
    stream?: boolean
    top_k?: number
    chunk_top_k?: number
    max_entity_tokens?: number
    max_relation_tokens?: number
    max_total_tokens?: number
    user_prompt?: string
    enable_rerank?: boolean
    include_references?: boolean
    include_chunk_content?: boolean
  }
): Promise<KnowledgeQueryResult> {
  const response = await platformHttpClient.post(resolveEndpoint(projectId, '/query'), payload, {
    headers: buildHeaders(projectId)
  })
  return response.data as KnowledgeQueryResult
}

export async function streamProjectKnowledgeQuery(
  projectId: string,
  payload: {
    query: string
    mode?: string
    only_need_context?: boolean
    only_need_prompt?: boolean
    response_type?: string
    stream?: boolean
    top_k?: number
    chunk_top_k?: number
    max_entity_tokens?: number
    max_relation_tokens?: number
    max_total_tokens?: number
    user_prompt?: string
    enable_rerank?: boolean
    include_references?: boolean
    include_chunk_content?: boolean
  },
  handlers: {
    onReferences?: (references: KnowledgeQueryResult['references']) => void
    onChunk: (chunk: string) => void
  }
) {
  const token = (await resolveAuthorizedAccessToken()).trim()
  const response = await fetch(
    `${platformApiBaseUrl}${resolveEndpoint(projectId, '/query/stream')}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...buildHeaders(projectId),
      },
      body: JSON.stringify(payload),
    },
  )

  if (!response.ok || !response.body) {
    throw new Error(`knowledge_query_stream_failed:${response.status}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  const processLine = (line: string) => {
    if (!line.trim()) {
      return
    }

    const parsed = JSON.parse(line) as KnowledgeQueryResult | { response?: string; references?: KnowledgeQueryResult['references']; error?: string }
    if ('error' in parsed && parsed.error) {
      throw new Error(parsed.error)
    }
    if ('references' in parsed && parsed.references) {
      handlers.onReferences?.(parsed.references)
    }
    if ('response' in parsed && parsed.response) {
      handlers.onChunk(parsed.response)
    }
  }

  while (true) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value, { stream: !done })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      processLine(line)
    }

    if (done) {
      break
    }
  }

  processLine(buffer)
}

export async function listProjectKnowledgeGraphLabels(projectId: string): Promise<string[]> {
  const response = await platformHttpClient.get(resolveEndpoint(projectId, '/graph/label/list'), {
    headers: buildHeaders(projectId)
  })
  return response.data as string[]
}

export async function listProjectKnowledgePopularGraphLabels(
  projectId: string,
  limit = 10
): Promise<string[]> {
  const response = await platformHttpClient.get(resolveEndpoint(projectId, '/graph/label/popular'), {
    headers: buildHeaders(projectId),
    params: {
      limit
    }
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

export async function checkProjectKnowledgeEntityExists(
  projectId: string,
  entityName: string
): Promise<boolean> {
  const response = await platformHttpClient.get(resolveEndpoint(projectId, '/graph/entity/exists'), {
    headers: buildHeaders(projectId),
    params: {
      name: entityName.trim()
    }
  })
  return Boolean((response.data as { exists?: boolean }).exists)
}

export async function updateProjectKnowledgeEntity(
  projectId: string,
  payload: {
    entity_name: string
    updated_data: Record<string, unknown>
    allow_rename?: boolean
    allow_merge?: boolean
  }
): Promise<Record<string, unknown>> {
  const response = await platformHttpClient.post(resolveEndpoint(projectId, '/graph/entity/edit'), payload, {
    headers: buildHeaders(projectId)
  })
  return response.data as Record<string, unknown>
}

export async function updateProjectKnowledgeRelation(
  projectId: string,
  payload: {
    source_id: string
    target_id: string
    updated_data: Record<string, unknown>
  }
): Promise<Record<string, unknown>> {
  const response = await platformHttpClient.post(resolveEndpoint(projectId, '/graph/relation/edit'), payload, {
    headers: buildHeaders(projectId)
  })
  return response.data as Record<string, unknown>
}

export async function deleteProjectKnowledgeEntity(
  projectId: string,
  entityName: string
): Promise<Record<string, unknown>> {
  const response = await platformHttpClient.delete(resolveEndpoint(projectId, '/graph/entity'), {
    headers: buildHeaders(projectId),
    data: {
      entity_name: entityName.trim()
    }
  })
  return response.data as Record<string, unknown>
}

export async function deleteProjectKnowledgeRelation(
  projectId: string,
  payload: {
    source_entity: string
    target_entity: string
  }
): Promise<Record<string, unknown>> {
  const response = await platformHttpClient.delete(resolveEndpoint(projectId, '/graph/relation'), {
    headers: buildHeaders(projectId),
    data: {
      source_entity: payload.source_entity.trim(),
      target_entity: payload.target_entity.trim()
    }
  })
  return response.data as Record<string, unknown>
}

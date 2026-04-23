import { beforeEach, describe, expect, it, vi } from 'vitest'

const { platformHttpClientMock, resolveAuthorizedAccessTokenMock } = vi.hoisted(() => ({
  platformHttpClientMock: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn()
  },
  resolveAuthorizedAccessTokenMock: vi.fn()
}))

vi.mock('@/services/http/client', () => ({
  platformApiBaseUrl: 'http://platform.test',
  platformHttpClient: platformHttpClientMock,
  resolveAuthorizedAccessToken: resolveAuthorizedAccessTokenMock
}))

import {
  cancelProjectKnowledgePipeline,
  getProjectKnowledgeSpace,
  getProjectKnowledgeScanProgress,
  getProjectKnowledgeDocumentDetail,
  listProjectKnowledgeDocuments,
  listProjectKnowledgePopularGraphLabels,
  refreshProjectKnowledgeSpace,
  reprocessFailedProjectKnowledgeDocuments,
  searchProjectKnowledgeGraphLabels,
  streamProjectKnowledgeQuery,
  uploadProjectKnowledgeDocument
} from './knowledge.service'

describe('knowledge.service', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    resolveAuthorizedAccessTokenMock.mockResolvedValue('token-1')
  })

  it('builds the project knowledge endpoint and project header for space fetches', async () => {
    const expected = { project_id: 'project-42' }
    platformHttpClientMock.get.mockResolvedValue({ data: expected })

    await expect(getProjectKnowledgeSpace('project-42')).resolves.toEqual(expected)

    expect(platformHttpClientMock.get).toHaveBeenCalledWith('/api/projects/project-42/knowledge', {
      headers: {
        'x-project-id': 'project-42'
      }
    })
  })

  it('keeps refresh requests on the non-redirected settings route family', async () => {
    const expected = { status: 'ok' }
    platformHttpClientMock.post.mockResolvedValue({ data: expected })

    await expect(refreshProjectKnowledgeSpace('project-42')).resolves.toEqual(expected)

    expect(platformHttpClientMock.post).toHaveBeenCalledWith(
      '/api/projects/project-42/knowledge/refresh',
      undefined,
      {
        headers: {
          'x-project-id': 'project-42'
        }
      }
    )
  })

  it('sends upload requests with encoded filename and file content type headers', async () => {
    const file = new File(['# Knowledge'], 'roadmap & scope.md', { type: 'text/markdown' })
    const expected = { document_id: 'doc-1' }
    platformHttpClientMock.post.mockResolvedValue({ data: expected })

    await expect(uploadProjectKnowledgeDocument('project-42', file)).resolves.toEqual(expected)

    expect(platformHttpClientMock.post).toHaveBeenCalledWith(
      '/api/projects/project-42/knowledge/documents/upload',
      file,
      {
        headers: {
          'x-project-id': 'project-42',
          'content-type': 'text/markdown',
          'x-knowledge-filename': 'roadmap%20%26%20scope.md'
        }
      }
    )
  })

  it('posts paginated document queries with defaulted pagination and normalized filters', async () => {
    const expected = { items: [], total: 0, page: 1, page_size: 20 }
    platformHttpClientMock.post.mockResolvedValue({ data: expected })

    await expect(
      listProjectKnowledgeDocuments('project-42', {
        status_filter: '   '
      })
    ).resolves.toEqual(expected)

    expect(platformHttpClientMock.post).toHaveBeenCalledWith(
      '/api/projects/project-42/knowledge/documents/paginated',
      {
        page: 1,
        page_size: 20,
        status_filter: undefined,
        sort_field: 'updated_at',
        sort_direction: 'desc'
      },
      {
        headers: {
          'x-project-id': 'project-42'
        }
      }
    )
  })

  it('routes scan progress and pipeline actions through the project-scoped endpoints', async () => {
    platformHttpClientMock.get.mockResolvedValue({ data: { progress: 75 } })
    platformHttpClientMock.post.mockResolvedValue({ data: { status: 'ok' } })

    await expect(getProjectKnowledgeScanProgress('project-42')).resolves.toEqual({ progress: 75 })
    await expect(reprocessFailedProjectKnowledgeDocuments('project-42')).resolves.toEqual({
      status: 'ok'
    })
    await expect(cancelProjectKnowledgePipeline('project-42')).resolves.toEqual({ status: 'ok' })

    expect(platformHttpClientMock.get).toHaveBeenCalledWith(
      '/api/projects/project-42/knowledge/documents/scan-progress',
      {
        headers: {
          'x-project-id': 'project-42'
        }
      }
    )
    expect(platformHttpClientMock.post).toHaveBeenNthCalledWith(
      1,
      '/api/projects/project-42/knowledge/documents/reprocess-failed',
      undefined,
      {
        headers: {
          'x-project-id': 'project-42'
        }
      }
    )
    expect(platformHttpClientMock.post).toHaveBeenNthCalledWith(
      2,
      '/api/projects/project-42/knowledge/documents/cancel-pipeline',
      undefined,
      {
        headers: {
          'x-project-id': 'project-42'
        }
      }
    )
  })

  it('loads project-scoped document detail from the dedicated endpoint', async () => {
    const expected = { id: 'doc-1', file_path: 'a.txt' }
    platformHttpClientMock.get.mockResolvedValue({ data: expected })

    await expect(getProjectKnowledgeDocumentDetail('project-42', 'doc-1')).resolves.toEqual(expected)

    expect(platformHttpClientMock.get).toHaveBeenCalledWith(
      '/api/projects/project-42/knowledge/documents/doc-1',
      {
        headers: {
          'x-project-id': 'project-42'
        }
      }
    )
  })

  it('trims graph label searches and forwards the explicit limit', async () => {
    const expected = ['Architecture', 'Scope']
    platformHttpClientMock.get.mockResolvedValue({ data: expected })

    await expect(searchProjectKnowledgeGraphLabels('project-42', '  arch  ', 10)).resolves.toEqual(
      expected
    )

    expect(platformHttpClientMock.get).toHaveBeenCalledWith(
      '/api/projects/project-42/knowledge/graph/label/search',
      {
        headers: {
          'x-project-id': 'project-42'
        },
        params: {
          q: 'arch',
          limit: 10
        }
      }
    )
  })

  it('loads popular graph labels from the project-scoped helper endpoint', async () => {
    const expected = ['Popular A', 'Popular B']
    platformHttpClientMock.get.mockResolvedValue({ data: expected })

    await expect(listProjectKnowledgePopularGraphLabels('project-42', 7)).resolves.toEqual(expected)

    expect(platformHttpClientMock.get).toHaveBeenCalledWith(
      '/api/projects/project-42/knowledge/graph/label/popular',
      {
        headers: {
          'x-project-id': 'project-42'
        },
        params: {
          limit: 7
        }
      }
    )
  })

  it('streams knowledge query chunks and references through the project endpoint', async () => {
    const read = vi
      .fn()
      .mockResolvedValueOnce({
        done: false,
        value: new TextEncoder().encode(
          '{"references":[{"reference_id":"1","file_path":"a.txt"}]}\n{"response":"hello "}\n{"response":"world"}\n'
        )
      })
      .mockResolvedValueOnce({
        done: true,
        value: undefined
      })

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        body: {
          getReader: () => ({ read })
        }
      })
    )

    const references: unknown[] = []
    const chunks: string[] = []

    await streamProjectKnowledgeQuery(
      'project-42',
      {
        query: 'hello',
        stream: true
      },
      {
        onReferences(next) {
          references.push(next)
        },
        onChunk(chunk) {
          chunks.push(chunk)
        }
      }
    )

    expect(fetch).toHaveBeenCalledWith(
      'http://platform.test/api/projects/project-42/knowledge/query/stream',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          Authorization: 'Bearer token-1',
          'x-project-id': 'project-42'
        })
      })
    )
    expect(references).toEqual([[{ reference_id: '1', file_path: 'a.txt' }]])
    expect(chunks).toEqual(['hello ', 'world'])
    vi.unstubAllGlobals()
  })
})

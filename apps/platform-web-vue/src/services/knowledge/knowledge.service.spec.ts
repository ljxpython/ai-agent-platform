import { beforeEach, describe, expect, it, vi } from 'vitest'

const { platformHttpClientMock } = vi.hoisted(() => ({
  platformHttpClientMock: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn()
  }
}))

vi.mock('@/services/http/client', () => ({
  platformHttpClient: platformHttpClientMock
}))

import {
  getProjectKnowledgeSpace,
  listProjectKnowledgeDocuments,
  refreshProjectKnowledgeSpace,
  searchProjectKnowledgeGraphLabels,
  uploadProjectKnowledgeDocument
} from './knowledge.service'

describe('knowledge.service', () => {
  beforeEach(() => {
    vi.clearAllMocks()
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
})

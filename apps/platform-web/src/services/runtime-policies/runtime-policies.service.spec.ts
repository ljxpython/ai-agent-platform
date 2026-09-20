import { beforeEach, describe, expect, it, vi } from 'vitest'

const { platformHttpClientMock } = vi.hoisted(() => ({
  platformHttpClientMock: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn()
  }
}))

vi.mock('@/services/http/client', () => ({ platformHttpClient: platformHttpClientMock }))

import {
  createToolRestriction,
  deleteToolRestriction,
  listToolRestrictions
} from './runtime-policies.service'

describe('runtime policies tool restrictions service', () => {
  beforeEach(() => vi.clearAllMocks())

  it('lists tool restrictions with correct path', async () => {
    platformHttpClientMock.get.mockResolvedValue({ data: { items: [], total: 0 } })

    const result = await listToolRestrictions('proj-123')

    expect(platformHttpClientMock.get).toHaveBeenCalledWith(
      '/api/projects/proj-123/runtime-policies/tool-restrictions'
    )
    expect(result).toEqual({ items: [], total: 0 })
  })

  it('creates tool restriction with exact payload', async () => {
    const payload = {
      graph_id: 'dearflow_agent',
      subject_type: 'user' as const,
      subject_id: '11111111-1111-1111-1111-111111111111',
      tool_name: 'execute',
      reason: '禁止执行终端命令'
    }
    const mockCreated = {
      ...payload,
      id: '22222222-2222-2222-2222-222222222222',
      project_id: 'proj-123',
      created_by: 'admin',
      created_at: '2026-09-20T12:00:00Z'
    }
    platformHttpClientMock.post.mockResolvedValue({ data: mockCreated })

    const result = await createToolRestriction('proj-123', payload)

    expect(platformHttpClientMock.post).toHaveBeenCalledWith(
      '/api/projects/proj-123/runtime-policies/tool-restrictions',
      payload
    )
    expect(result).toEqual(mockCreated)
  })

  it('deletes tool restriction by id', async () => {
    platformHttpClientMock.delete.mockResolvedValue({ data: undefined })

    await deleteToolRestriction('proj-123', 'rest-999')

    expect(platformHttpClientMock.delete).toHaveBeenCalledWith(
      '/api/projects/proj-123/runtime-policies/tool-restrictions/rest-999'
    )
  })
})

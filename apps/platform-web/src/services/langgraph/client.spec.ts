import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/http/client', () => ({
  platformApiBaseUrl: 'https://platform.example.com',
  refreshAccessToken: async () => '',
  resolveAuthorizedAccessToken: async () => ''
}))

import { createLanggraphAuthorizedFetch, getLanggraphApiUrl } from './client'
import { clearTokenSet } from '@/services/auth/token'

describe('createLanggraphAuthorizedFetch', () => {
  it('rejects late SDK responses after logout and does not reuse the old client', async () => {
    let complete!: (response: Response) => void
    const fetchImpl = vi.fn<typeof fetch>().mockImplementationOnce(() => new Promise(resolve => { complete = resolve }))
    const client = createLanggraphAuthorizedFetch({ fetchImpl, getAccessToken: () => 'old' })
    const request = client('https://example.com/threads')
    const result = expect(request).rejects.toThrow('登录会话已变更')
    await vi.waitFor(() => expect(complete).toBeTypeOf('function'))
    clearTokenSet()
    complete(new Response('{}'))
    await result
    await expect(client('https://example.com/threads')).rejects.toThrow('登录会话已变更')
    expect(fetchImpl).toHaveBeenCalledTimes(1)
  })
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('builds an absolute /api/langgraph base url from platformApiBaseUrl', () => {
    expect(getLanggraphApiUrl()).toBe('https://platform.example.com/api/langgraph')
  })

  it('uses the latest access token on the first request', async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(new Response(null, { status: 200 }))
    const authFetch = createLanggraphAuthorizedFetch({
      fetchImpl,
      getAccessToken: () => 'latest-token',
      refreshAccessToken: async () => ''
    })

    await authFetch('http://example.com/runs', { method: 'POST' })

    expect(fetchImpl).toHaveBeenCalledTimes(1)
    expect(new Headers(fetchImpl.mock.calls[0]?.[1]?.headers).get('Authorization')).toBe(
      'Bearer latest-token'
    )
  })

  it('refreshes once and retries when the first response is 401', async () => {
    const fetchImpl = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(new Response('expired', { status: 401 }))
      .mockResolvedValueOnce(new Response(null, { status: 200 }))
    const refreshToken = vi.fn(async () => 'refreshed-token')

    const authFetch = createLanggraphAuthorizedFetch({
      fetchImpl,
      getAccessToken: () => 'expired-token',
      refreshAccessToken: refreshToken
    })

    const response = await authFetch('http://example.com/runs', { method: 'POST' })

    expect(response.status).toBe(200)
    expect(refreshToken).toHaveBeenCalledTimes(1)
    expect(fetchImpl).toHaveBeenCalledTimes(2)
    expect(new Headers(fetchImpl.mock.calls[0]?.[1]?.headers).get('Authorization')).toBe(
      'Bearer expired-token'
    )
    expect(new Headers(fetchImpl.mock.calls[1]?.[1]?.headers).get('Authorization')).toBe(
      'Bearer refreshed-token'
    )
  })

  it('adds one idempotency key to a thread command and reuses it after authentication refresh', async () => {
    const fetchImpl = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(new Response('expired', { status: 401 }))
      .mockResolvedValueOnce(new Response(null, { status: 200 }))
    const authFetch = createLanggraphAuthorizedFetch({
      fetchImpl,
      getAccessToken: () => 'expired-token',
      refreshAccessToken: async () => 'refreshed-token'
    })

    await authFetch('http://example.com/api/langgraph/threads/thread-1/commands', {
      method: 'POST',
      body: JSON.stringify({ method: 'run.start' })
    })

    const firstKey = new Headers(fetchImpl.mock.calls[0]?.[1]?.headers).get('Idempotency-Key')
    const retryKey = new Headers(fetchImpl.mock.calls[1]?.[1]?.headers).get('Idempotency-Key')
    expect(firstKey).toMatch(/^run:/)
    expect(retryKey).toBe(firstKey)
  })

  it('returns the original 401 response when refresh fails', async () => {
    const fetchImpl = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(new Response('expired', { status: 401 }))
    const authFetch = createLanggraphAuthorizedFetch({
      fetchImpl,
      getAccessToken: () => 'expired-token',
      refreshAccessToken: async () => ''
    })

    const response = await authFetch('http://example.com/runs', { method: 'POST' })

    expect(response.status).toBe(401)
    expect(fetchImpl).toHaveBeenCalledTimes(1)
  })

  it('flattens the platform error envelope for the protocol SDK', async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          error: {
            code: 'thread_active_run_conflict',
            message: 'The thread already has an active Durable Run'
          }
        }),
        { status: 409, statusText: 'Conflict' }
      )
    )
    const authFetch = createLanggraphAuthorizedFetch({
      fetchImpl,
      getAccessToken: () => 'token',
      refreshAccessToken: async () => ''
    })

    const response = await authFetch('http://example.com/api/langgraph/threads/thread-1/runs', {
      method: 'POST'
    })

    expect(await response.json()).toMatchObject({
      code: 'thread_active_run_conflict',
      message: 'The thread already has an active Durable Run',
      error: 'The thread already has an active Durable Run'
    })
  })
})

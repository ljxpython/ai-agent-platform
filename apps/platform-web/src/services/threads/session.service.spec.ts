import { expect, it, vi } from 'vitest'
import { createSessionService } from './session.service'

it('uses SDK graphId and the public checkpoint wire contract', async () => {
  const requests: Array<{ url: string; body?: Record<string, unknown>; headers: Headers }> = []
  const transport = vi.fn<typeof fetch>(async (input, init) => {
    requests.push({ url: String(input), body: typeof init?.body === 'string' ? JSON.parse(init.body) : undefined, headers: new Headers(init?.headers) })
    return new Response(JSON.stringify({ thread_id: 'thread' }), { headers: { 'content-type': 'application/json' } })
  })
  const service = createSessionService(transport, 'project')
  await service.create('workflow_demo', 'agent', '标题')
  await service.state('thread', { checkpoint_id: 'check', checkpoint_ns: '' })
  await service.history('thread', { checkpoint_id: 'check', checkpoint_ns: '' })
  expect(requests[0]?.body?.metadata).toEqual({ graph_id: 'workflow_demo', agent_id: 'agent', title: '标题' })
  expect(requests[1]?.url).toMatch(/\/threads\/thread\/state\?checkpoint_id=check$/)
  expect(requests[2]?.body?.before).toEqual({ checkpoint_id: 'check', checkpoint_ns: '' })
  expect(requests.every(request => request.headers.get('x-project-id') === 'project')).toBe(true)
})

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
  await service.fork('thread', 'check', '分支标题')
  await service.resume('thread', { approval: { decisions: [{ type: 'approve' }] } })
  expect(requests[0]?.body?.metadata).toEqual({ graph_id: 'workflow_demo', agent_id: 'agent', title: '标题' })
  expect(requests[1]?.url).toMatch(/\/threads\/thread\/state\?checkpoint_id=check$/)
  expect(requests[2]?.body?.before).toEqual({ checkpoint_id: 'check', checkpoint_ns: '' })
  expect(requests[3]?.url).toMatch(/\/threads\/thread\/fork$/)
  expect(requests[3]?.body).toEqual({ checkpoint_id: 'check', title: '分支标题' })
  expect(requests[4]?.url).toMatch(/\/threads\/thread\/runs$/)
  expect(requests[4]?.body).toEqual({ command: { resume: { approval: { decisions: [{ type: 'approve' }] } } } })
  expect(requests.every(request => request.headers.get('x-project-id') === 'project')).toBe(true)
})

it('passes metadata and pagination options to search and count', async () => {
  const requests: Array<{ url: string; body?: Record<string, unknown> }> = []
  const transport = vi.fn<typeof fetch>(async (input, init) => {
    requests.push({ url: String(input), body: typeof init?.body === 'string' ? JSON.parse(init.body) : undefined })
    return new Response(JSON.stringify([{ thread_id: 't-1' }]), { headers: { 'content-type': 'application/json' } })
  })
  const service = createSessionService(transport, 'project')
  await service.list({ offset: 20, metadata: { agent_id: 'agent-1' } })
  await service.count({ metadata: { agent_id: 'agent-1' } })

  expect(requests[0]?.url).toMatch(/\/threads\/search$/)
  expect(requests[0]?.body?.offset).toBe(20)
  expect(requests[0]?.body?.metadata).toEqual({ agent_id: 'agent-1' })

  expect(requests[1]?.url).toMatch(/\/threads\/count$/)
  expect(requests[1]?.body?.metadata).toEqual({ agent_id: 'agent-1' })
})

it('unwraps object response into integer count', async () => {
  const transport = vi.fn<typeof fetch>(async () => {
    return new Response(JSON.stringify({ count: 42 }), { headers: { 'content-type': 'application/json' } })
  })
  const service = createSessionService(transport, 'project')
  const count = await service.count({ metadata: { agent_id: 'agent-1' } })
  expect(count).toBe(42)
})

it('updates thread metadata with PATCH request', async () => {
  const requests: Array<{ url: string; method?: string; body?: Record<string, unknown> }> = []
  const transport = vi.fn<typeof fetch>(async (input, init) => {
    requests.push({
      url: String(input),
      method: init?.method,
      body: typeof init?.body === 'string' ? JSON.parse(init.body) : undefined
    })
    return new Response(JSON.stringify({ thread_id: 'thread-1', metadata: { title: '新标题' } }), {
      headers: { 'content-type': 'application/json' }
    })
  })
  const service = createSessionService(transport, 'project')
  await service.update('thread-1', { title: '新标题', preview: '消息摘要' })

  expect(requests[0]?.url).toMatch(/\/threads\/thread-1$/)
  expect(requests[0]?.method).toBe('PATCH')
  expect(requests[0]?.body).toEqual({ title: '新标题', preview: '消息摘要' })
})

it('summarizes thread title with POST request', async () => {
  const requests: Array<{ url: string; method?: string; body?: Record<string, unknown> }> = []
  const transport = vi.fn<typeof fetch>(async (input, init) => {
    requests.push({
      url: String(input),
      method: init?.method,
      body: typeof init?.body === 'string' ? JSON.parse(init.body) : undefined
    })
    return new Response(JSON.stringify({ thread_id: 'thread-1', title: '智能标题' }), {
      headers: { 'content-type': 'application/json' }
    })
  })
  const service = createSessionService(transport, 'project')
  const res = await service.summarizeTitle('thread-1', [{ role: 'user', content: '测试消息' }])

  expect(requests[0]?.url).toMatch(/\/threads\/thread-1\/title\/summarize$/)
  expect(requests[0]?.method).toBe('POST')
  expect(requests[0]?.body).toEqual({ messages: [{ role: 'user', content: '测试消息' }] })
  expect(res.title).toBe('智能标题')
})


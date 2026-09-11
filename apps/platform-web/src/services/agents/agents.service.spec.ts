import { beforeEach, expect, it, vi } from 'vitest'
import type { UpdateAgentInput } from './types'

const http = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() }))
vi.mock('@/services/http/client', () => ({ platformHttpClient: http }))
import { listAgents, getAgent, updateAgent } from './agents.service'

beforeEach(() => {
  vi.clearAllMocks()
  http.post.mockResolvedValue({ data: {} })
  http.patch.mockResolvedValue({ data: {} })
  http.get.mockResolvedValue({ data: { id: 'agent-uuid' } })
})

it('lists aligned Agents for one Graph in the current project', async () => {
  await listAgents('project', { graphId: 'graph', limit: 1 })
  expect(http.get).toHaveBeenCalledWith('/api/projects/project/agents', {
    headers: { 'x-project-id': 'project' },
    params: { limit: 1, offset: 0, query: undefined, graph_id: 'graph' }
  })
})

it('updates cannot change graph or send removed fields and can clear context', async () => {
  await updateAgent('project', 'agent', { graph_id: 'other', config: {}, context: {} } as UpdateAgentInput)
  expect(http.patch.mock.calls[0]?.[1]).toEqual({ name: undefined, description: undefined,
    status: undefined, context: {} })
})

it('reads an exact Agent UUID in a fixed project instead of searching the first page', async () => {
  await getAgent('project-A', 'agent-uuid')
  expect(http.get).toHaveBeenCalledWith('/api/agents/agent-uuid', { headers: { 'x-project-id': 'project-A' } })
  await expect(getAgent('', 'agent-uuid')).rejects.toThrow('请选择项目')
})

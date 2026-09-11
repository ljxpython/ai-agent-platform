import { platformHttpClient } from '@/services/http/client'
import type { Agent, AgentPage, UpdateAgentInput } from './types'

function scoped(projectId: string) {
  if (!projectId.trim()) throw new Error('请选择项目')
  return { headers: { 'x-project-id': projectId } }
}

export async function listAgents(projectId: string, options: {
  limit?: number; offset?: number; query?: string; graphId?: string
} = {}): Promise<AgentPage> {
  const { data } = await platformHttpClient.get<AgentPage>(
    `/api/projects/${encodeURIComponent(projectId)}/agents`, {
      ...scoped(projectId),
      params: { limit: options.limit ?? 20, offset: options.offset ?? 0,
        query: options.query?.trim() || undefined, graph_id: options.graphId }
    }
  )
  return data
}

export async function getAgent(projectId: string, agentId: string): Promise<Agent> {
  const { data } = await platformHttpClient.get<Agent>(`/api/agents/${encodeURIComponent(agentId)}`, scoped(projectId))
  return data
}

export async function updateAgent(projectId: string, agentId: string, input: UpdateAgentInput): Promise<Agent> {
  const { name, description, status, context } = input
  const { data } = await platformHttpClient.patch<Agent>(
    `/api/agents/${encodeURIComponent(agentId)}`, { name, description, status, context }, scoped(projectId)
  )
  return data
}

export async function getAgentParameterSchema(projectId: string, graphId: string): Promise<Record<string, unknown>> {
  const { data } = await platformHttpClient.get<Record<string, unknown>>(
    `/api/graphs/${encodeURIComponent(graphId)}/assistant-parameter-schema`, scoped(projectId)
  )
  return data
}

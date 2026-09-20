export type AgentContext = {
  model_id?: string
  temperature?: number
  max_tokens?: number
  top_p?: number
  execution_mode?: 'flash' | 'standard' | 'pro' | 'ultra'
}

export type Agent = {
  id: string
  project_id: string
  graph_id: string
  name: string
  description: string
  status: 'active' | 'disabled'
  context: AgentContext
  created_by?: string | null
  updated_by?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export type UpdateAgentInput = Partial<Pick<Agent, 'name' | 'description' | 'status' | 'context'>>

export type CreateAgentInput = {
  graph_id: string
  name: string
  description?: string
  context?: AgentContext
}

export type AgentPage = { items: Agent[]; total: number }

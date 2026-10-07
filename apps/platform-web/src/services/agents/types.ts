export type AgentContext = {
  model_id?: string;
  temperature?: number;
  max_tokens?: number;
  top_p?: number;
  execution_mode?: "flash" | "standard" | "pro" | "ultra";
};

export type ModelResilienceSettings = {
  enabled: boolean;
  fallback_model_id: string | null;
  max_attempts: number;
  attempt_timeout_seconds: number;
  total_timeout_seconds: number;
};

export type Agent = {
  id: string;
  project_id: string;
  graph_id: string;
  name: string;
  description: string;
  status: "active" | "disabled";
  context: AgentContext;
  model_resilience?: ModelResilienceSettings | null;
  created_by?: string | null;
  updated_by?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type UpdateAgentInput = Partial<
  Pick<Agent, "name" | "description" | "status" | "context">
> & {
  model_resilience?: ModelResilienceSettings | null;
};

export type CreateAgentInput = {
  graph_id: string;
  name: string;
  description?: string;
  context?: AgentContext;
  model_resilience?: ModelResilienceSettings | null;
};

export type AgentPage = { items: Agent[]; total: number };

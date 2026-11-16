export interface BootstrapConfig {
  project_id: string;
  personal_project: boolean;
  assistant_id: string;
  agent_id: string;
  model_id: string;
  history: boolean;
}

export interface AssistantCapabilities {
  enabled: boolean;
  graph_id: string;
  history: boolean;
  long_term_memory: boolean;
  sandbox: boolean;
  write_tools: string[];
  source: boolean;
  databases: string[];
}

export interface AssistantAttachedContext {
  title: string;
  summary: string;
  diagnosticMarkdown: string;
  projectId?: string;
  traceId?: string;
  runId?: string;
  timestamp?: string;
}

export interface EvidenceSource {
  document_id?: string;
  title?: string;
  path?: string | null;
  revision?: string;
  sha256?: string;
  line_start?: number;
  line_end?: number;
  text?: string;
  truncated?: boolean;
  url?: string;
  snippet?: string;
}

export interface EvidenceDetail {
  evidence_id: string;
  operation:
    | "sql_query"
    | "documents"
    | "source"
    | "diagnostics"
    | "logs"
    | "public_search"
    | string;
  observed_at: string;
  scope?: {
    project_id?: string;
    [key: string]: unknown;
  };
  audit_recorded?: boolean;
  data?: {
    rows?: Record<string, unknown>[];
    row_count?: number;
    truncated?: boolean;
    revision?: string;
    limit?: number;
    sources?: EvidenceSource[];
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

export interface AssistantReviewAction {
  name: string;
  args: Record<string, unknown>;
  description?: string;
  allowed_decisions: ("approve" | "reject")[];
}

export interface AssistantPendingReview {
  interrupt_id: string;
  actions: AssistantReviewAction[];
}

export type AssistantTurnStatus =
  | "idle"
  | "running"
  | "awaiting_review"
  | "error";

export interface AssistantChatMessage {
  id: string;
  role: "user" | "assistant" | "tool";
  content: string;
  name?: string;
  tool_call_id?: string;
  evidence_id?: string;
  created_at?: string;
  error?: string;
}

export interface AssistantThreadSummary {
  thread_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

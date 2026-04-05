export type AuthTokenSet = {
  accessToken: string
  refreshToken: string
  tokenType: string
}

export type PaginatedResponse<T> = {
  items: T[]
  total: number
}

export type ManagementUser = {
  id: string
  username: string
  status: string
  is_super_admin: boolean
  email?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export type ManagementUserProject = {
  project_id: string
  project_name: string
  project_description: string
  project_status: string
  role: 'admin' | 'editor' | 'executor'
  joined_at: string
}

export type ManagementProject = {
  id: string
  name: string
  description: string
  status: string
}

export type ManagementProjectMember = {
  user_id: string
  username: string
  role: 'admin' | 'editor' | 'executor'
}

export type ManagementAssistant = {
  id: string
  project_id: string
  name: string
  description: string
  graph_id: string
  langgraph_assistant_id: string
  runtime_base_url: string
  sync_status: string
  last_sync_error?: string | null
  last_synced_at?: string | null
  status: 'active' | 'disabled'
  config: Record<string, unknown>
  context: Record<string, unknown>
  metadata: Record<string, unknown>
  created_by?: string | null
  updated_by?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export type ManagementAuditRow = {
  id: string
  request_id: string
  action: string | null
  target_type: string | null
  target_id: string | null
  method: string
  path: string
  status_code: number
  created_at: string
  user_id: string | null
}

export type ManagementAnnouncement = {
  id: string
  title: string
  summary: string
  body: string
  tone: 'info' | 'warning' | 'success'
  scope_type: string
  scope_project_id: string | null
  status: string
  publish_at: string | null
  expire_at: string | null
  created_at: string | null
  updated_at: string | null
  is_read: boolean
}

export type RuntimeModelItem = {
  id: string
  runtime_id: string
  model_id: string
  display_name: string
  is_default: boolean
  sync_status: string
  last_seen_at: string | null
  last_synced_at: string | null
}

export type RuntimeModelsResponse = {
  count: number
  models: RuntimeModelItem[]
  last_synced_at: string | null
}

export type RuntimeToolItem = {
  id: string
  runtime_id: string
  tool_key: string
  name: string
  source: string
  description: string
  sync_status: string
  last_seen_at: string | null
  last_synced_at: string | null
}

export type RuntimeToolsResponse = {
  count: number
  tools: RuntimeToolItem[]
  last_synced_at: string | null
}

export type RuntimeRefreshResponse = {
  ok: boolean
  count: number
  last_synced_at: string | null
}

export type ManagementGraph = {
  id: string
  runtime_id: string
  graph_id: string
  display_name: string
  description?: string
  source_type: string
  sync_status: string
  last_synced_at: string | null
}

export type ManagementGraphListResponse = PaginatedResponse<ManagementGraph> & {
  last_synced_at?: string | null
}

export type ManagementThread = {
  thread_id: string
  status?: string | null
  created_at?: string | null
  updated_at?: string | null
  metadata?: Record<string, unknown> | null
  values?: Record<string, unknown> | null
}

export type ThreadHistoryEntry = Record<string, unknown>

export type TestcaseOverview = {
  project_id: string
  documents_total: number
  parsed_documents_total: number
  failed_documents_total: number
  test_cases_total: number
  latest_batch_id?: string | null
  latest_activity_at?: string | null
}

export type TestcaseBatchSummary = {
  batch_id: string
  documents_count: number
  test_cases_count: number
  latest_created_at?: string | null
  parse_status_summary: Record<string, number>
}

export type TestcaseDocument = {
  id: string
  project_id: string
  batch_id?: string | null
  filename: string
  content_type: string
  storage_path?: string | null
  source_kind: string
  parse_status: string
  summary_for_model: string
  parsed_text?: string | null
  structured_data?: Record<string, unknown> | null
  provenance: Record<string, unknown>
  confidence?: number | null
  error?: Record<string, unknown> | null
  created_at: string
}

export type TestcaseDocumentRelationCase = {
  id: string
  case_id?: string | null
  title: string
  status: string
  batch_id?: string | null
}

export type TestcaseDocumentRelations = {
  document: TestcaseDocument
  runtime_meta: Record<string, unknown>
  related_cases: TestcaseDocumentRelationCase[]
  related_cases_count: number
}

export type TestcaseCase = {
  id: string
  project_id: string
  batch_id?: string | null
  case_id?: string | null
  title: string
  description: string
  status: string
  module_name?: string | null
  priority?: string | null
  source_document_ids: string[]
  source_documents?: TestcaseDocument[]
  missing_source_document_ids?: string[]
  content_json: Record<string, unknown>
  created_at: string
  updated_at: string
}

export type TestcaseRole = {
  project_id: string
  role: 'admin' | 'editor' | 'executor'
  can_write_testcase: boolean
}

export type ManagementDownload = {
  blob: Blob
  filename: string | null
  contentType: string | null
}

export type ManagementProjectListResponse = PaginatedResponse<ManagementProject>
export type ManagementUserListResponse = PaginatedResponse<ManagementUser>
export type ManagementAssistantListResponse = PaginatedResponse<ManagementAssistant>
export type ManagementAuditListResponse = PaginatedResponse<ManagementAuditRow>

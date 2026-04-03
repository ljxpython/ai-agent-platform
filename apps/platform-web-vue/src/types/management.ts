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

export type ManagementProject = {
  id: string
  name: string
  description: string
  status: string
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

export type ManagementProjectListResponse = PaginatedResponse<ManagementProject>
export type ManagementUserListResponse = PaginatedResponse<ManagementUser>
export type ManagementAssistantListResponse = PaginatedResponse<ManagementAssistant>
export type ManagementAuditListResponse = PaginatedResponse<ManagementAuditRow>

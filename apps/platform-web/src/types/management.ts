export type AuthTokenSet = {
  accessToken: string
  refreshToken: string
  tokenType: string
}

export type PlatformRole = 'platform_super_admin' | 'platform_operator' | 'platform_viewer'
export type ProjectRole = 'project_admin' | 'project_editor' | 'project_executor'
export type LegacyProjectRole = 'admin' | 'editor' | 'executor'
export type PermissionCode =
  | 'platform.user.read'
  | 'platform.user.write'
  | 'platform.user.create'
  | 'platform.user.profile.write'
  | 'platform.user.status.write'
  | 'platform.user.credential.reset'
  | 'platform.user.role.write'
  | 'platform.project.read'
  | 'platform.project.create'
  | 'platform.project.write'
  | 'platform.project.takeover'
  | 'platform.audit.read'
  | 'platform.catalog.refresh'
  | 'platform.announcement.write'
  | 'platform.config.read'
  | 'platform.config.write'
  | 'platform.service_account.read'
  | 'platform.service_account.write'
  | 'platform.service_account.grant.write'
  | 'project.member.read'
  | 'project.member.write'
  | 'project.audit.read'
  | 'project.announcement.read'
  | 'project.announcement.write'
  | 'project.assistant.read'
  | 'project.assistant.write'
  | 'project.runtime.read'
  | 'project.runtime.write'

export type PaginatedResponse<T> = {
  items: T[]
  total: number
}

export type ManagementUser = {
  id: string
  username: string
  status: string
  is_super_admin: boolean
  platform_roles: PlatformRole[]
  must_change_password: boolean
  email?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export type ManagementUserProject = {
  project_id: string
  project_name: string
  project_description: string
  project_status: string
  role: ProjectRole
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
  role: ProjectRole
}

export type ProjectAccess = {
  project_id: string
  roles: ProjectRole[]
  permissions: PermissionCode[]
}

export type ProjectMemberCandidate = {
  user_id: string
  username: string
  email?: string | null
}

export type ManagementAssistant = {
  id: string
  project_id: string
  name: string
  description: string
  graph_id: string
  runtime_base_url: string
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

export type RuntimeGraphPolicyValue = {
  is_enabled: boolean
  display_order?: number | null
  note?: string | null
  updated_at?: string | null
}

export type RuntimeGraphPolicyItem = {
  catalog_id: string
  graph_id: string
  display_name: string
  description: string
  source_type: string
  sync_status: string
  last_synced_at?: string | null
  policy: RuntimeGraphPolicyValue
}

export type RuntimeToolPolicyValue = {
  is_enabled: boolean
  display_order?: number | null
  note?: string | null
  updated_at?: string | null
}

export type RuntimeToolPolicyItem = {
  catalog_id: string
  tool_key: string
  name: string
  source: string
  description: string
  sync_status: string
  last_synced_at?: string | null
  policy: RuntimeToolPolicyValue
}

export type RuntimeModelPolicyValue = {
  is_enabled: boolean
  is_default_for_project: boolean
  temperature_default?: number | null
  note?: string | null
  updated_at?: string | null
}

export type RuntimeModelPolicyItem = {
  catalog_id: string
  model_id: string
  display_name: string
  is_default_runtime: boolean
  sync_status: string
  last_synced_at?: string | null
  policy: RuntimeModelPolicyValue
}

export type RuntimeGraphPolicyListResponse = PaginatedResponse<RuntimeGraphPolicyItem>
export type RuntimeToolPolicyListResponse = PaginatedResponse<RuntimeToolPolicyItem>
export type RuntimeModelPolicyListResponse = PaginatedResponse<RuntimeModelPolicyItem>

export type PlatformConfigSnapshot = {
  service: {
    name: string
    version: string
    env: string
    docs_enabled: boolean
  }
  database: {
    enabled: boolean
    auto_create: boolean
    migration_strategy: string
  }
  auth: {
    required: boolean
    bootstrap_admin_enabled: boolean
  }
  runtime: {
    langgraph_upstream_url: string
  }
  observability: {
    requests: {
      total: number
      failed: number
      failure_rate: number
      avg_duration_ms: number
      max_duration_ms: number
      by_method: Record<string, number>
      by_status_family: Record<string, number>
      top_paths: Array<{
        path: string
        count: number
        failed: number
        failure_rate: number
        avg_duration_ms: number
        max_duration_ms: number
      }>
    }
    trace: {
      request_id_header: string
      trace_id_header: string
    }
  }
  security: {
    oidc: {
      enabled: boolean
      issuer_url: string | null
      client_id: string | null
      mode: string
    }
    service_accounts: {
      enabled: boolean
      api_key_header: string
      default_token_ttl_days: number
      total_accounts: number
      active_accounts: number
      active_tokens: number
      revoked_tokens: number
    }
    sensitive_config: Record<
      string,
      {
        configured: boolean
        masked_value: string | null
      }
    >
  }
  environment: {
    current: string
    supported: string[]
    production_like: boolean
    auth_required: boolean
    docs_enabled: boolean
    bootstrap_admin_enabled: boolean
  }
  data_governance: {
    audit_storage: string
    delete_mode: string
  }
  feature_flags: Record<string, boolean>
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

export type ManagementServiceAccountToken = {
  id: string
  name: string
  token_prefix: string
  status: string
  expires_at: string | null
  last_used_at: string | null
  revoked_at: string | null
  created_at: string | null
}

export type ManagementServiceAccount = {
  id: string
  name: string
  description: string | null
  status: string
  platform_roles: PlatformRole[]
  created_by: string | null
  updated_by: string | null
  last_used_at: string | null
  created_at: string | null
  updated_at: string | null
  tokens: ManagementServiceAccountToken[]
}

export type ManagementServiceAccountPage = PaginatedResponse<ManagementServiceAccount>

export type CreatedServiceAccountToken = {
  token: ManagementServiceAccountToken
  plain_text_token: string
}

export type ServiceAccountProjectGrant = {
  id: string
  service_account_id: string
  project_id: string
  role: ProjectRole
  created_at: string | null
  updated_at: string | null
}

export type RuntimeModelItem = {
  id: string
  display_name: string
  provider: string
  base_url: string
  protocol: string
  model: string
  enabled: boolean
  credential_configured: boolean
}

export type RuntimeModelsResponse = {
  count: number
  models: RuntimeModelItem[]
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

export type RuntimeGraphItem = {
  id: string
  runtime_id: string
  graph_id: string
  display_name: string
  description: string
  source_type: string
  sync_status: string
  last_seen_at: string | null
  last_synced_at: string | null
}

export type RuntimeGraphsResponse = {
  count: number
  graphs: RuntimeGraphItem[]
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
  error?: Record<string, unknown> | string | null
}

export type ThreadHistoryEntry = Record<string, unknown>

export type ManagementDownload = {
  blob: Blob
  filename: string | null
  contentType: string | null
}

export type ManagementProjectListResponse = PaginatedResponse<ManagementProject>
export type ManagementUserListResponse = PaginatedResponse<ManagementUser>
export type ManagementAssistantListResponse = PaginatedResponse<ManagementAssistant>
export type ManagementAuditListResponse = PaginatedResponse<ManagementAuditRow>

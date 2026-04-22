import { platformHttpClient } from '@/services/http/client'
import type { ManagementAuditListResponse, ManagementAuditRow } from '@/types/management'

type AuditEventItem = {
  id: string
  request_id: string
  action?: string | null
  target_type?: string | null
  target_id?: string | null
  actor_user_id?: string | null
  method: string
  path: string
  status_code: number
  created_at: string
}

function normalizeAuditItem(item: AuditEventItem | ManagementAuditRow): ManagementAuditRow {
  return {
    id: item.id,
    request_id: item.request_id,
    action: item.action ?? null,
    target_type: item.target_type ?? null,
    target_id: item.target_id ?? null,
    method: item.method,
    path: item.path,
    status_code: item.status_code,
    created_at: item.created_at,
    user_id: 'user_id' in item ? item.user_id ?? null : item.actor_user_id ?? null
  }
}

export async function listAudit(
  projectId: string | null,
  options?: {
    limit?: number
    offset?: number
    action?: string
    targetType?: string
    targetId?: string
    method?: string
    statusCode?: number | null
  }
): Promise<ManagementAuditListResponse> {
  const response = await platformHttpClient.get('/api/audit', {
    params: {
      project_id: projectId?.trim() || undefined,
      limit: options?.limit ?? 50,
      offset: options?.offset ?? 0,
      action: options?.action?.trim() || undefined,
      target_type: options?.targetType?.trim() || undefined,
      target_id: options?.targetId?.trim() || undefined,
      method: options?.method?.trim().toUpperCase() || undefined,
      status_code:
        typeof options?.statusCode === 'number' && options.statusCode > 0
          ? options.statusCode
          : undefined
    }
  })

  const payload = response.data as ManagementAuditListResponse | { items: AuditEventItem[]; total: number }

  return {
    items: Array.isArray(payload.items) ? payload.items.map((item) => normalizeAuditItem(item)) : [],
    total: payload.total ?? 0
  }
}

import { httpClient } from '@/services/http/client'
import type { ManagementAuditListResponse } from '@/types/management'

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
  const response = await httpClient.get('/_management/audit', {
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

  return response.data as ManagementAuditListResponse
}

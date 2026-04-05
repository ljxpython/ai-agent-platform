import { httpClient } from '@/services/http/client'
import type { ManagementAnnouncement } from '@/types/management'

type AnnouncementsFeedResponse = {
  items: ManagementAnnouncement[]
  total: number
}

type AnnouncementListResponse = {
  items: ManagementAnnouncement[]
  total: number
}

export async function listAnnouncementsFeed(
  projectId?: string
): Promise<AnnouncementsFeedResponse> {
  const response = await httpClient.get('/_management/announcements/feed', {
    params: {
      project_id: projectId?.trim() || undefined
    }
  })

  return response.data as AnnouncementsFeedResponse
}

export async function markAnnouncementRead(announcementId: string): Promise<{
  ok: boolean
  read_at: string
}> {
  const response = await httpClient.post(`/_management/announcements/${announcementId}/read`)
  return response.data as { ok: boolean; read_at: string }
}

export async function markAllAnnouncementsRead(projectId?: string): Promise<{
  ok: boolean
  count: number
}> {
  const response = await httpClient.post('/_management/announcements/read-all', null, {
    params: {
      project_id: projectId?.trim() || undefined
    }
  })
  return response.data as { ok: boolean; count: number }
}

export async function listAnnouncements(options?: {
  limit?: number
  offset?: number
  query?: string
  status?: string
  projectId?: string
  scopeType?: string
}): Promise<AnnouncementListResponse> {
  const response = await httpClient.get('/_management/announcements', {
    params: {
      limit: options?.limit ?? 50,
      offset: options?.offset ?? 0,
      query: options?.query?.trim() || undefined,
      status: options?.status?.trim() || undefined,
      project_id: options?.projectId?.trim() || undefined,
      scope_type: options?.scopeType?.trim() || undefined
    }
  })

  return response.data as AnnouncementListResponse
}

export async function createAnnouncement(payload: {
  title: string
  summary?: string
  body: string
  tone: 'info' | 'warning' | 'success'
  scope_type: 'global' | 'project'
  scope_project_id?: string | null
  status: 'draft' | 'published' | 'archived'
  publish_at?: string | null
  expire_at?: string | null
}): Promise<ManagementAnnouncement> {
  const response = await httpClient.post('/_management/announcements', payload)
  return response.data as ManagementAnnouncement
}

export async function updateAnnouncement(
  announcementId: string,
  payload: {
    title?: string
    summary?: string
    body?: string
    tone?: 'info' | 'warning' | 'success'
    scope_type?: 'global' | 'project'
    scope_project_id?: string | null
    status?: 'draft' | 'published' | 'archived'
    publish_at?: string | null
    expire_at?: string | null
  }
): Promise<ManagementAnnouncement> {
  const response = await httpClient.patch(`/_management/announcements/${announcementId}`, payload)
  return response.data as ManagementAnnouncement
}

export async function deleteAnnouncement(announcementId: string): Promise<{ ok: boolean }> {
  const response = await httpClient.delete(`/_management/announcements/${announcementId}`)
  return response.data as { ok: boolean }
}

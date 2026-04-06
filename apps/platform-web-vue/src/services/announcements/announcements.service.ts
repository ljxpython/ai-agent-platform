import { httpClient, platformV2HttpClient } from '@/services/http/client'
import { resolvePlatformClientScope } from '@/services/platform/control-plane'
import type { ManagementAnnouncement } from '@/types/management'

type AnnouncementsFeedResponse = {
  items: ManagementAnnouncement[]
  total: number
}

type AnnouncementListResponse = {
  items: ManagementAnnouncement[]
  total: number
}

export type AnnouncementServiceMode = 'legacy' | 'runtime'

export type AnnouncementServiceOptions = {
  mode?: AnnouncementServiceMode
}

function useRuntimeAnnouncementsApi(options?: AnnouncementServiceOptions) {
  return options?.mode === 'runtime' && resolvePlatformClientScope('announcements') === 'v2'
}

export async function listAnnouncementsFeed(
  projectId?: string,
  requestOptions?: AnnouncementServiceOptions
): Promise<AnnouncementsFeedResponse> {
  const useRuntimeApi = useRuntimeAnnouncementsApi(requestOptions)
  const client = useRuntimeApi ? platformV2HttpClient : httpClient
  const endpoint = useRuntimeApi ? '/api/announcements/feed' : '/_management/announcements/feed'
  const response = await client.get(endpoint, {
    params: {
      project_id: projectId?.trim() || undefined
    }
  })

  return response.data as AnnouncementsFeedResponse
}

export async function markAnnouncementRead(
  announcementId: string,
  requestOptions?: AnnouncementServiceOptions
): Promise<{
  ok: boolean
  read_at: string
}> {
  const useRuntimeApi = useRuntimeAnnouncementsApi(requestOptions)
  const client = useRuntimeApi ? platformV2HttpClient : httpClient
  const endpoint = useRuntimeApi
    ? `/api/announcements/${announcementId}/read`
    : `/_management/announcements/${announcementId}/read`
  const response = await client.post(endpoint)
  return response.data as { ok: boolean; read_at: string }
}

export async function markAllAnnouncementsRead(
  projectId?: string,
  requestOptions?: AnnouncementServiceOptions
): Promise<{
  ok: boolean
  count: number
}> {
  const useRuntimeApi = useRuntimeAnnouncementsApi(requestOptions)
  const client = useRuntimeApi ? platformV2HttpClient : httpClient
  const endpoint = useRuntimeApi ? '/api/announcements/read-all' : '/_management/announcements/read-all'
  const response = await client.post(endpoint, null, {
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
}, requestOptions?: AnnouncementServiceOptions): Promise<AnnouncementListResponse> {
  const useRuntimeApi = useRuntimeAnnouncementsApi(requestOptions)
  const client = useRuntimeApi ? platformV2HttpClient : httpClient
  const endpoint = useRuntimeApi ? '/api/announcements' : '/_management/announcements'
  const response = await client.get(endpoint, {
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
}, requestOptions?: AnnouncementServiceOptions): Promise<ManagementAnnouncement> {
  const useRuntimeApi = useRuntimeAnnouncementsApi(requestOptions)
  const client = useRuntimeApi ? platformV2HttpClient : httpClient
  const endpoint = useRuntimeApi ? '/api/announcements' : '/_management/announcements'
  const response = await client.post(endpoint, payload)
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
  },
  requestOptions?: AnnouncementServiceOptions
): Promise<ManagementAnnouncement> {
  const useRuntimeApi = useRuntimeAnnouncementsApi(requestOptions)
  const client = useRuntimeApi ? platformV2HttpClient : httpClient
  const endpoint = useRuntimeApi
    ? `/api/announcements/${announcementId}`
    : `/_management/announcements/${announcementId}`
  const response = await client.patch(endpoint, payload)
  return response.data as ManagementAnnouncement
}

export async function deleteAnnouncement(
  announcementId: string,
  requestOptions?: AnnouncementServiceOptions
): Promise<{ ok: boolean }> {
  const useRuntimeApi = useRuntimeAnnouncementsApi(requestOptions)
  const client = useRuntimeApi ? platformV2HttpClient : httpClient
  const endpoint = useRuntimeApi
    ? `/api/announcements/${announcementId}`
    : `/_management/announcements/${announcementId}`
  const response = await client.delete(endpoint)
  return response.data as { ok: boolean }
}

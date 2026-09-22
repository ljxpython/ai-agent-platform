import { platformHttpClient } from '@/services/http/client'
import type { ThreadAction } from './session.service'

export type SharedThreadAction = Extract<ThreadAction, 'read' | 'comment' | 'edit' | 'share' | 'delete'>
export type TakeoverCategory = 'security_incident' | 'compliance' | 'user_support' | 'handover'

export async function shareThread(projectId: string, threadId: string, userId: string | null, actions: SharedThreadAction[]) {
  return (await platformHttpClient.put(`/api/langgraph/threads/${encodeURIComponent(threadId)}/shares`,
    { user_id: userId, actions }, { headers: { 'x-project-id': projectId } })).data
}

export async function takeOverThread(projectId: string, threadId: string, payload: {
  category: TakeoverCategory; reason: string; reference: string; duration_minutes: number
}): Promise<{ expires_at: number }> {
  return (await platformHttpClient.post(`/api/langgraph/threads/${encodeURIComponent(threadId)}/takeover`,
    payload, { headers: { 'x-project-id': projectId } })).data
}

export async function endThreadTakeover(projectId: string, threadId: string) {
  return (await platformHttpClient.delete(`/api/langgraph/threads/${encodeURIComponent(threadId)}/takeover`,
    { headers: { 'x-project-id': projectId } })).data
}

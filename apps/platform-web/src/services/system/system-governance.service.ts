import { platformHttpClient } from '@/services/http/client'
import type { PlatformConfigSnapshot } from '@/types/management'

export type SystemProbeStatus = {
  status: string
  service?: string
  version?: string
  env?: string
  request_id?: string
  trace_id?: string
  database_ready?: string | boolean
  healthy_workers?: string | number
  stale_workers?: number
}

export async function getSystemHealth(): Promise<SystemProbeStatus> {
  const response = await platformHttpClient.get('/_system/health')
  return response.data as SystemProbeStatus
}

export async function getSystemLiveProbe(): Promise<SystemProbeStatus> {
  const response = await platformHttpClient.get('/_system/probes/live')
  return response.data as SystemProbeStatus
}

export async function getSystemReadyProbe(): Promise<SystemProbeStatus> {
  const response = await platformHttpClient.get('/_system/probes/ready')
  return response.data as SystemProbeStatus
}

export async function getSystemMetrics(): Promise<PlatformConfigSnapshot['observability']> {
  const response = await platformHttpClient.get('/_system/metrics')
  return response.data as PlatformConfigSnapshot['observability']
}

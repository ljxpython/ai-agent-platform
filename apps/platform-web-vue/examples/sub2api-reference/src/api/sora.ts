/**
 * Sora 客户端 API
 * 封装所有 Sora 生成、作品库、配额等接口调用
 */

import { apiClient } from './client'

// ==================== 类型定义 ====================

export interface SoraGeneration {
  id: number
  user_id: number
  model: string
  prompt: string
  media_type: string
  status: string // pending | generating | completed | failed | cancelled
  storage_type: string // upstream | s3 | local
  media_url: string
  media_urls: string[]
  s3_object_keys: string[]
  file_size_bytes: number
  error_message: string
  created_at: string
  completed_at?: string
}

export interface GenerateRequest {
  model: string
  prompt: string
  video_count?: number
  media_type?: string
  image_input?: string
  api_key_id?: number
}

export interface GenerateResponse {
  generation_id: number
  status: string
}

export interface GenerationListResponse {
  data: SoraGeneration[]
  total: number
  page: number
}

export interface QuotaInfo {
  quota_bytes: number
  used_bytes: number
  available_bytes: number
  quota_source: string // user | group | system | unlimited
  source?: string // 兼容旧字段
}

export interface StorageStatus {
  s3_enabled: boolean
  s3_healthy: boolean
  local_enabled: boolean
}

/** 单个扁平模型（旧接口，保留兼容） */
export interface SoraModel {
  id: string
  name: string
  type: string // video | image
  orientation?: string
  duration?: number
}

/** 模型家族（新接口 — 后端从 soraModelConfigs 自动聚合） */
export interface SoraModelFamily {
  id: string          // 家族 ID，如 "sora2"
  name: string        // 显示名，如 "Sora 2"
  type: string        // "video" | "image"
  orientations: string[]  // ["landscape", "portrait"] 或 ["landscape", "portrait", "square"]
  durations?: number[]    // [10, 15, 25]（仅视频模型）
}

type LooseRecord = Record<string, unknown>

function asRecord(value: unknown): LooseRecord | null {
  return value !== null && typeof value === 'object' ? value as LooseRecord : null
}

function asArray<T = unknown>(value: unknown): T[] {
  return Array.isArray(value) ? value as T[] : []
}

function asPositiveInt(value: unknown): number | null {
  const n = Number(value)
  if (!Number.isFinite(n) || n <= 0) return null
  return Math.round(n)
}

function dedupeStrings(values: string[]): string[] {
  return Array.from(new Set(values))
}

function extractOrientationFromModelID(modelID: string): string | null {
  const m = modelID.match(/-(landscape|portrait|square)(?:-\d+s)?$/i)
  return m ? m[1].toLowerCase() : null
}

function extractDurationFromModelID(modelID: string): number | null {
  const m = modelID.match(/-(\d+)s$/i)
  return m ? asPositiveInt(m[1]) : null
}

function normalizeLegacyFamilies(candidates: unknown[]): SoraModelFamily[] {
  const familyMap = new Map<string, SoraModelFamily>()

  for (const item of candidates) {
    const model = asRecord(item)
    if (!model || typeof model.id !== 'string' || model.id.trim() === '') continue

    const rawID = model.id.trim()
    const type = model.type === 'image' ? 'image' : 'video'
    const name = typeof model.name === 'string' && model.name.trim() ? model.name.trim() : rawID
    const baseID = rawID.replace(/-(landscape|portrait|square)(?:-\d+s)?$/i, '')
    const orientation =
      typeof model.orientation === 'string' && model.orientation
        ? model.orientation.toLowerCase()
        : extractOrientationFromModelID(rawID)
    const duration = asPositiveInt(model.duration) ?? extractDurationFromModelID(rawID)
    const familyKey = baseID || rawID

    const family = familyMap.get(familyKey) ?? {
      id: familyKey,
      name,
      type,
      orientations: [],
      durations: []
    }

    if (orientation) {
      family.orientations.push(orientation)
    }
    if (type === 'video' && duration) {
      family.durations = family.durations || []
      family.durations.push(duration)
    }

    familyMap.set(familyKey, family)
  }

  return Array.from(familyMap.values())
    .map((family) => ({
      ...family,
      orientations:
        family.orientations.length > 0
          ? dedupeStrings(family.orientations)
          : (family.type === 'image' ? ['square'] : ['landscape']),
      durations:
        family.type === 'video'
          ? Array.from(new Set((family.durations || []).filter((d): d is number => Number.isFinite(d)))).sort((a, b) => a - b)
          : []
    }))
    .filter((family) => family.id !== '')
}

function normalizeModelFamilyRecord(item: unknown): SoraModelFamily | null {
  const model = asRecord(item)
  if (!model || typeof model.id !== 'string' || model.id.trim() === '') return null
  // 仅把明确的“家族结构”识别为 family；老结构（单模型）走 legacy 聚合逻辑。
  if (!Array.isArray(model.orientations) && !Array.isArray(model.durations)) return null

  const orientations = asArray<string>(model.orientations).filter((o): o is string => typeof o === 'string' && o.length > 0)
  const durations = asArray<unknown>(model.durations)
    .map(asPositiveInt)
    .filter((d): d is number => d !== null)

  return {
    id: model.id.trim(),
    name: typeof model.name === 'string' && model.name.trim() ? model.name.trim() : model.id.trim(),
    type: model.type === 'image' ? 'image' : 'video',
    orientations: dedupeStrings(orientations),
    durations: Array.from(new Set(durations)).sort((a, b) => a - b)
  }
}

function extractCandidateArray(payload: unknown): unknown[] {
  if (Array.isArray(payload)) return payload
  const record = asRecord(payload)
  if (!record) return []

  const keys: Array<keyof LooseRecord> = ['data', 'items', 'models', 'families']
  for (const key of keys) {
    if (Array.isArray(record[key])) {
      return record[key] as unknown[]
    }
  }
  return []
}

export function normalizeModelFamiliesResponse(payload: unknown): SoraModelFamily[] {
  const candidates = extractCandidateArray(payload)
  if (candidates.length === 0) return []

  const normalized = candidates
    .map(normalizeModelFamilyRecord)
    .filter((item): item is SoraModelFamily => item !== null)

  if (normalized.length > 0) return normalized
  return normalizeLegacyFamilies(candidates)
}

export function normalizeGenerationListResponse(payload: unknown): GenerationListResponse {
  const record = asRecord(payload)
  if (!record) {
    return { data: [], total: 0, page: 1 }
  }

  const data = Array.isArray(record.data)
    ? (record.data as SoraGeneration[])
    : Array.isArray(record.items)
      ? (record.items as SoraGeneration[])
      : []

  const total = Number(record.total)
  const page = Number(record.page)

  return {
    data,
    total: Number.isFinite(total) ? total : data.length,
    page: Number.isFinite(page) && page > 0 ? page : 1
  }
}

// ==================== API 方法 ====================

/** 异步生成 — 创建 pending 记录后立即返回 */
export async function generate(req: GenerateRequest): Promise<GenerateResponse> {
  const { data } = await apiClient.post<GenerateResponse>('/sora/generate', req)
  return data
}

/** 查询生成记录列表 */
export async function listGenerations(params?: {
  page?: number
  page_size?: number
  status?: string
  storage_type?: string
  media_type?: string
}): Promise<GenerationListResponse> {
  const { data } = await apiClient.get<unknown>('/sora/generations', { params })
  return normalizeGenerationListResponse(data)
}

/** 查询生成记录详情 */
export async function getGeneration(id: number): Promise<SoraGeneration> {
  const { data } = await apiClient.get<SoraGeneration>(`/sora/generations/${id}`)
  return data
}

/** 删除生成记录 */
export async function deleteGeneration(id: number): Promise<{ message: string }> {
  const { data } = await apiClient.delete<{ message: string }>(`/sora/generations/${id}`)
  return data
}

/** 取消生成任务 */
export async function cancelGeneration(id: number): Promise<{ message: string }> {
  const { data } = await apiClient.post<{ message: string }>(`/sora/generations/${id}/cancel`)
  return data
}

/** 手动保存到 S3 */
export async function saveToStorage(
  id: number
): Promise<{ message: string; object_key: string; object_keys?: string[] }> {
  const { data } = await apiClient.post<{ message: string; object_key: string; object_keys?: string[] }>(
    `/sora/generations/${id}/save`
  )
  return data
}

/** 查询配额信息 */
export async function getQuota(): Promise<QuotaInfo> {
  const { data } = await apiClient.get<QuotaInfo>('/sora/quota')
  return data
}

/** 获取可用模型家族列表 */
export async function getModels(): Promise<SoraModelFamily[]> {
  const { data } = await apiClient.get<unknown>('/sora/models')
  return normalizeModelFamiliesResponse(data)
}

/** 获取存储状态 */
export async function getStorageStatus(): Promise<StorageStatus> {
  const { data } = await apiClient.get<StorageStatus>('/sora/storage-status')
  return data
}

const soraAPI = {
  generate,
  listGenerations,
  getGeneration,
  deleteGeneration,
  cancelGeneration,
  saveToStorage,
  getQuota,
  getModels,
  getStorageStatus
}

export default soraAPI

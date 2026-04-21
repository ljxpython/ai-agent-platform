import type { TestcaseDocument } from '@/types/management'

function asRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {}
  }
  return value as Record<string, unknown>
}

function coerceText(value: unknown): string {
  if (value == null) {
    return ''
  }
  return String(value).trim()
}

function contentTypeFromFilename(filename: unknown): string {
  const normalized = coerceText(filename).toLowerCase()
  if (!normalized.includes('.')) {
    return ''
  }

  const extension = normalized.slice(normalized.lastIndexOf('.') + 1)
  const byExtension: Record<string, string> = {
    pdf: 'application/pdf',
    jpg: 'image/jpeg',
    jpeg: 'image/jpeg',
    png: 'image/png',
    gif: 'image/gif',
    webp: 'image/webp',
    bmp: 'image/bmp',
    svg: 'image/svg+xml',
    txt: 'text/plain',
    md: 'text/markdown',
    markdown: 'text/markdown',
    json: 'application/json',
    xml: 'application/xml',
    html: 'text/html',
    htm: 'text/html',
    csv: 'text/csv'
  }
  return byExtension[extension] || ''
}

export function resolveDocumentStoragePath(document: TestcaseDocument | null): string {
  if (!document) {
    return ''
  }
  if (document.storage_path) {
    return document.storage_path
  }
  const provenance = asRecord(document.provenance)
  const asset = asRecord(provenance.asset)
  return coerceText(asset.storage_path)
}

export function resolveDocumentContentType(document: TestcaseDocument | null): string {
  if (!document) {
    return ''
  }

  const direct = coerceText(document.content_type)
  if (direct) {
    return direct
  }

  const provenance = asRecord(document.provenance)
  const asset = asRecord(provenance.asset)
  for (const candidate of [
    asset.content_type,
    asset.mime_type,
    provenance.content_type,
    provenance.mime_type
  ]) {
    const normalized = coerceText(candidate)
    if (normalized) {
      return normalized
    }
  }

  return contentTypeFromFilename(document.filename)
}

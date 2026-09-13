import { isValidImageRef, type RuntimeImageRef } from '@/services/threads/images.service'
import { isValidFileRef, type RuntimeFileRef } from '@/services/threads/files.service'

type ChatTextBlock = {
  type: 'text'
  text: string
}

export type ChatRuntimeImageTextBlock = {
  type: 'text'
  text: string
  extras: {
    runtime_image: RuntimeImageRef
  }
}

export type ChatRuntimeFileTextBlock = {
  type: 'text'
  text: string
  extras: {
    runtime_file: RuntimeFileRef
  }
}

export type ChatImageAttachmentBlock = {
  type: 'image'
  mimeType: string
  data: string
  file?: File
  uploadStatus?: 'pending' | 'hashing' | 'uploading' | 'uploaded' | 'failed'
  runtimeImageRef?: RuntimeImageRef
  errorMessage?: string
  metadata?: Record<string, unknown>
}

export type ChatFileAttachmentBlock = {
  type: 'file'
  mimeType: string
  data?: string
  file?: File
  uploadStatus?: 'pending' | 'hashing' | 'uploading' | 'uploaded' | 'failed'
  runtimeFileRef?: RuntimeFileRef
  errorMessage?: string
  metadata?: Record<string, unknown>
}

export type ChatAttachmentBlock = ChatImageAttachmentBlock | ChatFileAttachmentBlock

export function isRuntimeImageTextBlock(value: unknown): value is ChatRuntimeImageTextBlock {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return false
  }
  const obj = value as Record<string, unknown>
  if (obj.type !== 'text' || typeof obj.text !== 'string') {
    return false
  }
  const extras = obj.extras
  if (!extras || typeof extras !== 'object' || Array.isArray(extras)) {
    return false
  }
  return isValidImageRef((extras as Record<string, unknown>).runtime_image)
}

export function createRuntimeImageTextBlock(filename: string, ref: RuntimeImageRef): ChatRuntimeImageTextBlock {
  return {
    type: 'text',
    text: `[图片附件] ${filename}\n${ref.path}`,
    extras: {
      runtime_image: ref,
    },
  }
}

export function isRuntimeFileTextBlock(value: unknown): value is ChatRuntimeFileTextBlock {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return false
  }
  const obj = value as Record<string, unknown>
  if (obj.type !== 'text' || typeof obj.text !== 'string') {
    return false
  }
  const extras = obj.extras
  if (!extras || typeof extras !== 'object' || Array.isArray(extras)) {
    return false
  }
  return isValidFileRef((extras as Record<string, unknown>).runtime_file)
}

export function createRuntimeFileTextBlock(filename: string, ref: RuntimeFileRef): ChatRuntimeFileTextBlock {
  return {
    type: 'text',
    text: `[文档附件] ${filename}\n${ref.path}`,
    extras: {
      runtime_file: ref,
    },
  }
}

export const SUPPORTED_CHAT_ATTACHMENT_MIME_TYPES = [
  'image/jpeg',
  'image/png',
  'image/gif',
  'image/webp',
  'application/pdf',
  'text/plain',
  'text/markdown',
  'application/json',
  'text/csv',
] as const

export const SUPPORTED_FILE_EXTENSIONS = [
  '.pdf',
  '.txt',
  '.md',
  '.markdown',
  '.json',
  '.csv',
] as const

export const CHAT_ATTACHMENT_ACCEPT = [
  ...SUPPORTED_CHAT_ATTACHMENT_MIME_TYPES,
  ...SUPPORTED_FILE_EXTENSIONS,
].join(',')

export function isDocumentFile(file: File): boolean {
  const name = file.name.toLowerCase()
  if (SUPPORTED_FILE_EXTENSIONS.some((ext) => name.endsWith(ext))) {
    return true
  }
  const mime = (file.type || '').split(';')[0].trim().toLowerCase()
  return [
    'application/pdf',
    'text/plain',
    'text/markdown',
    'application/json',
    'text/csv',
  ].includes(mime)
}

export function resolveDocumentMime(file: File): string {
  const name = file.name.toLowerCase()
  if (name.endsWith('.pdf')) return 'application/pdf'
  if (name.endsWith('.txt')) return 'text/plain'
  if (name.endsWith('.md') || name.endsWith('.markdown')) return 'text/markdown'
  if (name.endsWith('.json')) return 'application/json'
  if (name.endsWith('.csv')) return 'text/csv'
  return file.type || 'application/octet-stream'
}

function asRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {}
  }
  return value as Record<string, unknown>
}

function stringifyUnknown(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

export function isChatTextBlock(value: unknown): value is ChatTextBlock {
  const block = asRecord(value)
  return block.type === 'text' && typeof block.text === 'string'
}

export function isChatAttachmentBlock(value: unknown): value is ChatAttachmentBlock {
  const block = asRecord(value)
  if (block.type === 'image') {
    return typeof block.mimeType === 'string' && block.mimeType.startsWith('image/')
  }
  if (block.type === 'file') {
    return typeof block.mimeType === 'string'
  }
  return false
}

export async function fileToBase64(file: File): Promise<string> {
  return await new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onloadend = () => {
      const result = typeof reader.result === 'string' ? reader.result : ''
      resolve(result.includes(',') ? result.split(',')[1] || '' : result)
    }
    reader.onerror = () => reject(reader.error || new Error('文件读取失败'))
    reader.readAsDataURL(file)
  })
}

export async function fileToChatAttachmentBlock(file: File): Promise<ChatAttachmentBlock> {
  const mime = (file.type || '').split(';')[0].trim().toLowerCase()
  const isDoc = isDocumentFile(file)
  const isImg = file.type.startsWith('image/') || ['image/jpeg', 'image/png', 'image/gif', 'image/webp'].includes(mime)

  if (!isDoc && !isImg) {
    throw new Error(`暂不支持 ${file.name || '此格式'} 文件`)
  }

  if (isImg) {
    const data = await fileToBase64(file)
    return {
      type: 'image',
      mimeType: file.type || 'image/png',
      data,
      file,
      uploadStatus: 'pending',
      metadata: {
        name: file.name,
      },
    }
  }

  // 文档类型不转 Base64，杜绝内存膨胀
  return {
    type: 'file',
    mimeType: resolveDocumentMime(file),
    data: '',
    file,
    uploadStatus: 'pending',
    metadata: {
      filename: file.name,
      name: file.name,
      size: file.size,
    },
  }
}

export function getChatAttachmentName(block: ChatAttachmentBlock): string {
  const metadata = asRecord(block.metadata)
  const filename = typeof metadata.filename === 'string' ? metadata.filename.trim() : ''
  if (filename) {
    return filename
  }

  const name = typeof metadata.name === 'string' ? metadata.name.trim() : ''
  if (name) {
    return name
  }

  if (block.file?.name) {
    return block.file.name
  }

  return block.type === 'image' ? 'image' : 'document'
}

export function getChatAttachmentDataUrl(block: ChatAttachmentBlock): string {
  return block.data ? `data:${block.mimeType};base64,${block.data}` : ''
}

export function getMessageText(content: unknown): string {
  if (typeof content === 'string') {
    return content
  }

  if (Array.isArray(content)) {
    return content
      .map((item) => {
        if (typeof item === 'string') {
          return item
        }
        if (isChatTextBlock(item)) {
          return item.text
        }
        return ''
      })
      .filter((item) => item.trim().length > 0)
      .join('\n')
  }

  if (content && typeof content === 'object') {
    return stringifyUnknown(content)
  }

  return ''
}

export function getMessageAttachments(content: unknown): ChatAttachmentBlock[] {
  if (!Array.isArray(content)) {
    return []
  }

  return content.filter(isChatAttachmentBlock)
}

export function summarizeMessageContent(content: unknown): string {
  const text = getMessageText(content).trim()
  if (text) {
    return text
  }

  const attachments = getMessageAttachments(content)
  if (attachments.length > 0) {
    return attachments
      .map((block) => {
        const name = getChatAttachmentName(block)
        return block.type === 'image' ? `[图片] ${name}` : `[文档] ${name}`
      })
      .join(' · ')
  }

  if (content && typeof content === 'object') {
    return stringifyUnknown(content)
  }

  return ''
}

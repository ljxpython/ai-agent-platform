type ChatTextBlock = {
  type: 'text'
  text: string
}

export type ChatImageAttachmentBlock = {
  type: 'image'
  mimeType: string
  data: string
  metadata?: Record<string, unknown>
}

export type ChatFileAttachmentBlock = {
  type: 'file'
  mimeType: string
  data: string
  metadata?: Record<string, unknown>
}

export type ChatAttachmentBlock = ChatImageAttachmentBlock | ChatFileAttachmentBlock

export const SUPPORTED_CHAT_ATTACHMENT_MIME_TYPES = [
  'image/jpeg',
  'image/png',
  'image/gif',
  'image/webp',
  'application/pdf'
] as const

export const CHAT_ATTACHMENT_ACCEPT = SUPPORTED_CHAT_ATTACHMENT_MIME_TYPES.join(',')

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
    return typeof block.mimeType === 'string' && block.mimeType.startsWith('image/') && typeof block.data === 'string'
  }
  if (block.type === 'file') {
    return typeof block.mimeType === 'string' && block.mimeType === 'application/pdf' && typeof block.data === 'string'
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
  if (!SUPPORTED_CHAT_ATTACHMENT_MIME_TYPES.includes(file.type as (typeof SUPPORTED_CHAT_ATTACHMENT_MIME_TYPES)[number])) {
    throw new Error(`暂不支持 ${file.type || 'unknown'} 文件`)
  }

  const data = await fileToBase64(file)

  if (file.type.startsWith('image/')) {
    return {
      type: 'image',
      mimeType: file.type,
      data,
      metadata: {
        name: file.name
      }
    }
  }

  return {
    type: 'file',
    mimeType: 'application/pdf',
    data,
    metadata: {
      filename: file.name
    }
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

  return block.type === 'image' ? 'image' : 'document.pdf'
}

export function getChatAttachmentDataUrl(block: ChatAttachmentBlock): string {
  return `data:${block.mimeType};base64,${block.data}`
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
        return block.type === 'image' ? `[图片] ${name}` : `[PDF] ${name}`
      })
      .join(' · ')
  }

  if (content && typeof content === 'object') {
    return stringifyUnknown(content)
  }

  return ''
}

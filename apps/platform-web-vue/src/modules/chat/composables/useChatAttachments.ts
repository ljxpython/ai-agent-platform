import { ref } from 'vue'
import { useUiStore } from '@/stores/ui'
import {
  fileToChatAttachmentBlock,
  getChatAttachmentName,
  type ChatAttachmentBlock,
  SUPPORTED_CHAT_ATTACHMENT_MIME_TYPES
} from '@/utils/chat-content'

function isDuplicateFile(file: File, attachments: ChatAttachmentBlock[]) {
  return attachments.some((attachment) => {
    if (attachment.type === 'image' && !file.type.startsWith('image/')) {
      return false
    }
    if (attachment.type === 'file' && file.type !== 'application/pdf') {
      return false
    }
    return attachment.mimeType === file.type && getChatAttachmentName(attachment) === file.name
  })
}

export function useChatAttachments() {
  const uiStore = useUiStore()
  const attachments = ref<ChatAttachmentBlock[]>([])

  async function appendFiles(inputFiles: File[] | FileList | null | undefined) {
    const files = Array.isArray(inputFiles) ? inputFiles : Array.from(inputFiles || [])
    if (files.length === 0) {
      return 0
    }

    const validFiles = files.filter((file) =>
      SUPPORTED_CHAT_ATTACHMENT_MIME_TYPES.includes(file.type as (typeof SUPPORTED_CHAT_ATTACHMENT_MIME_TYPES)[number])
    )
    const invalidFiles = files.filter(
      (file) =>
        !SUPPORTED_CHAT_ATTACHMENT_MIME_TYPES.includes(file.type as (typeof SUPPORTED_CHAT_ATTACHMENT_MIME_TYPES)[number])
    )
    const duplicateFiles = validFiles.filter((file) => isDuplicateFile(file, attachments.value))
    const uniqueFiles = validFiles.filter((file) => !isDuplicateFile(file, attachments.value))

    if (invalidFiles.length > 0) {
      uiStore.pushToast({
        type: 'warning',
        title: '存在不支持的附件',
        message: '当前聊天只支持 JPEG、PNG、GIF、WEBP 图片以及 PDF 文档。'
      })
    }

    if (duplicateFiles.length > 0) {
      uiStore.pushToast({
        type: 'warning',
        title: '发现重复附件',
        message: `同一条消息里不能重复上传：${duplicateFiles.map((item) => item.name).join('、')}`
      })
    }

    if (uniqueFiles.length === 0) {
      return 0
    }

    const newAttachments = await Promise.all(uniqueFiles.map(fileToChatAttachmentBlock))
    attachments.value = [...attachments.value, ...newAttachments]
    return newAttachments.length
  }

  async function handleInputChange(event: Event) {
    const input = event.target as HTMLInputElement | null
    if (!input?.files) {
      return
    }
    await appendFiles(input.files)
    input.value = ''
  }

  async function handlePaste(event: ClipboardEvent) {
    const items = Array.from(event.clipboardData?.items || [])
    const files = items
      .filter((item) => item.kind === 'file')
      .map((item) => item.getAsFile())
      .filter((item): item is File => item instanceof File)

    if (files.length === 0) {
      return false
    }

    event.preventDefault()
    await appendFiles(files)
    return true
  }

  function removeAttachment(index: number) {
    attachments.value = attachments.value.filter((_, currentIndex) => currentIndex !== index)
  }

  function resetAttachments() {
    attachments.value = []
  }

  return {
    attachments,
    appendFiles,
    handleInputChange,
    handlePaste,
    removeAttachment,
    resetAttachments
  }
}

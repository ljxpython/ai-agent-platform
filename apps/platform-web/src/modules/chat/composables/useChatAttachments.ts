import { onScopeDispose, ref, type Ref } from "vue";
import { useUiStore } from "@/stores/ui";
import {
  fileToChatAttachmentBlock,
  getChatAttachmentName,
  type ChatAttachmentBlock,
  SUPPORTED_CHAT_ATTACHMENT_MIME_TYPES,
} from "@/utils/chat-content";

function isDuplicateFile(file: File, attachments: ChatAttachmentBlock[]) {
  return attachments.some((attachment) => {
    if (attachment.type === "image" && !file.type.startsWith("image/")) {
      return false;
    }
    if (attachment.type === "file" && file.type !== "application/pdf") {
      return false;
    }
    return (
      attachment.mimeType === file.type &&
      getChatAttachmentName(attachment) === file.name
    );
  });
}

export function useChatAttachments(
  attachments: Ref<ChatAttachmentBlock[]> = ref([]),
) {
  const uiStore = useUiStore();
  const loading = ref(false);
  let epoch = 0;
  let disposed = false;
  onScopeDispose(() => {
    disposed = true;
    epoch += 1;
  });

  async function appendFiles(inputFiles: File[] | FileList | null | undefined) {
    const files = Array.isArray(inputFiles)
      ? inputFiles
      : Array.from(inputFiles || []);
    if (files.length === 0) {
      return 0;
    }
    if (loading.value || disposed) return 0;
    if (
      files.some((file) => file.size > 5 * 1024 * 1024) ||
      files.length + attachments.value.length > 8 ||
      files.reduce((sum, file) => sum + file.size, 0) +
        attachments.value.reduce(
          (sum, file) => sum + file.data.length * 0.75,
          0,
        ) >
        20 * 1024 * 1024
    ) {
      uiStore.pushToast({
        type: "warning",
        title: "附件超过限制",
        message: "每个文件最多 5 MB，每条消息最多 8 个附件、合计 20 MB。",
      });
      return 0;
    }

    const validFiles = files.filter((file) =>
      SUPPORTED_CHAT_ATTACHMENT_MIME_TYPES.includes(
        file.type as (typeof SUPPORTED_CHAT_ATTACHMENT_MIME_TYPES)[number],
      ),
    );
    const invalidFiles = files.filter(
      (file) =>
        !SUPPORTED_CHAT_ATTACHMENT_MIME_TYPES.includes(
          file.type as (typeof SUPPORTED_CHAT_ATTACHMENT_MIME_TYPES)[number],
        ),
    );
    const seen = new Set<string>();
    const duplicateFiles: File[] = [];
    const uniqueFiles = validFiles.filter((file) => {
      const key = JSON.stringify([file.name, file.type]);
      if (seen.has(key) || isDuplicateFile(file, attachments.value)) {
        duplicateFiles.push(file);
        return false;
      }
      seen.add(key);
      return true;
    });

    if (invalidFiles.length > 0) {
      uiStore.pushToast({
        type: "warning",
        title: "存在不支持的附件",
        message: "当前聊天只支持 JPEG、PNG、GIF、WEBP 图片以及 PDF 文档。",
      });
    }

    if (duplicateFiles.length > 0) {
      uiStore.pushToast({
        type: "warning",
        title: "发现重复附件",
        message: `同一条消息里不能重复上传：${duplicateFiles.map((item) => item.name).join("、")}`,
      });
    }

    if (uniqueFiles.length === 0) {
      return 0;
    }

    const pendingEpoch = epoch;
    loading.value = true;
    try {
      const newAttachments = await Promise.all(
        uniqueFiles.map(fileToChatAttachmentBlock),
      );
      if (disposed || pendingEpoch !== epoch) return 0;
      attachments.value = [...attachments.value, ...newAttachments];
      return newAttachments.length;
    } catch {
      if (!disposed)
        uiStore.pushToast({
          type: "error",
          title: "读取附件失败",
          message: "请重新选择文件。",
        });
      return 0;
    } finally {
      if (!disposed) loading.value = false;
    }
  }

  async function handleInputChange(event: Event) {
    const input = event.target as HTMLInputElement | null;
    if (!input?.files) {
      return;
    }
    await appendFiles(input.files);
    input.value = "";
  }

  async function handlePaste(event: ClipboardEvent) {
    const items = Array.from(event.clipboardData?.items || []);
    const files = items
      .filter((item) => item.kind === "file")
      .map((item) => item.getAsFile())
      .filter((item): item is File => item instanceof File);

    if (files.length === 0) {
      return false;
    }

    event.preventDefault();
    await appendFiles(files);
    return true;
  }

  function removeAttachment(index: number) {
    attachments.value = attachments.value.filter(
      (_, currentIndex) => currentIndex !== index,
    );
  }

  function resetAttachments() {
    epoch += 1;
    attachments.value = [];
  }

  return {
    attachments,
    loading,
    appendFiles,
    handleInputChange,
    handlePaste,
    removeAttachment,
    resetAttachments,
  };
}

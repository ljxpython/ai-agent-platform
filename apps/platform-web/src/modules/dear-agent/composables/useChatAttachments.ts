import { onScopeDispose, ref, type Ref } from "vue";
import { useUiStore } from "@/stores/ui";
import {
  fileToChatAttachmentBlock,
  getChatAttachmentName,
  isDocumentFile,
  type ChatAttachmentBlock,
  SUPPORTED_CHAT_ATTACHMENT_MIME_TYPES,
  SUPPORTED_FILE_EXTENSIONS,
} from "@/utils/chat-content";

function isDuplicateFile(file: File, attachments: ChatAttachmentBlock[]) {
  return attachments.some((attachment) => {
    return getChatAttachmentName(attachment) === file.name;
  });
}

export function useChatAttachments(
  attachments: Ref<ChatAttachmentBlock[]> = ref([]),
  options?: {
    graphId?: Ref<string> | string;
  },
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

    const currentGraphId =
      typeof options?.graphId === "object"
        ? options.graphId.value
        : options?.graphId;
    if (currentGraphId === "showcase_demo") {
      const gifFiles = files.filter(
        (f) => f.type === "image/gif" || f.name.toLowerCase().endsWith(".gif"),
      );
      if (gifFiles.length > 0) {
        uiStore.pushToast({
          type: "warning",
          title: "不支持 GIF 图片",
          message: "不支持动态 GIF，请转换为 PNG/JPEG/WEBP 后上传。",
        });
        return 0;
      }
    }

    const exceedsSizeLimit = files.some((file) => {
      const isDoc = isDocumentFile(file);
      const limit = isDoc ? 20 * 1024 * 1024 : 5 * 1024 * 1024;
      return file.size > limit;
    });

    const totalExistingBytes = attachments.value.reduce((sum, item) => {
      if (item.file?.size) return sum + item.file.size;
      if (item.data) return sum + item.data.length * 0.75;
      return sum;
    }, 0);

    const incomingTotalBytes = files.reduce((sum, file) => sum + file.size, 0);

    if (
      exceedsSizeLimit ||
      files.length + attachments.value.length > 8 ||
      totalExistingBytes + incomingTotalBytes > 30 * 1024 * 1024
    ) {
      uiStore.pushToast({
        type: "warning",
        title: "附件超过限制",
        message: "图片最多 5 MB，文档最多 20 MB，每条消息最多 8 个附件。",
      });
      return 0;
    }

    const isSupported = (file: File) => {
      const name = file.name.toLowerCase();
      if (SUPPORTED_FILE_EXTENSIONS.some((ext) => name.endsWith(ext))) {
        return true;
      }
      return SUPPORTED_CHAT_ATTACHMENT_MIME_TYPES.includes(
        file.type as (typeof SUPPORTED_CHAT_ATTACHMENT_MIME_TYPES)[number],
      );
    };

    const validFiles = files.filter(isSupported);
    const invalidFiles = files.filter((file) => !isSupported(file));

    const seen = new Set<string>();
    const duplicateFiles: File[] = [];
    const uniqueFiles = validFiles.filter((file) => {
      const key = JSON.stringify([file.name, file.size]);
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
        message: "当前聊天支持图片（JPEG/PNG/WEBP）以及文档（PDF/TXT/MD/JSON/CSV）。",
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

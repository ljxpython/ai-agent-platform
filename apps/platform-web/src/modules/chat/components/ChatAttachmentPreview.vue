<script setup lang="ts">
import { computed } from "vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import {
  getChatAttachmentDataUrl,
  getChatAttachmentName,
  type ChatAttachmentBlock,
} from "@/utils/chat-content";

const props = withDefaults(
  defineProps<{
    block: ChatAttachmentBlock;
    removable?: boolean;
    compact?: boolean;
  }>(),
  {
    removable: false,
    compact: false,
  },
);

const emit = defineEmits<{
  remove: [];
}>();

const isImage = computed(() => props.block.type === "image");
const attachmentName = computed(() => getChatAttachmentName(props.block));
const imageUrl = computed(() =>
  isImage.value ? getChatAttachmentDataUrl(props.block) : "",
);

function formatBytes(bytes?: number): string {
  if (bytes == null || bytes <= 0) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const fileTypeLabel = computed(() => {
  if (isImage.value) return "图片";
  const name = attachmentName.value.toLowerCase();
  const mime = (props.block.mimeType || "").toLowerCase();
  let label = "文本文档";
  if (name.endsWith(".pdf") || mime.includes("pdf")) label = "PDF 文档";
  else if (name.endsWith(".docx") || mime.includes("wordprocessingml"))
    label = "Word 文档";
  else if (name.endsWith(".pptx") || mime.includes("presentationml"))
    label = "PPT 演示文稿";
  else if (
    name.endsWith(".xlsx") ||
    name.endsWith(".xls") ||
    mime.includes("spreadsheetml")
  )
    label = "Excel 表格";
  else if (name.endsWith(".csv") || mime.includes("csv")) label = "CSV 表格";
  else if (name.endsWith(".json") || mime.includes("json")) label = "JSON 数据";
  else if (name.endsWith(".md") || name.endsWith(".markdown"))
    label = "Markdown";

  const sizeStr = formatBytes(props.block.file?.size);
  return sizeStr ? `${label} · ${sizeStr}` : label;
});
</script>

<template>
  <div
    class="pw-panel relative overflow-hidden p-0"
    :class="compact ? 'max-w-[180px]' : 'max-w-[220px]'"
  >
    <button
      v-if="removable"
      type="button"
      class="absolute right-2 top-2 z-10 rounded-full bg-slate-950/70 p-1 text-white transition hover:bg-slate-950"
      aria-label="移除附件"
      @click="emit('remove')"
    >
      <BaseIcon name="x" size="xs" />
    </button>

    <template v-if="isImage">
      <img
        :src="imageUrl"
        :alt="attachmentName"
        class="block w-full object-cover"
        :class="compact ? 'h-28' : 'h-36'"
      />
      <div
        class="border-t border-gray-100 px-3 py-2 text-xs font-medium text-gray-600 dark:border-dark-700 dark:text-dark-200 truncate"
        :title="attachmentName"
      >
        {{ attachmentName }}
      </div>
    </template>

    <template v-else>
      <div class="flex items-start gap-3 px-3 py-3">
        <span
          class="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-primary-50 text-primary-600 dark:bg-primary-950/30 dark:text-primary-200"
        >
          <BaseIcon name="file" size="md" />
        </span>
        <div class="min-w-0 flex-1">
          <div
            class="truncate text-sm font-semibold text-gray-900 dark:text-white"
            :title="attachmentName"
          >
            {{ attachmentName }}
          </div>
          <div
            class="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-gray-500 dark:text-dark-300"
          >
            <span>{{ fileTypeLabel }}</span>
            <span
              v-if="
                block.uploadStatus === 'uploading' ||
                block.uploadStatus === 'hashing'
              "
              class="text-primary-600 dark:text-primary-400 font-medium"
            >
              · 上传中
            </span>
            <span
              v-else-if="block.uploadStatus === 'failed'"
              class="text-red-600 dark:text-red-400 font-medium"
            >
              · 上传失败
            </span>
            <span
              v-else-if="block.uploadStatus === 'uploaded'"
              class="text-emerald-600 dark:text-emerald-400 font-medium"
            >
              · 已上传
            </span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

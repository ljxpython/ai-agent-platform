<script setup lang="ts">
import { computed, ref } from "vue";
import { isAxiosError } from "axios";
import {
  downloadThreadFile,
  previewThreadFileInNewTab,
  type RuntimeFileRef,
} from "@/services/threads/files.service";
import BaseIcon from "@/components/base/BaseIcon.vue";

const props = defineProps<{
  projectId: string;
  threadId: string;
  fileRef: RuntimeFileRef;
  alt?: string;
}>();

const actionLoading = ref(false);
const error = ref<string | null>(null);

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const filename = computed(() => {
  return props.fileRef.file_name || props.fileRef.path.split("/").pop() || "document";
});

const fileBadge = computed(() => {
  const mime = (props.fileRef.mime_type || "").toLowerCase();
  const name = filename.value.toLowerCase();
  if (mime.includes("pdf") || name.endsWith(".pdf")) return { text: "PDF", bg: "bg-red-50 text-red-600 dark:bg-red-950/40 dark:text-red-300 border-red-200 dark:border-red-900/50" };
  if (mime.includes("csv") || name.endsWith(".csv")) return { text: "CSV", bg: "bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-300 border-emerald-200 dark:border-emerald-900/50" };
  if (mime.includes("json") || name.endsWith(".json")) return { text: "JSON", bg: "bg-amber-50 text-amber-600 dark:bg-amber-950/40 dark:text-amber-300 border-amber-200 dark:border-amber-900/50" };
  if (name.endsWith(".md") || name.endsWith(".markdown")) return { text: "MD", bg: "bg-blue-50 text-blue-600 dark:bg-blue-950/40 dark:text-blue-300 border-blue-200 dark:border-blue-900/50" };
  return { text: "TXT", bg: "bg-slate-50 text-slate-600 dark:bg-slate-800 dark:text-slate-300 border-slate-200 dark:border-slate-700" };
});

async function handlePreviewInNewTab() {
  actionLoading.value = true;
  error.value = null;
  try {
    await previewThreadFileInNewTab(
      props.projectId,
      props.threadId,
      props.fileRef.path,
      filename.value,
    );
  } catch (err: unknown) {
    if (isAxiosError(err) && err.response) {
      if (err.response.status === 403) {
        error.value = "无权访问此文档";
      } else if (err.response.status === 404) {
        error.value = "文档已不存在";
      } else {
        error.value = "文档获取失败";
      }
    } else {
      error.value = "网络错误，无法预览文档";
    }
  } finally {
    actionLoading.value = false;
  }
}

async function handleDownload(event: MouseEvent) {
  event.stopPropagation();
  actionLoading.value = true;
  error.value = null;
  try {
    await downloadThreadFile(
      props.projectId,
      props.threadId,
      props.fileRef.path,
      filename.value,
    );
  } catch (err: unknown) {
    if (isAxiosError(err) && err.response) {
      if (err.response.status === 403) {
        error.value = "无权访问此文档";
      } else if (err.response.status === 404) {
        error.value = "文档已不存在";
      } else {
        error.value = "文档下载失败";
      }
    } else {
      error.value = "网络错误，无法下载文档";
    }
  } finally {
    actionLoading.value = false;
  }
}
</script>

<template>
  <div class="thread-file-container my-2 max-w-md rounded-xl border border-slate-200 bg-white p-3 shadow-xs dark:border-dark-700 dark:bg-dark-800 transition-all hover:border-primary-300 dark:hover:border-primary-700">
    <div class="flex items-start justify-between gap-3">
      <!-- 文件类型徽标 -->
      <div
        class="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border font-mono text-xs font-bold tracking-wider"
        :class="fileBadge.bg"
      >
        {{ fileBadge.text }}
      </div>

      <!-- 文件信息 -->
      <div class="min-w-0 flex-1">
        <div
          class="truncate text-sm font-semibold text-slate-900 dark:text-white"
          :title="filename"
        >
          {{ filename }}
        </div>
        <div class="mt-1 flex items-center gap-2 text-xs text-slate-500 dark:text-dark-300">
          <span>{{ formatBytes(fileRef.size_bytes) }}</span>
          <span>·</span>
          <span class="font-mono text-[11px] text-slate-400 dark:text-dark-400">
            {{ fileRef.sha256.slice(0, 8) }}
          </span>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="flex shrink-0 items-center gap-1.5">
        <button
          type="button"
          :disabled="actionLoading"
          class="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100 hover:text-slate-900 disabled:opacity-50 dark:border-dark-600 dark:bg-dark-700 dark:text-dark-200 dark:hover:bg-dark-600 dark:hover:text-white transition-colors"
          title="在新标签页预览文档"
          @click="handlePreviewInNewTab"
        >
          <BaseIcon
            v-if="!actionLoading"
            name="sparkle"
            size="xs"
          />
          <BaseIcon
            v-else
            name="refresh"
            size="xs"
            class="animate-spin"
          />
          <span>预览</span>
        </button>

        <button
          type="button"
          :disabled="actionLoading"
          class="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100 hover:text-slate-900 disabled:opacity-50 dark:border-dark-600 dark:bg-dark-700 dark:text-dark-200 dark:hover:bg-dark-600 dark:hover:text-white transition-colors"
          title="下载文档"
          @click="handleDownload"
        >
          <BaseIcon
            name="download"
            size="xs"
          />
          <span>下载</span>
        </button>
      </div>
    </div>

    <!-- 错误状态提示 -->
    <div
      v-if="error"
      class="mt-2 rounded-lg border border-red-200 bg-red-50/70 px-2.5 py-1.5 text-xs text-red-600 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-400 flex items-center justify-between"
    >
      <div class="flex items-center gap-1.5">
        <BaseIcon
          name="alert"
          size="xs"
        />
        <span>{{ error }}</span>
      </div>
      <button
        type="button"
        class="font-medium underline hover:text-red-700 dark:hover:text-red-300"
        @click="handlePreviewInNewTab"
      >
        重试
      </button>
    </div>
  </div>
</template>

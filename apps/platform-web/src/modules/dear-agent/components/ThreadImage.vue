<script setup lang="ts">
import { computed, onScopeDispose, ref, watch } from "vue";
import { isAxiosError } from "axios";
import {
  getThreadImageBlob,
  type RuntimeImageRef,
} from "@/services/threads/images.service";
import BaseIcon from "@/components/base/BaseIcon.vue";

const props = defineProps<{
  projectId: string;
  threadId: string;
  imageRef: RuntimeImageRef;
  alt?: string;
}>();

const loading = ref(true);
const error = ref<string | null>(null);
const blobUrl = ref<string | null>(null);
const showPreview = ref(false);

function cleanupBlob() {
  if (blobUrl.value) {
    URL.revokeObjectURL(blobUrl.value);
    blobUrl.value = null;
  }
}

const filename = computed(() => {
  const parts = props.imageRef.path.split("/");
  return parts[parts.length - 1] || "image.png";
});

async function loadImage() {
  cleanupBlob();
  loading.value = true;
  error.value = null;

  try {
    const blob = await getThreadImageBlob(
      props.projectId,
      props.threadId,
      props.imageRef.path,
    );
    blobUrl.value = URL.createObjectURL(blob);
  } catch (err: unknown) {
    if (isAxiosError(err) && err.response) {
      if (err.response.status === 403) {
        error.value = "无权访问此图片";
      } else if (err.response.status === 404) {
        error.value = "图片已不存在";
      } else {
        error.value = "图片加载失败";
      }
    } else {
      error.value = "网络错误，无法加载图片";
    }
  } finally {
    loading.value = false;
  }
}

watch(
  [() => props.projectId, () => props.threadId, () => props.imageRef.path],
  () => {
    void loadImage();
  },
  { immediate: true },
);

onScopeDispose(() => {
  cleanupBlob();
});

function downloadImage(event: MouseEvent) {
  event.stopPropagation();
  if (!blobUrl.value) return;
  const link = document.createElement("a");
  link.href = blobUrl.value;
  link.download = filename.value;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}
</script>

<template>
  <div class="thread-image-container my-2 max-w-md rounded-lg border border-slate-200 bg-slate-50 p-2 shadow-sm dark:border-slate-800 dark:bg-slate-900/50">
    <div
      v-if="loading"
      class="flex h-48 w-full items-center justify-center rounded-md bg-slate-100 dark:bg-slate-800 animate-pulse text-slate-400"
    >
      <BaseIcon
        name="refresh"
        class="h-6 w-6 animate-spin mr-2"
      />
      <span class="text-xs">加载图片中...</span>
    </div>

    <div
      v-else-if="error"
      class="flex flex-col items-center justify-center rounded-md border border-dashed border-red-200 bg-red-50/50 p-4 text-center dark:border-red-900/50 dark:bg-red-950/20"
    >
      <BaseIcon
        name="alert"
        class="h-6 w-6 text-red-500 mb-1"
      />
      <span class="text-xs font-medium text-red-600 dark:text-red-400">{{ error }}</span>
      <span
        class="text-[11px] text-slate-500 truncate max-w-xs mt-1"
        :title="imageRef.path"
      >{{ imageRef.path }}</span>
      <button
        type="button"
        class="mt-2 text-xs text-blue-600 hover:underline dark:text-blue-400"
        @click="loadImage"
      >
        重试
      </button>
    </div>

    <div
      v-else-if="blobUrl"
      class="group relative overflow-hidden rounded-md"
    >
      <img
        :src="blobUrl"
        :alt="alt || filename"
        class="max-h-72 w-auto max-w-full cursor-zoom-in rounded-md object-contain transition-transform duration-200 group-hover:scale-[1.01]"
        @click="showPreview = true"
      >
      <div class="mt-1 flex items-center justify-between px-1 text-[11px] text-slate-500">
        <span
          class="truncate max-w-[200px]"
          :title="filename"
        >{{ filename }}</span>
        <button
          type="button"
          class="flex items-center gap-1 hover:text-blue-600 dark:hover:text-blue-400"
          title="下载图片"
          @click="downloadImage"
        >
          <BaseIcon
            name="download"
            class="h-3.5 w-3.5"
          />
          <span>下载</span>
        </button>
      </div>
    </div>

    <!-- 预览弹窗 -->
    <Teleport to="body">
      <div
        v-if="showPreview && blobUrl"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 cursor-zoom-out"
        @click="showPreview = false"
      >
        <div class="relative max-h-[90vh] max-w-[90vw] overflow-auto">
          <img
            :src="blobUrl"
            :alt="alt || filename"
            class="max-h-[90vh] max-w-[90vw] object-contain rounded-lg shadow-2xl"
          >
          <button
            type="button"
            class="absolute top-2 right-2 rounded-full bg-black/60 p-2 text-white hover:bg-black/80"
            @click.stop="showPreview = false"
          >
            <BaseIcon
              name="x"
              class="h-5 w-5"
            />
          </button>
        </div>
      </div>
    </Teleport>
  </div>
</template>

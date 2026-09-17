<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import {
  getWorkspacePreview,
  type WorkspacePreviewResult,
} from '@/services/threads/workspace.service';
import BaseIcon from '@/components/base/BaseIcon.vue';
import SandboxedHtmlFrame from './SandboxedHtmlFrame.vue';
import { renderMarkdown } from '@/utils/markdown';
import { copyText } from '@/utils/clipboard';

const props = defineProps<{
  projectId?: string;
  threadId?: string;
  path: string;
  previewResult: WorkspacePreviewResult | null;
  loading: boolean;
  error: string | null;
}>();

const emit = defineEmits<{
  (e: 'download', path: string): void;
}>();

const fileName = computed(() => {
  return props.path.split('/').filter(Boolean).pop() || '';
});

// Markdown 模式切换：'preview' | 'source'
const markdownViewMode = ref<'preview' | 'source'>('preview');

// 单张独立图片预览时的 Blob Object URL
const imageUrl = ref<string>('');
watch(
  () => props.previewResult?.imageBlob,
  (blob) => {
    if (imageUrl.value) {
      URL.revokeObjectURL(imageUrl.value);
      imageUrl.value = '';
    }
    if (blob) {
      imageUrl.value = URL.createObjectURL(blob);
    }
  },
  { immediate: true },
);

// Markdown 内部工作区图片解析与 Blob Object URL 资源池
const markdownBlobUrls = ref<string[]>([]);
const resolvedMarkdown = ref<string>('');

function cleanupMarkdownBlobUrls() {
  for (const url of markdownBlobUrls.value) {
    try {
      URL.revokeObjectURL(url);
    } catch {
      // 忽略清理异常
    }
  }
  markdownBlobUrls.value = [];
}

function resolveWorkspacePath(imageSrc: string, baseFilePath: string): string {
  const trimmed = imageSrc.trim().split('?')[0].split('#')[0];
  if (!trimmed || trimmed.startsWith('http://') || trimmed.startsWith('https://') || trimmed.startsWith('data:')) {
    return '';
  }
  if (trimmed.startsWith('/workspace/')) {
    return trimmed;
  }
  if (trimmed.startsWith('/workspace')) {
    return '/workspace' + trimmed.slice('/workspace'.length);
  }
  if (trimmed.startsWith('/')) {
    return `/workspace${trimmed}`;
  }
  // 相对路径常见目录前缀
  if (
    trimmed.startsWith('charts/') ||
    trimmed.startsWith('generated/') ||
    trimmed.startsWith('work/') ||
    trimmed.startsWith('outputs/') ||
    trimmed.startsWith('reports/')
  ) {
    return `/workspace/${trimmed}`;
  }

  // 基于当前文档所在目录进行相对路径解析
  const dir = baseFilePath.split('/').slice(0, -1).join('/') || '/workspace';
  const combined = `${dir}/${trimmed}`.replace(/\/+/g, '/');
  const segments = combined.split('/');
  const stack: string[] = [];
  for (const seg of segments) {
    if (!seg || seg === '.') continue;
    if (seg === '..') {
      stack.pop();
    } else {
      stack.push(seg);
    }
  }
  const normalized = '/' + stack.join('/');
  return normalized.startsWith('/workspace') ? normalized : `/workspace${normalized}`;
}

watch(
  [
    () => props.previewResult?.textPreview?.text,
    () => props.path,
    () => props.projectId,
    () => props.threadId,
  ],
  async ([rawText, currentPath, projId, thId]) => {
    cleanupMarkdownBlobUrls();

    if (!rawText || props.previewResult?.kind !== 'markdown') {
      resolvedMarkdown.value = rawText || '';
      return;
    }

    // 先同步展示原文本，保障即时呈现
    resolvedMarkdown.value = rawText;

    if (!projId || !thId) {
      return;
    }

    // 提取所有可能的图片路径
    const imgRegexMarkdown = /!\[([^\]]*)\]\(([^)]+)\)/g;
    const imgRegexHtml = /<img\s+[^>]*src=["']([^"']+)["'][^>]*>/gi;
    const candidates = new Set<string>();

    let match: RegExpExecArray | null;
    while ((match = imgRegexMarkdown.exec(rawText)) !== null) {
      if (match[2]) candidates.add(match[2].trim());
    }
    while ((match = imgRegexHtml.exec(rawText)) !== null) {
      if (match[1]) candidates.add(match[1].trim());
    }

    if (candidates.size === 0) {
      return;
    }

    let modifiedText = rawText;
    const newBlobUrls: string[] = [];

    for (const src of candidates) {
      const workspaceTarget = resolveWorkspacePath(src, currentPath);
      if (!workspaceTarget) continue;

      try {
        const preview = await getWorkspacePreview(projId, thId, workspaceTarget);
        if (preview.kind === 'image' && preview.imageBlob) {
          const blobUrl = URL.createObjectURL(preview.imageBlob);
          newBlobUrls.push(blobUrl);
          // 全局替换该图片路径为本地 Object URL
          modifiedText = modifiedText.split(src).join(blobUrl);
        }
      } catch {
        // 单张图片拉取失败不影响其它图片及文本渲染
      }
    }

    markdownBlobUrls.value = newBlobUrls;
    resolvedMarkdown.value = modifiedText;
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  if (imageUrl.value) {
    URL.revokeObjectURL(imageUrl.value);
  }
  cleanupMarkdownBlobUrls();
});

// 复制顶部按钮状态
const copied = ref(false);
function copyContent(text: string) {
  void copyText(text);
  copied.value = true;
  setTimeout(() => {
    copied.value = false;
  }, 1500);
}

// Markdown 内部代码块一键复制事件代理
async function handleMarkdownClick(event: MouseEvent) {
  const target = event.target as HTMLElement | null;
  const copyButton = target?.closest('[data-copy-code]') as HTMLButtonElement | null;
  if (!copyButton) return;

  const codeElement = copyButton.closest('.pw-markdown-code')?.querySelector('code');
  const code = codeElement?.textContent || '';
  if (!code) return;

  const success = await copyText(code);
  if (success) {
    copyButton.textContent = '已复制';
    window.setTimeout(() => {
      copyButton.textContent = '复制';
    }, 1600);
  }
}

// 代码行号处理
const codeLines = computed(() => {
  if (!props.previewResult?.textPreview?.text) return [];
  return props.previewResult.textPreview.text.split('\n');
});
</script>

<template>
  <div class="flex h-full w-full flex-col bg-white text-gray-900 dark:bg-dark-900 dark:text-gray-100">
    <!-- 空状态 -->
    <div
      v-if="!path"
      class="flex h-full flex-col items-center justify-center p-8 text-center text-gray-400 dark:text-dark-400"
    >
      <BaseIcon
        name="file"
        class="h-10 w-10 stroke-1 opacity-40"
      />
      <p class="mt-3 text-sm">选择左侧文件或产物查看预览</p>
    </div>

    <!-- 加载中 -->
    <div
      v-else-if="loading"
      class="flex h-full flex-col items-center justify-center p-8 text-center text-gray-400 dark:text-dark-400"
    >
      <BaseIcon
        name="refresh"
        class="h-6 w-6 animate-spin text-primary-500"
      />
      <p class="mt-2 text-xs">正在加载预览...</p>
    </div>

    <!-- 错误状态 -->
    <div
      v-else-if="error"
      class="flex h-full flex-col items-center justify-center p-8 text-center"
    >
      <BaseIcon
        name="alert"
        class="h-8 w-8 text-amber-500"
      />
      <p class="mt-3 text-sm font-medium text-gray-700 dark:text-dark-200">{{ error }}</p>
      <button
        type="button"
        class="mt-4 inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 dark:border-dark-700 dark:bg-dark-800 dark:text-dark-200 dark:hover:bg-dark-700"
        @click="emit('download', path)"
      >
        <BaseIcon
          name="download"
          class="h-3.5 w-3.5"
        />
        直接下载原文件
      </button>
    </div>

    <!-- 正常预览内容 -->
    <div
      v-else
      class="flex h-full flex-col"
    >
      <!-- 预览顶部工具栏 -->
      <div
        class="flex h-11 shrink-0 items-center justify-between border-b border-gray-200 bg-gray-50/60 px-4 dark:border-dark-800 dark:bg-dark-950/40"
      >
        <div class="flex min-w-0 items-center gap-2">
          <BaseIcon
            name="file"
            class="h-4 w-4 shrink-0 text-gray-400"
          />
          <span
            class="truncate text-xs font-semibold text-gray-800 dark:text-dark-100"
            :title="path"
          >
            {{ fileName }}
          </span>
          <span
            v-if="previewResult?.textPreview?.truncated"
            class="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] text-amber-800 dark:bg-amber-950/60 dark:text-amber-300"
          >
            截断显示 (前 256KB)
          </span>
        </div>

        <div class="flex items-center gap-1.5">
          <!-- Markdown 切换按钮 -->
          <template v-if="previewResult?.kind === 'markdown'">
            <button
              type="button"
              class="rounded px-2 py-1 text-xs font-medium transition-colors"
              :class="
                markdownViewMode === 'preview'
                  ? 'bg-white text-primary-600 shadow-sm dark:bg-dark-800 dark:text-primary-400'
                  : 'text-gray-500 hover:text-gray-900 dark:text-dark-400 dark:hover:text-dark-100'
              "
              @click="markdownViewMode = 'preview'"
            >
              渲染
            </button>
            <button
              type="button"
              class="rounded px-2 py-1 text-xs font-medium transition-colors"
              :class="
                markdownViewMode === 'source'
                  ? 'bg-white text-primary-600 shadow-sm dark:bg-dark-800 dark:text-primary-400'
                  : 'text-gray-500 hover:text-gray-900 dark:text-dark-400 dark:hover:text-dark-100'
              "
              @click="markdownViewMode = 'source'"
            >
              源码
            </button>
          </template>

          <!-- 复制代码按钮 -->
          <button
            v-if="previewResult?.textPreview?.text"
            type="button"
            class="inline-flex items-center gap-1 rounded px-2 py-1 text-xs text-gray-600 hover:bg-gray-200/70 hover:text-gray-900 dark:text-dark-300 dark:hover:bg-dark-800 dark:hover:text-dark-100"
            @click="copyContent(previewResult.textPreview.text)"
          >
            <BaseIcon
              :name="copied ? 'check' : 'copy'"
              class="h-3.5 w-3.5"
            />
            {{ copied ? '已复制' : '复制' }}
          </button>

          <!-- 下载按钮 -->
          <button
            type="button"
            class="inline-flex items-center gap-1 rounded px-2 py-1 text-xs text-gray-600 hover:bg-gray-200/70 hover:text-gray-900 dark:text-dark-300 dark:hover:bg-dark-800 dark:hover:text-dark-100"
            @click="emit('download', path)"
          >
            <BaseIcon
              name="download"
              class="h-3.5 w-3.5"
            />
            下载
          </button>
        </div>
      </div>

      <!-- 预览主体区 -->
      <div class="relative min-h-0 flex-1 overflow-auto">
        <!-- 1. HTML 沙箱 -->
        <div
          v-if="previewResult?.kind === 'html-sandbox'"
          class="h-full w-full p-2"
        >
          <SandboxedHtmlFrame
            :html="previewResult.htmlContent || ''"
            :title="fileName"
          />
        </div>

        <!-- 2. 图片预览 -->
        <div
          v-else-if="previewResult?.kind === 'image'"
          class="flex h-full items-center justify-center p-4"
        >
          <img
            :src="imageUrl"
            :alt="fileName"
            class="max-h-full max-w-full rounded-lg object-contain shadow-sm"
          />
        </div>

        <!-- 3. Markdown 渲染态 -->
        <div
          v-else-if="previewResult?.kind === 'markdown' && markdownViewMode === 'preview'"
          class="pw-markdown pw-workspace-markdown max-w-none p-6"
          @click="handleMarkdownClick"
          v-html="renderMarkdown(resolvedMarkdown || previewResult.textPreview?.text || '')"
        />

        <!-- 4. 文本或 Markdown 源码态 -->
        <div
          v-else-if="previewResult?.textPreview?.text"
          class="flex min-h-full font-mono text-xs leading-5"
        >
          <!-- 行号 -->
          <div
            class="select-none border-r border-gray-200 bg-gray-50/60 py-4 pr-3 pl-3 text-right text-gray-400 dark:border-dark-800 dark:bg-dark-950/40 dark:text-dark-500"
          >
            <div
              v-for="(_, index) in codeLines"
              :key="index"
            >
              {{ index + 1 }}
            </div>
          </div>
          <!-- 代码正文 -->
          <pre
            class="flex-1 overflow-x-auto py-4 px-4 text-gray-800 dark:text-dark-100"
          ><code>{{ previewResult.textPreview.text }}</code></pre>
        </div>

        <!-- 5. 纯下载卡片（未知二进制或过大文件） -->
        <div
          v-else
          class="flex h-full flex-col items-center justify-center p-8 text-center"
        >
          <BaseIcon
            name="archive"
            class="h-12 w-12 text-gray-400"
          />
          <h3 class="mt-3 text-sm font-semibold text-gray-800 dark:text-dark-100">
            {{ fileName }}
          </h3>
          <p class="mt-1 text-xs text-gray-500 dark:text-dark-400">
            此文件类型不支持在线预览，可点击下方按钮下载至本地查看。
          </p>
          <button
            type="button"
            class="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-primary-600 px-4 py-2 text-xs font-medium text-white shadow-sm hover:bg-primary-700"
            @click="emit('download', path)"
          >
            <BaseIcon
              name="download"
              class="h-4 w-4"
            />
            下载原文件
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.pw-workspace-markdown :deep(.pw-markdown-code) {
  background-color: #020617 !important;
  border-color: rgba(30, 41, 59, 0.8) !important;
}

.pw-workspace-markdown :deep(.pw-markdown-code pre) {
  background-color: transparent !important;
  margin: 0 !important;
}

.pw-workspace-markdown :deep(.pw-markdown-code pre code) {
  color: #f1f5f9 !important;
  background-color: transparent !important;
}

.pw-workspace-markdown :deep(.pw-markdown-code-header) {
  border-bottom-color: rgba(255, 255, 255, 0.1) !important;
  color: #94a3b8 !important;
}

.pw-workspace-markdown :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 0.5rem;
  margin-top: 1rem;
  margin-bottom: 1rem;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
}
</style>

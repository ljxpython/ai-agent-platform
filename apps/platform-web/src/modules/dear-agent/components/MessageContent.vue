<script setup lang="ts">
import { ref } from "vue";
import MarkdownContent from "@/components/platform/MarkdownContent.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import ThreadImage from "./ThreadImage.vue";
import ThreadFile from "./ThreadFile.vue";
import type { ContentItem } from "../transcript";

defineProps<{
  blocks: ContentItem[];
  isStreaming?: boolean;
  projectId?: string;
  threadId?: string;
}>();
const expanded = ref<Record<string, boolean>>({});
</script>

<template>
  <div class="min-w-0 space-y-3 break-words">
    <template
      v-for="block in blocks"
      :key="block.key"
    >
      <div
        v-if="block.kind === 'loading'"
        class="flex items-center gap-2 text-xs text-primary-600 dark:text-primary-400 py-1 font-medium"
      >
        <span class="relative flex h-2 w-2">
          <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary-400 opacity-75" />
          <span class="relative inline-flex rounded-full h-2 w-2 bg-primary-500" />
        </span>
        <span>Agent 正在组织答复...</span>
      </div>
      <div
        v-else-if="block.kind === 'text'"
        class="relative leading-relaxed"
      >
        <MarkdownContent
          :content="block.text.length > 12000 && !expanded[block.key] ? block.text.slice(0, 12000) : block.text"
        />
        <span
          v-if="isStreaming"
          class="inline-block h-4 w-1.5 translate-y-0.5 animate-pulse bg-primary-600 dark:bg-primary-400 ml-0.5 align-middle rounded-xs"
          aria-hidden="true"
        />
      </div>
      <details
        v-else-if="block.kind === 'reasoning'"
        class="group/reasoning my-1 select-none transition-all"
        :open="expanded[block.key] ?? !!isStreaming"
        @toggle="
          expanded[block.key] = ($event.target as HTMLDetailsElement).open
        "
      >
        <summary class="inline-flex max-w-full cursor-pointer items-center gap-1.5 text-xs text-gray-500 hover:text-gray-800 dark:text-dark-400 dark:hover:text-gray-200 transition-colors">
          <span
            v-if="isStreaming"
            class="relative flex h-2 w-2 mr-0.5"
          >
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
            <span class="relative inline-flex rounded-full h-2 w-2 bg-blue-500" />
          </span>
          <span
            v-else
            class="text-[13px] opacity-70"
          >
            ⚛
          </span>
          <span class="font-medium text-gray-600 dark:text-dark-300">Think</span>
          <span class="text-gray-400 dark:text-dark-500">·</span>
          <span class="truncate font-mono text-[11px] text-gray-400 dark:text-dark-400 max-w-[500px]">
            {{ block.text }}
          </span>
        </summary>
        <div
          class="mt-2 max-h-96 overflow-auto whitespace-pre-wrap rounded-lg border border-gray-100 bg-gray-50/50 p-3 text-xs text-gray-600 dark:border-dark-800 dark:bg-dark-900/40 dark:text-dark-300 leading-relaxed font-mono select-text"
        >
          {{ block.text }}
        </div>
      </details>
      <details
        v-else-if="block.kind === 'unknown'"
        class="rounded-lg border border-gray-200 p-2.5 text-xs text-gray-500 dark:border-dark-700"
        @toggle="
          expanded[block.key] = ($event.target as HTMLDetailsElement).open
        "
      >
        <summary class="cursor-pointer text-xs text-gray-500">
          其他内容
        </summary>
        <pre
          v-if="expanded[block.key]"
          class="mt-2 max-h-96 overflow-auto whitespace-pre-wrap text-xs font-mono"
        >{{ block.text }}</pre>
      </details>
      <div
        v-else-if="block.kind === 'image' && block.imageRef"
        class="my-1"
      >
        <ThreadImage
          :project-id="projectId || ''"
          :thread-id="threadId || ''"
          :image-ref="block.imageRef"
          :alt="block.text"
        />
      </div>
      <div
        v-else-if="block.kind === 'image' && block.url"
        class="overflow-hidden rounded-xl border border-gray-200 shadow-xs dark:border-dark-700 max-w-md my-1"
      >
        <img
          :src="block.url"
          :alt="block.text"
          loading="lazy"
          referrerpolicy="no-referrer"
          class="max-h-96 w-full object-contain bg-gray-50 dark:bg-dark-900"
        >
      </div>
      <div
        v-else-if="block.kind === 'file' && block.fileRef"
        class="my-1"
      >
        <ThreadFile
          :project-id="projectId || ''"
          :thread-id="threadId || ''"
          :file-ref="block.fileRef"
          :alt="block.text"
        />
      </div>
      <a
        v-else-if="block.kind === 'file' && block.url"
        :href="block.url"
        target="_blank"
        rel="noopener noreferrer"
        class="inline-flex items-center gap-1.5 rounded-lg border border-primary-200/80 bg-primary-50/60 px-3 py-1.5 text-xs font-medium text-primary-700 hover:bg-primary-100/80 transition-colors dark:border-primary-900/50 dark:bg-primary-950/30 dark:text-primary-300"
      >
        <BaseIcon
          name="file"
          size="xs"
        />
        <span>{{ block.text }}</span>
      </a>
      <p
        v-else
        class="text-xs text-gray-500"
      >
        {{ block.text }} · 没有可安全打开的资源地址
      </p>
      <button
        v-if="block.kind === 'text' && block.text.length > 12000"
        class="text-xs underline text-primary-600 dark:text-primary-400"
        :aria-expanded="!!expanded[block.key]"
        @click="expanded[block.key] = !expanded[block.key]"
      >
        {{ expanded[block.key] ? '收起长内容' : '内容较长，展开全文（复制保留全文）' }}
      </button>
    </template>
  </div>
</template>

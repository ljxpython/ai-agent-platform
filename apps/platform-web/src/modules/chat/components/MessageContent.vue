<script setup lang="ts">
import { ref } from "vue";
import MarkdownContent from "@/components/platform/MarkdownContent.vue";
import type { ContentItem } from "../transcript";

defineProps<{
  blocks: ContentItem[];
  isStreaming?: boolean;
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
        class="flex items-center gap-2 text-xs text-gray-500 dark:text-dark-400 py-1"
      >
        <span class="inline-block h-2 w-2 animate-ping rounded-full bg-primary-500" />
        <span>Agent 正在组织答复...</span>
      </div>
      <div
        v-else-if="block.kind === 'text'"
        class="relative"
      >
        <MarkdownContent
          :content="block.text.length > 12000 && !expanded[block.key] ? block.text.slice(0, 12000) : block.text"
        />
        <span
          v-if="isStreaming"
          class="inline-block h-4 w-1.5 translate-y-0.5 animate-pulse bg-primary-600 dark:bg-primary-400 ml-0.5 align-middle"
          aria-hidden="true"
        />
      </div>
      <details
        v-else-if="block.kind === 'reasoning'"
        class="rounded-lg border border-gray-200 bg-gray-50/60 p-2.5 dark:border-dark-700 dark:bg-dark-800/50 text-xs"
        :open="expanded[block.key] ?? !!isStreaming"
        @toggle="
          expanded[block.key] = ($event.target as HTMLDetailsElement).open
        "
      >
        <summary class="cursor-pointer font-medium text-gray-600 dark:text-dark-300 select-none flex items-center gap-1.5">
          <span
            v-if="isStreaming"
            class="inline-block h-1.5 w-1.5 animate-ping rounded-full bg-amber-500"
          />
          <span>{{ isStreaming ? "正在思考中..." : "思考过程" }}</span>
        </summary>
        <div
          class="mt-2 max-h-96 overflow-auto whitespace-pre-wrap text-xs text-gray-700 dark:text-dark-200 border-t border-gray-200/60 pt-2 dark:border-dark-700"
        >
          {{ block.text }}
        </div>
      </details>
      <details
        v-else-if="block.kind === 'unknown'"
        class="text-xs text-gray-500"
        @toggle="
          expanded[block.key] = ($event.target as HTMLDetailsElement).open
        "
      >
        <summary class="cursor-pointer text-xs text-gray-500">
          其他内容
        </summary>
        <pre
          v-if="expanded[block.key]"
          class="mt-2 max-h-96 overflow-auto whitespace-pre-wrap text-xs"
        >{{ block.text }}</pre>
      </details>
      <img
        v-else-if="block.kind === 'image' && block.url"
        :src="block.url"
        :alt="block.text"
        loading="lazy"
        referrerpolicy="no-referrer"
        class="max-h-96 max-w-full rounded-lg"
      >
      <a
        v-else-if="block.kind === 'file' && block.url"
        :href="block.url"
        target="_blank"
        rel="noopener noreferrer"
        class="text-primary-600 underline"
      >{{ block.text }}</a>
      <p
        v-else
        class="text-xs text-gray-500"
      >
        {{ block.text }} · 没有可安全打开的资源地址
      </p>
      <button
        v-if="block.kind === 'text' && block.text.length > 12000"
        class="text-xs underline"
        :aria-expanded="!!expanded[block.key]"
        @click="expanded[block.key] = !expanded[block.key]"
      >
        {{ expanded[block.key] ? '收起长内容' : '内容较长，展开全文（复制保留全文）' }}
      </button>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import MarkdownContent from "@/components/platform/MarkdownContent.vue";
import type { ContentItem } from "../transcript";

defineProps<{ blocks: ContentItem[] }>();
const expanded = ref<Record<string, boolean>>({});
</script>

<template>
  <div class="min-w-0 space-y-3 break-words">
    <template
      v-for="block in blocks"
      :key="block.key"
    >
      <MarkdownContent
        v-if="block.kind === 'text'"
        :content="block.text.length > 12000 && !expanded[block.key] ? block.text.slice(0, 12000) : block.text"
      />
      <details
        v-else-if="block.kind === 'reasoning' || block.kind === 'unknown'"
        @toggle="
          expanded[block.key] = ($event.target as HTMLDetailsElement).open
        "
      >
        <summary class="cursor-pointer text-xs text-gray-500">
          {{ block.kind === "reasoning" ? "公开推理" : "其他内容" }}
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

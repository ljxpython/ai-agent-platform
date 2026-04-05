<script setup lang="ts">
import { computed } from 'vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import {
  getChatAttachmentDataUrl,
  getChatAttachmentName,
  type ChatAttachmentBlock
} from '@/utils/chat-content'

const props = withDefaults(
  defineProps<{
    block: ChatAttachmentBlock
    removable?: boolean
    compact?: boolean
  }>(),
  {
    removable: false,
    compact: false
  }
)

const emit = defineEmits<{
  remove: []
}>()

const isImage = computed(() => props.block.type === 'image')
const attachmentName = computed(() => getChatAttachmentName(props.block))
const imageUrl = computed(() => (isImage.value ? getChatAttachmentDataUrl(props.block) : ''))
</script>

<template>
  <div
    class="relative overflow-hidden rounded-[20px] border border-white/80 bg-white/90 shadow-soft dark:border-dark-700 dark:bg-dark-900/85"
    :class="compact ? 'max-w-[180px]' : 'max-w-[220px]'"
  >
    <button
      v-if="removable"
      type="button"
      class="absolute right-2 top-2 z-10 rounded-full bg-slate-950/70 p-1 text-white transition hover:bg-slate-950"
      aria-label="移除附件"
      @click="emit('remove')"
    >
      <BaseIcon
        name="x"
        size="xs"
      />
    </button>

    <template v-if="isImage">
      <img
        :src="imageUrl"
        :alt="attachmentName"
        class="block w-full object-cover"
        :class="compact ? 'h-28' : 'h-36'"
      >
      <div class="border-t border-gray-100 px-3 py-2 text-xs font-medium text-gray-600 dark:border-dark-700 dark:text-dark-200">
        {{ attachmentName }}
      </div>
    </template>

    <template v-else>
      <div class="flex items-start gap-3 px-3 py-3">
        <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-primary-50 text-primary-600 dark:bg-primary-950/30 dark:text-primary-200">
          <BaseIcon
            name="file"
            size="md"
          />
        </span>
        <div class="min-w-0">
          <div class="break-all text-sm font-semibold text-gray-900 dark:text-white">
            {{ attachmentName }}
          </div>
          <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
            PDF 文档
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseSelect from '@/components/base/BaseSelect.vue'
import SurfaceCard from '@/components/base/SurfaceCard.vue'

export type KnowledgeQuerySettings = {
  mode: string
  response_type: string
  stream: boolean
  top_k: number
  chunk_top_k: number
  max_entity_tokens: number
  max_relation_tokens: number
  max_total_tokens: number
  only_need_context: boolean
  only_need_prompt: boolean
  enable_rerank: boolean
  user_prompt: string
}

const props = defineProps<{
  modelValue: KnowledgeQuerySettings
  recentPrompts: string[]
}>()

const emit = defineEmits<{
  'update:modelValue': [KnowledgeQuerySettings]
}>()

const defaults: KnowledgeQuerySettings = {
  mode: 'mix',
  response_type: 'Multiple Paragraphs',
  stream: false,
  top_k: 40,
  chunk_top_k: 20,
  max_entity_tokens: 6000,
  max_relation_tokens: 8000,
  max_total_tokens: 30000,
  only_need_context: false,
  only_need_prompt: false,
  enable_rerank: true,
  user_prompt: '',
}

const presetPrompts = computed(() => props.recentPrompts.filter((item) => item.trim()).slice(0, 8))

function update<K extends keyof KnowledgeQuerySettings>(key: K, value: KnowledgeQuerySettings[K]) {
  emit('update:modelValue', {
    ...props.modelValue,
    [key]: value,
  })
}

function reset() {
  emit('update:modelValue', { ...defaults })
}
</script>

<template>
  <SurfaceCard class="space-y-4">
    <div class="flex items-center justify-between gap-3">
      <div>
        <div class="text-xs font-semibold uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
          Query Settings
        </div>
        <div class="mt-2 text-lg font-semibold text-gray-900 dark:text-white">
          检索参数
        </div>
      </div>
      <BaseButton
        variant="secondary"
        @click="reset"
      >
        重置参数
      </BaseButton>
    </div>

    <div class="grid gap-4 md:grid-cols-2">
      <label class="flex flex-col gap-2 text-sm font-medium text-gray-700 dark:text-dark-200">
        模式
        <BaseSelect
          :model-value="modelValue.mode"
          @update:model-value="update('mode', String($event || 'mix'))"
        >
          <option value="mix">mix</option>
          <option value="hybrid">hybrid</option>
          <option value="local">local</option>
          <option value="global">global</option>
          <option value="naive">naive</option>
          <option value="bypass">bypass</option>
        </BaseSelect>
      </label>

      <label class="flex flex-col gap-2 text-sm font-medium text-gray-700 dark:text-dark-200">
        响应格式
        <BaseSelect
          :model-value="modelValue.response_type"
          @update:model-value="update('response_type', String($event || 'Multiple Paragraphs'))"
        >
          <option value="Multiple Paragraphs">Multiple Paragraphs</option>
          <option value="Single Paragraph">Single Paragraph</option>
          <option value="Bullet Points">Bullet Points</option>
        </BaseSelect>
      </label>

      <label class="flex flex-col gap-2 text-sm font-medium text-gray-700 dark:text-dark-200">
        top_k
        <input
          :value="modelValue.top_k"
          type="number"
          min="1"
          class="pw-input"
          @input="update('top_k', Number(($event.target as HTMLInputElement).value || 40))"
        >
      </label>

      <label class="flex flex-col gap-2 text-sm font-medium text-gray-700 dark:text-dark-200">
        chunk_top_k
        <input
          :value="modelValue.chunk_top_k"
          type="number"
          min="1"
          class="pw-input"
          @input="update('chunk_top_k', Number(($event.target as HTMLInputElement).value || 20))"
        >
      </label>

      <label class="flex flex-col gap-2 text-sm font-medium text-gray-700 dark:text-dark-200">
        max_entity_tokens
        <input
          :value="modelValue.max_entity_tokens"
          type="number"
          min="1"
          class="pw-input"
          @input="update('max_entity_tokens', Number(($event.target as HTMLInputElement).value || 6000))"
        >
      </label>

      <label class="flex flex-col gap-2 text-sm font-medium text-gray-700 dark:text-dark-200">
        max_relation_tokens
        <input
          :value="modelValue.max_relation_tokens"
          type="number"
          min="1"
          class="pw-input"
          @input="update('max_relation_tokens', Number(($event.target as HTMLInputElement).value || 8000))"
        >
      </label>

      <label class="flex flex-col gap-2 text-sm font-medium text-gray-700 dark:text-dark-200 md:col-span-2">
        max_total_tokens
        <input
          :value="modelValue.max_total_tokens"
          type="number"
          min="1"
          class="pw-input"
          @input="update('max_total_tokens', Number(($event.target as HTMLInputElement).value || 30000))"
        >
      </label>
    </div>

    <label class="flex flex-col gap-2 text-sm font-medium text-gray-700 dark:text-dark-200">
      自定义 user prompt
      <textarea
        :value="modelValue.user_prompt"
        rows="4"
        class="pw-input min-h-[120px] resize-y"
        placeholder="可选：覆盖默认 query prompt 模板"
        @input="update('user_prompt', ($event.target as HTMLTextAreaElement).value)"
      />
    </label>

    <div
      v-if="presetPrompts.length"
      class="space-y-2"
    >
      <div class="text-xs font-semibold uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
        Recent User Prompts
      </div>
      <div class="flex flex-wrap gap-2">
        <button
          v-for="prompt in presetPrompts"
          :key="prompt"
          type="button"
          class="rounded-full border border-gray-200 px-3 py-1 text-xs text-gray-600 transition hover:border-primary-300 hover:text-primary-700 dark:border-dark-700 dark:text-dark-300"
          @click="update('user_prompt', prompt)"
        >
          {{ prompt }}
        </button>
      </div>
    </div>

    <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <label class="flex min-w-0 items-start gap-2 rounded-lg bg-gray-50 px-3 py-2 text-sm leading-5 text-gray-700 dark:bg-dark-800/70 dark:text-dark-200">
        <input
          :checked="modelValue.stream"
          type="checkbox"
          class="mt-0.5 shrink-0"
          @change="update('stream', ($event.target as HTMLInputElement).checked)"
        >
        <span class="break-words">stream</span>
      </label>
      <label class="flex min-w-0 items-start gap-2 rounded-lg bg-gray-50 px-3 py-2 text-sm leading-5 text-gray-700 dark:bg-dark-800/70 dark:text-dark-200">
        <input
          :checked="modelValue.only_need_context"
          type="checkbox"
          class="mt-0.5 shrink-0"
          @change="update('only_need_context', ($event.target as HTMLInputElement).checked)"
        >
        <span class="break-words">only_need_context</span>
      </label>
      <label class="flex min-w-0 items-start gap-2 rounded-lg bg-gray-50 px-3 py-2 text-sm leading-5 text-gray-700 dark:bg-dark-800/70 dark:text-dark-200">
        <input
          :checked="modelValue.only_need_prompt"
          type="checkbox"
          class="mt-0.5 shrink-0"
          @change="update('only_need_prompt', ($event.target as HTMLInputElement).checked)"
        >
        <span class="break-words">only_need_prompt</span>
      </label>
      <label class="flex min-w-0 items-start gap-2 rounded-lg bg-gray-50 px-3 py-2 text-sm leading-5 text-gray-700 dark:bg-dark-800/70 dark:text-dark-200">
        <input
          :checked="modelValue.enable_rerank"
          type="checkbox"
          class="mt-0.5 shrink-0"
          @change="update('enable_rerank', ($event.target as HTMLInputElement).checked)"
        >
        <span class="break-words">enable_rerank</span>
      </label>
    </div>
  </SurfaceCard>
</template>

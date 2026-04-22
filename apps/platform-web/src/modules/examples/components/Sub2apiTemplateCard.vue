<script setup lang="ts">
import { computed } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import StatusPill from '@/components/platform/StatusPill.vue'
import Sub2apiTemplatePreview from '@/modules/examples/components/Sub2apiTemplatePreview.vue'
import { getTemplateCurationMeta } from '@/modules/examples/ui-assets-curation'
import { humanizeTemplateName, type Sub2apiTemplateItem } from '@/modules/examples/ui-assets-catalog'

const props = defineProps<{
  item: Sub2apiTemplateItem
}>()

const emit = defineEmits<{
  preview: [item: Sub2apiTemplateItem]
  inspect: [item: Sub2apiTemplateItem]
  code: [item: Sub2apiTemplateItem]
}>()

const curation = computed(() => getTemplateCurationMeta(props.item))

function toneOf(item: Sub2apiTemplateItem) {
  if (item.kind === 'page') {
    return 'info'
  }

  if (item.kind === 'component') {
    return 'success'
  }

  return 'warning'
}
</script>

<template>
  <article class="pw-card p-4">
    <Sub2apiTemplatePreview
      :item="item"
    />

    <div class="mt-4 flex flex-wrap items-center gap-2">
      <StatusPill :tone="toneOf(item)">
        {{ item.sceneLabel }}
      </StatusPill>
      <span
        v-if="curation.isTeamRecommended"
        class="pw-pill-soft pw-pill-soft-warning"
      >
        团队推荐 Top {{ curation.teamRank }}
      </span>
      <span
        v-else-if="curation.isRecommended"
        class="pw-pill-soft pw-pill-soft-success"
      >
        首选模板
      </span>
      <span class="pw-pill-soft pw-pill-soft-neutral">
        {{ item.groupTitle }}
      </span>
      <span
        v-if="item.previewPath"
        class="pw-pill-soft pw-pill-soft-info"
      >
        {{ item.previewPath }}
      </span>
    </div>

    <div class="mt-4">
      <h3 class="text-base font-semibold text-gray-900 dark:text-white">
        {{ humanizeTemplateName(item.name) }}
      </h3>
      <p class="mt-2 text-sm leading-7 text-gray-500 dark:text-dark-300">
        {{ item.summary }}
      </p>
    </div>

    <div
      v-if="curation.teamReason"
      class="pw-panel-warning mt-4 px-4 py-3 text-sm leading-7 text-amber-800 dark:text-amber-200"
    >
      团队建议：{{ curation.teamReason }}
    </div>

    <div class="mt-4 flex flex-wrap gap-2">
      <span
        v-for="tag in item.tags.slice(0, 5)"
        :key="tag"
        class="pw-pill-soft pw-pill-soft-neutral"
      >
        {{ tag }}
      </span>
    </div>

    <div class="mt-4 space-y-2 text-sm text-gray-500 dark:text-dark-300">
      <div>
        <span class="font-semibold text-gray-700 dark:text-dark-100">源码：</span>
        <code class="text-xs">{{ item.shortSource }}</code>
      </div>
      <div>
        <span class="font-semibold text-gray-700 dark:text-dark-100">可借用：</span>
        {{ item.borrow.slice(0, 3).join(' / ') || '以结构和分层方式为主' }}
      </div>
      <div v-if="item.note">
        <span class="font-semibold text-gray-700 dark:text-dark-100">备注：</span>
        {{ item.note }}
      </div>
    </div>

    <div class="mt-5 flex items-center gap-3">
      <BaseButton
        variant="secondary"
        @click="emit('preview', item)"
      >
        <span class="inline-flex items-center gap-2">
          <BaseIcon
            name="eye"
            size="sm"
          />
          页面展示
        </span>
      </BaseButton>

      <BaseButton
        variant="ghost"
        @click="emit('inspect', item)"
      >
        <span class="inline-flex items-center gap-2">
          <BaseIcon
            name="sparkle"
            size="sm"
          />
          源码拆解
        </span>
      </BaseButton>

      <button
        type="button"
        class="pw-btn pw-btn-ghost"
        @click="emit('code', item)"
      >
        查看源码
      </button>
    </div>
  </article>
</template>

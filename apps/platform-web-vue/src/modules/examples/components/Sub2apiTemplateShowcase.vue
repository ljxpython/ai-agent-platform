<script setup lang="ts">
import { computed, defineAsyncComponent } from 'vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import Sub2apiTemplateCard from '@/modules/examples/components/Sub2apiTemplateCard.vue'
import { curatedTemplatesByMode, recommendedTemplatesByMode } from '@/modules/examples/ui-assets-curation'
import { type TemplateMode } from '@/modules/examples/ui-assets-catalog'
import { useSub2apiTemplateDialog } from '@/modules/examples/useSub2apiTemplateDialog'

const Sub2apiTemplateDialog = defineAsyncComponent(
  () => import('@/modules/examples/components/Sub2apiTemplateDialog.vue')
)

const props = withDefaults(
  defineProps<{
    mode: TemplateMode
    title: string
    description: string
    actionTo: string
    actionLabel: string
    limit?: number
  }>(),
  {
    limit: 3
  }
)

const totalCount = computed(() => curatedTemplatesByMode[props.mode].length)
const {
  selectedTemplate,
  selectedTemplateDetail,
  detailLoading,
  initialTab,
  relatedItems,
  openTemplate,
  closeTemplate
} = useSub2apiTemplateDialog()

const featuredItems = computed(() => recommendedTemplatesByMode[props.mode].slice(0, props.limit))
</script>

<template>
  <section class="pw-card p-6">
    <div class="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <div class="pw-page-eyebrow">
          Featured Templates
        </div>
        <h2 class="mt-1 text-xl font-semibold text-gray-900 dark:text-white">
          {{ title }}
        </h2>
        <p class="mt-2 max-w-4xl text-sm leading-7 text-gray-500 dark:text-dark-300">
          {{ description }}
        </p>
      </div>

      <div class="flex items-center gap-3">
        <div class="rounded-full border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-600 dark:border-dark-700 dark:bg-dark-900 dark:text-dark-200">
          {{ featuredItems.length }} 个精选 / {{ totalCount }} 个总模板
        </div>

        <router-link
          :to="actionTo"
          class="pw-btn pw-btn-secondary inline-flex items-center gap-2"
        >
          <BaseIcon
            name="chevron-right"
            size="sm"
          />
          {{ actionLabel }}
        </router-link>
      </div>
    </div>

    <div class="mt-6 grid gap-4 xl:grid-cols-3">
      <Sub2apiTemplateCard
        v-for="item in featuredItems"
        :key="item.id"
        :item="item"
        @preview="openTemplate(item, 'preview')"
        @inspect="openTemplate(item, 'overview')"
        @code="openTemplate(item, 'code')"
      />
    </div>

    <Sub2apiTemplateDialog
      :show="!!selectedTemplate"
      :item="selectedTemplate"
      :detail="selectedTemplateDetail"
      :initial-tab="initialTab"
      :related-items="relatedItems"
      :loading="detailLoading"
      @close="closeTemplate"
      @open-related="openTemplate"
    />
  </section>
</template>

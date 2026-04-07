<script setup lang="ts">
import { defineAsyncComponent } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import StatusPill from '@/components/platform/StatusPill.vue'
import { teamRecommendedTemplates } from '@/modules/examples/ui-assets-curation'
import {
  humanizeTemplateName,
  type Sub2apiTemplateItem,
  type TemplateMode
} from '@/modules/examples/ui-assets-catalog'
import { useSub2apiTemplateDialog } from '@/modules/examples/useSub2apiTemplateDialog'

const Sub2apiTemplateDialog = defineAsyncComponent(
  () => import('@/modules/examples/components/Sub2apiTemplateDialog.vue')
)

const {
  selectedTemplate,
  selectedTemplateDetail,
  detailLoading,
  initialTab,
  relatedItems,
  openTemplate,
  closeTemplate
} = useSub2apiTemplateDialog()

function modeLabel(mode: TemplateMode) {
  if (mode === 'pages') {
    return '页面模板'
  }

  if (mode === 'components') {
    return '组件模板'
  }

  return '工程模板'
}

function toneOf(item: Sub2apiTemplateItem) {
  if (item.mode === 'pages') {
    return 'info'
  }

  if (item.mode === 'components') {
    return 'success'
  }

  return 'warning'
}
</script>

<template>
  <section class="pw-card p-5">
    <div class="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <div class="pw-page-eyebrow">
          Team Recommended
        </div>
        <h2 class="mt-1 text-xl font-semibold text-gray-900 dark:text-white">
          团队推荐 Top 10
        </h2>
        <p class="mt-2 max-w-5xl text-sm leading-7 text-gray-500 dark:text-dark-300">
          这 10 个模板是整个资源库里最应该先吃透的那批。后续做后台壳层、列表页、弹窗和表格工程逻辑时，优先从这里开工，能少走很多弯路。
        </p>
      </div>

      <div class="rounded-full border border-amber-200 bg-amber-50 px-3.5 py-1.5 text-sm font-medium text-amber-700 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-300">
        固定锚点 10 个
      </div>
    </div>

    <div class="mt-6 grid gap-4 xl:grid-cols-2">
      <article
        v-for="entry in teamRecommendedTemplates"
        :id="entry.item.id"
        :key="entry.item.id"
        class="pw-panel-lg"
      >
        <div class="flex items-start justify-between gap-4">
          <div>
            <div class="inline-flex items-center gap-2 rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-amber-700 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-300">
              Top {{ entry.rank }}
            </div>
            <h3 class="mt-4 text-lg font-semibold text-gray-900 dark:text-white">
              {{ humanizeTemplateName(entry.item.name) }}
            </h3>
          </div>

          <StatusPill :tone="toneOf(entry.item)">
            {{ modeLabel(entry.item.mode) }}
          </StatusPill>
        </div>

        <p class="mt-3 text-sm leading-7 text-gray-600 dark:text-dark-300">
          {{ entry.reason }}
        </p>

        <div class="pw-panel-muted mt-4">
          <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-500">
            源码位置
          </div>
          <code class="mt-2 block break-all text-xs text-gray-700 dark:text-dark-100">{{ entry.item.shortSource }}</code>
          <p class="mt-3 text-sm leading-7 text-gray-500 dark:text-dark-300">
            {{ entry.item.summary }}
          </p>
        </div>

        <div class="mt-5 flex flex-wrap items-center gap-3">
          <BaseButton
            variant="secondary"
            @click="openTemplate(entry.item, 'preview')"
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
            @click="openTemplate(entry.item, 'overview')"
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
            @click="openTemplate(entry.item, 'code')"
          >
            查看源码
          </button>
        </div>
      </article>
    </div>

    <Sub2apiTemplateDialog
      :show="Boolean(selectedTemplate)"
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

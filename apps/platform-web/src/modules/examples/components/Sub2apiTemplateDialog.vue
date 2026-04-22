<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseDialog from '@/components/base/BaseDialog.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import StatusPill from '@/components/platform/StatusPill.vue'
import Sub2apiTemplatePreview from '@/modules/examples/components/Sub2apiTemplatePreview.vue'
import { getTemplateCurationMeta } from '@/modules/examples/ui-assets-curation'
import type { TemplateDetailTab } from '@/modules/examples/useSub2apiTemplateDialog'
import { useUiStore } from '@/stores/ui'
import {
  humanizeTemplateName,
  type Sub2apiTemplateDetail,
  type Sub2apiTemplateItem
} from '@/modules/examples/ui-assets-catalog'

const props = defineProps<{
  show: boolean
  item: Sub2apiTemplateItem | null
  detail: Sub2apiTemplateDetail | null
  relatedItems: Sub2apiTemplateItem[]
  loading: boolean
  initialTab: TemplateDetailTab
}>()

const emit = defineEmits<{
  close: []
  openRelated: [item: Sub2apiTemplateItem, tab?: TemplateDetailTab]
}>()

const uiStore = useUiStore()
const activeTab = ref<TemplateDetailTab>('preview')

const availableTabs = computed(() => {
  const tabs: Array<{ key: TemplateDetailTab; label: string }> = [
    { key: 'preview', label: '页面展示' },
    { key: 'overview', label: '源码拆解' }
  ]

  if (props.detail?.blocks.template) {
    tabs.push({ key: 'template', label: 'Template' })
  }

  if (props.detail?.blocks.script) {
    tabs.push({ key: 'script', label: 'Script' })
  }

  if (props.detail?.blocks.style) {
    tabs.push({ key: 'style', label: 'Style' })
  }

  tabs.push({ key: 'code', label: 'Raw Code' })

  return tabs
})

const activeCode = computed(() => {
  if (!props.detail) {
    return ''
  }

  if (activeTab.value === 'template') {
    return props.detail.blocks.template || ''
  }

  if (activeTab.value === 'script') {
    return props.detail.blocks.script || ''
  }

  if (activeTab.value === 'style') {
    return props.detail.blocks.style || ''
  }

  return props.detail.code
})

const curation = computed(() => (props.item ? getTemplateCurationMeta(props.item) : null))

watch(
  () => [props.item?.id, props.initialTab],
  () => {
    activeTab.value = props.initialTab
  }
)

watch(
  availableTabs,
  (tabs) => {
    if (!tabs.some((tab) => tab.key === activeTab.value)) {
      activeTab.value = tabs[0]?.key || 'preview'
    }
  },
  { immediate: true }
)

function closeDialog() {
  emit('close')
}

function toneOf(item: Sub2apiTemplateItem | null) {
  if (!item) {
    return 'neutral'
  }

  if (item.kind === 'page') {
    return 'info'
  }

  if (item.kind === 'component') {
    return 'success'
  }

  return 'warning'
}

async function copyValue(value: string, message: string) {
  try {
    await navigator.clipboard.writeText(value)
    uiStore.pushToast({
      type: 'success',
      title: '已复制',
      message
    })
  } catch {
    uiStore.pushToast({
      type: 'warning',
      title: '复制失败',
      message: '当前环境不支持写入剪贴板，请手动复制。'
    })
  }
}
</script>

<template>
  <BaseDialog
    :show="show"
    :title="item ? humanizeTemplateName(item.name) : '模板详情'"
    width="full"
    @close="closeDialog"
  >
    <template v-if="item">
      <div class="grid gap-5 xl:grid-cols-[320px_minmax(0,1fr)]">
        <aside class="space-y-4">
          <div class="pw-panel-muted">
            <div class="flex flex-wrap gap-2">
              <StatusPill :tone="toneOf(item)">
                {{ item.sceneLabel }}
              </StatusPill>
              <span
                v-if="curation?.isTeamRecommended"
                class="pw-pill-soft pw-pill-soft-warning"
              >
                团队推荐 Top {{ curation.teamRank }}
              </span>
              <span
                v-else-if="curation?.isRecommended"
                class="pw-pill-soft pw-pill-soft-success"
              >
                首选模板
              </span>
              <span class="pw-pill px-3 py-1 text-xs">
                {{ item.groupTitle }}
              </span>
            </div>

            <div class="mt-4 space-y-3 text-sm text-gray-500 dark:text-dark-300">
              <div>
                <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-500">
                  摘要
                </div>
                <p class="mt-2 leading-7">
                  {{ item.summary }}
                </p>
              </div>

              <div>
                <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-500">
                  源码路径
                </div>
                <code class="mt-2 block break-all text-xs text-gray-700 dark:text-dark-100">{{ item.source }}</code>
              </div>

              <div v-if="item.previewPath">
                <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-500">
                  原始路由
                </div>
                <code class="mt-2 block text-xs text-gray-700 dark:text-dark-100">{{ item.previewPath }}</code>
              </div>

              <div v-if="detail">
                <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-500">
                  代码规模
                </div>
                <div class="mt-2 text-sm font-medium text-gray-900 dark:text-white">
                  {{ detail.lineCount }} 行
                </div>
              </div>

              <div v-if="curation?.isRecommended">
                <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-500">
                  推荐层级
                </div>
                <div class="mt-2 text-sm font-medium text-gray-900 dark:text-white">
                  {{ curation.isTeamRecommended ? `团队推荐 Top ${curation.teamRank}` : '默认首选模板' }}
                </div>
              </div>
            </div>

            <div class="mt-4 flex flex-wrap gap-3">
              <BaseButton
                variant="secondary"
                @click="activeTab = 'preview'"
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
                @click="activeTab = 'overview'"
              >
                <span class="inline-flex items-center gap-2">
                  <BaseIcon
                    name="sparkle"
                    size="sm"
                  />
                  源码拆解
                </span>
              </BaseButton>

              <BaseButton
                variant="ghost"
                @click="activeTab = 'code'"
              >
                <span class="inline-flex items-center gap-2">
                  <BaseIcon
                    name="copy"
                    size="sm"
                  />
                  查看源码
                </span>
              </BaseButton>

              <BaseButton
                variant="ghost"
                @click="copyValue(item.source, '源码路径已经写进剪贴板。')"
              >
                <span class="inline-flex items-center gap-2">
                  <BaseIcon
                    name="copy"
                    size="sm"
                  />
                  复制源码路径
                </span>
              </BaseButton>

              <BaseButton
                variant="ghost"
                @click="copyValue(item.shortSource, '相对源码路径已经复制。')"
              >
                复制相对路径
              </BaseButton>
            </div>
          </div>

          <div class="pw-panel">
            <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-500">
              推荐借用
            </div>
            <div class="mt-3 flex flex-wrap gap-2">
              <span
                v-for="borrow in detail?.borrow || item.borrow"
                :key="borrow"
                class="pw-pill-soft pw-pill-soft-neutral"
              >
                {{ borrow }}
              </span>
            </div>
          </div>

          <div
            v-if="curation?.teamReason"
            class="pw-panel-warning"
          >
            <div class="text-xs font-semibold uppercase tracking-[0.16em] text-amber-600 dark:text-amber-300">
              团队建议
            </div>
            <p class="mt-3 text-sm leading-7 text-amber-800 dark:text-amber-100">
              {{ curation.teamReason }}
            </p>
          </div>

          <div class="pw-panel">
            <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-500">
              相关模板
            </div>
            <div class="mt-3 space-y-2">
              <button
                v-for="related in relatedItems"
                :key="related.id"
                type="button"
                class="flex w-full items-center justify-between rounded-2xl border border-gray-100 bg-gray-50/80 px-3 py-3 text-left text-sm text-gray-700 transition hover:border-primary-200 hover:bg-primary-50/70 dark:border-dark-800 dark:bg-dark-900/70 dark:text-dark-200 dark:hover:border-primary-900/40 dark:hover:bg-primary-950/20"
                @click="emit('openRelated', related, activeTab)"
              >
                <span class="min-w-0 truncate">{{ humanizeTemplateName(related.name) }}</span>
                <BaseIcon
                  name="chevron-right"
                  size="sm"
                />
              </button>
              <div
                v-if="relatedItems.length === 0"
                class="rounded-2xl border border-dashed border-gray-200 px-3 py-4 text-sm text-gray-500 dark:border-dark-700 dark:text-dark-300"
              >
                当前分组下没有更多模板。
              </div>
            </div>
          </div>
        </aside>

        <section class="min-w-0">
          <div class="pw-panel">
            <div class="flex flex-wrap gap-2">
              <button
                v-for="tab in availableTabs"
                :key="tab.key"
                type="button"
                class="pw-table-tool-button"
                :class="activeTab === tab.key ? 'pw-pagination-page-active' : ''"
                @click="activeTab = tab.key"
              >
                {{ tab.label }}
              </button>
            </div>

            <div
              v-if="loading"
              class="mt-4 rounded-2xl border border-dashed border-gray-200 px-4 py-10 text-sm text-gray-500 dark:border-dark-700 dark:text-dark-300"
            >
              正在读取模板源码和结构块...
            </div>

            <template v-else-if="activeTab === 'preview'">
              <div class="mt-4 space-y-4">
                <div class="pw-panel-muted">
                  <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-500">
                    Visual Preview
                  </div>
                  <p class="mt-3 text-sm leading-7 text-gray-600 dark:text-dark-300">
                    这是基于模板标签、路径和场景规则生成的高保真可视化展示，不是真实运行上游页面，但足够让你快速判断它更像列表页、看板页、认证页、弹窗组件还是工程骨架。
                  </p>
                </div>

                <Sub2apiTemplatePreview
                  :item="item"
                  size="expanded"
                />
              </div>
            </template>

            <template v-else-if="activeTab === 'overview' && detail">
              <div class="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
                <div class="pw-panel-muted">
                  <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-500">
                    结构说明
                  </div>
                  <div class="mt-3 space-y-4 text-sm leading-7 text-gray-600 dark:text-dark-300">
                    <p>
                      这不是单纯给你看文件名，而是把上游模板按结构拆给你看。后续开发者要借用时，优先拿壳层、工具栏、内容区和状态弹窗，不要整页粗暴复制。
                    </p>
                    <p>
                      当前模板命中的标签：
                      <span class="font-semibold text-gray-900 dark:text-white">{{ detail.tags.join(' / ') }}</span>
                    </p>
                  </div>
                </div>

                <div class="pw-panel-muted">
                  <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-500">
                    依赖导入
                  </div>
                  <div class="mt-3 space-y-2">
                    <code
                      v-for="importPath in detail.imports.slice(0, 12)"
                      :key="importPath"
                      class="block rounded-xl border border-gray-200 bg-white px-3 py-2 text-xs text-gray-700 dark:border-dark-700 dark:bg-dark-900 dark:text-dark-100"
                    >
                      {{ importPath }}
                    </code>
                    <div
                      v-if="detail.imports.length === 0"
                      class="rounded-xl border border-dashed border-gray-200 px-3 py-4 text-sm text-gray-500 dark:border-dark-700 dark:text-dark-300"
                    >
                      这个模板没有明显的 import 依赖，或者导入方式比较简单。
                    </div>
                  </div>
                </div>
              </div>
            </template>

            <template v-else>
              <pre class="mt-4 max-h-[68vh] overflow-auto rounded-2xl bg-slate-950 p-4 text-xs leading-6 text-slate-100"><code>{{ activeCode }}</code></pre>
            </template>
          </div>
        </section>
      </div>
    </template>
  </BaseDialog>
</template>

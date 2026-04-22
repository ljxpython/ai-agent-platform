<script setup lang="ts">
import { computed, defineAsyncComponent, ref, watch } from 'vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import SearchInput from '@/components/platform/SearchInput.vue'
import Sub2apiTemplateCard from '@/modules/examples/components/Sub2apiTemplateCard.vue'
import {
  curatedTemplatesByMode,
  recommendedTemplatesByMode,
  sortTemplatesByRecommendation,
  teamRecommendedTemplatesByMode,
  templateExplorerLayers,
  templateSceneStats,
  templateScenesByMode,
  type TemplateExplorerLayer
} from '@/modules/examples/ui-assets-curation'
import {
  humanizeTemplateName,
  sub2apiTemplateGroups,
  type Sub2apiTemplateGroup,
  templateModeOptions,
  type TemplateMode
} from '@/modules/examples/ui-assets-catalog'
import { useSub2apiTemplateDialog } from '@/modules/examples/useSub2apiTemplateDialog'

const Sub2apiTemplateDialog = defineAsyncComponent(
  () => import('@/modules/examples/components/Sub2apiTemplateDialog.vue')
)

const props = withDefaults(
  defineProps<{
    mode: TemplateMode
    eyebrow?: string
    title?: string
    description?: string
    searchPlaceholder?: string
  }>(),
  {
    eyebrow: 'Template Gallery',
    title: '',
    description: '',
    searchPlaceholder: '搜索模板名、路径、路由、标签'
  }
)

const searchQuery = ref('')
const activeGroupKey = ref<'all' | string>('all')
const activeLayer = ref<TemplateExplorerLayer>('recommended')
const {
  selectedTemplate,
  selectedTemplateDetail,
  detailLoading,
  initialTab,
  relatedItems,
  openTemplate,
  closeTemplate
} = useSub2apiTemplateDialog()

const currentModeOption = computed(() =>
  templateModeOptions.find((item) => item.key === props.mode)
)

const currentLayerOption = computed(() =>
  templateExplorerLayers.find((item) => item.key === activeLayer.value)
)

const activeGroups = computed(() => sub2apiTemplateGroups[props.mode])
const libraryItems = computed(() => sortTemplatesByRecommendation(curatedTemplatesByMode[props.mode]))
const recommendedItems = computed(() =>
  sortTemplatesByRecommendation(recommendedTemplatesByMode[props.mode])
)
const teamRecommendedItems = computed(() => teamRecommendedTemplatesByMode[props.mode])
const sceneGroups = computed(() => templateScenesByMode[props.mode])

const totalActiveCount = computed(() =>
  libraryItems.value.length
)

const libraryItemIdSet = computed(() => new Set(libraryItems.value.map((item) => item.id)))

const libraryGroups = computed<Sub2apiTemplateGroup[]>(() =>
  activeGroups.value
    .map((group) => ({
      ...group,
      items: sortTemplatesByRecommendation(
        group.items.filter((item) => libraryItemIdSet.value.has(item.id))
      )
    }))
    .filter((group) => group.items.length > 0)
)

const groupOptions = computed(() => [
  { key: 'all', label: '全部分组' },
  ...libraryGroups.value.map((group) => ({
    key: group.key,
    label: `${group.title} · ${group.items.length}`
  }))
])

const filteredGroups = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()

  return libraryGroups.value
    .filter((group) => activeGroupKey.value === 'all' || group.key === activeGroupKey.value)
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => {
        if (!query) {
          return true
        }

        return [
          item.name,
          item.groupTitle,
          item.shortSource,
          item.summary,
          item.previewPath || '',
          item.tags.join(' '),
          item.borrow.join(' ')
        ]
          .join(' ')
          .toLowerCase()
          .includes(query)
      })
    }))
    .filter((group) => group.items.length > 0)
})

const filteredCount = computed(() =>
  filteredGroups.value.reduce((total, group) => total + group.items.length, 0)
)

const currentDisplayLabel = computed(() => {
  if (activeLayer.value === 'recommended') {
    return `当前展示 ${recommendedItems.value.length} / ${totalActiveCount.value} 个首选模板，其中 ${teamRecommendedItems.value.length} 个已列为团队推荐`
  }

  if (activeLayer.value === 'scenes') {
    return `当前展示 ${templateSceneStats[props.mode].sceneCount} 个场景 / ${templateSceneStats[props.mode].templateCount} 个代表模板`
  }

  return `当前展示 ${filteredCount.value} / ${totalActiveCount.value} 个去重模板`
})

const currentDisplayHint = computed(() => {
  if (activeLayer.value === 'recommended') {
    return '这层是默认入口，已经把高频重复和同质化模板压缩成一组可直接开工的代表模板。'
  }

  if (activeLayer.value === 'scenes') {
    return '不确定先借页面骨架、列表体系还是工程接线时，就从场景模板看，按任务类型选。'
  }

  return '这里只保留去重后的模板库，继续支持搜索、分组和可视化卡片，不再把整库源码档案直接摊给你。'
})

watch(
  () => props.mode,
  () => {
    searchQuery.value = ''
    activeGroupKey.value = 'all'
    activeLayer.value = 'recommended'
    closeTemplate()
  }
)
</script>

<template>
  <article class="pw-card p-5">
    <div class="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <div class="pw-page-eyebrow">
          {{ eyebrow }}
        </div>
        <h2
          v-if="title"
          class="mt-1 text-xl font-semibold text-gray-900 dark:text-white"
        >
          {{ title }}
        </h2>
        <p
          v-if="description || currentModeOption?.description"
          class="mt-2 max-w-4xl text-sm leading-7 text-gray-500 dark:text-dark-300"
        >
          {{ description || currentModeOption?.description }}
        </p>
      </div>

      <div
        v-if="activeLayer === 'library'"
        class="w-full lg:w-[320px]"
      >
        <SearchInput
          v-model="searchQuery"
          :placeholder="searchPlaceholder"
        />
      </div>
    </div>

    <div class="mt-6 grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div class="pw-panel-muted-lg">
        <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-500">
          当前模式
        </div>
        <div class="mt-2 text-lg font-semibold text-gray-900 dark:text-white">
          {{ currentModeOption?.label }}
        </div>
        <p class="mt-2 text-sm leading-7 text-gray-500 dark:text-dark-300">
          默认先看推荐模板，再按场景找，最后再进模板库补细节。别一上来就把一整坨源码卡片翻到底。
        </p>
      </div>

      <div class="pw-panel-muted-lg">
        <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-500">
          当前层级
        </div>
        <div class="mt-2 text-lg font-semibold text-gray-900 dark:text-white">
          {{ currentLayerOption?.label }}
        </div>
        <p class="mt-2 text-sm leading-7 text-gray-500 dark:text-dark-300">
          {{ currentLayerOption?.description }}
        </p>
      </div>
    </div>

    <div class="mt-6 flex flex-wrap gap-2">
      <button
        v-for="layer in templateExplorerLayers"
        :key="layer.key"
        type="button"
        class="pw-table-tool-button"
        :class="activeLayer === layer.key ? 'pw-pagination-page-active' : ''"
        @click="activeLayer = layer.key"
      >
        {{ layer.label }}
      </button>
    </div>

    <div class="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div class="pw-panel-muted-lg">
        <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-500">
          展示范围
        </div>
        <div class="mt-2 text-lg font-semibold text-gray-900 dark:text-white">
          {{ currentDisplayLabel }}
        </div>
        <p class="mt-2 text-sm leading-7 text-gray-500 dark:text-dark-300">
          {{ currentDisplayHint }}
        </p>
      </div>

      <div class="pw-panel-muted-lg">
        <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-500">
          选型顺序
        </div>
        <div class="mt-2 space-y-2 text-sm leading-7 text-gray-500 dark:text-dark-300">
          <div>1. 先从推荐模板选能直接开工的首选骨架。</div>
          <div>2. 不确定时切到场景模板，按任务类型缩小范围。</div>
          <div>3. 还要横向对比时，再进模板库看去重后的完整集合。</div>
        </div>
      </div>
    </div>

    <template v-if="activeLayer === 'recommended'">
      <div class="mt-6 grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div class="pw-panel-lg">
          <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-500">
            Default Picks
          </div>
          <div class="mt-2 text-xl font-semibold text-gray-900 dark:text-white">
            这批就是默认首选模板
          </div>
          <p class="mt-2 max-w-4xl text-sm leading-7 text-gray-500 dark:text-dark-300">
            这里不是平均摊给每个目录几个模板，而是按实际开发最常复用的壳层、列表、弹窗、图表和工程骨架压出来的首选集合。先把这批吃透，开发效率会比翻完整档案高得多。
          </p>
        </div>

        <div class="pw-panel-info p-5">
          <div class="text-xs font-semibold uppercase tracking-[0.16em] text-primary-500 dark:text-primary-300">
            使用建议
          </div>
          <div class="mt-2 text-lg font-semibold text-gray-900 dark:text-white">
            默认别跳过这层
          </div>
          <p class="mt-2 text-sm leading-7 text-gray-600 dark:text-dark-300">
            如果这层已经能满足大部分选型，就不要再回头翻更大的模板集合。先把首选骨架确定掉，后面就顺很多。
          </p>
          <div class="mt-4">
            <button
              type="button"
              class="pw-btn pw-btn-secondary inline-flex items-center gap-2"
              @click="activeLayer = 'scenes'"
            >
              <BaseIcon
                name="sparkle"
                size="sm"
              />
              查看场景模板
            </button>
          </div>
        </div>
      </div>

      <div
        v-if="teamRecommendedItems.length > 0"
        class="pw-panel-warning mt-5 p-5"
      >
        <div class="text-xs font-semibold uppercase tracking-[0.16em] text-amber-600 dark:text-amber-300">
          Team Picks
        </div>
        <div class="mt-2 text-lg font-semibold text-gray-900 dark:text-white">
          当前分类钉死的团队推荐
        </div>
        <p class="mt-2 text-sm leading-7 text-amber-900/80 dark:text-amber-100">
          这些模板在当前分类里优先级最高。先从它们开工，再去看同层其他首选模板，开发者不容易选岔。
        </p>
        <div class="mt-4 flex flex-wrap gap-2">
          <router-link
            v-for="entry in teamRecommendedItems"
            :key="entry.item.id"
            :to="{ name: 'workspace-resources-top-picks', hash: `#${entry.item.id}` }"
            class="inline-flex items-center gap-2 rounded-xl border border-amber-200 bg-white px-3 py-2 text-sm font-medium text-amber-700 transition hover:border-amber-300 hover:bg-amber-50 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-200 dark:hover:bg-amber-950/35"
          >
            <span class="pw-pill-count bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-200">
              Top {{ entry.rank }}
            </span>
            <span>{{ humanizeTemplateName(entry.item.name) }}</span>
          </router-link>
        </div>
      </div>

      <div class="mt-6 grid gap-4 xl:grid-cols-2 2xl:grid-cols-3">
        <Sub2apiTemplateCard
          v-for="item in recommendedItems"
          :key="item.id"
          :item="item"
          @preview="openTemplate(item, 'preview')"
          @inspect="openTemplate(item, 'overview')"
          @code="openTemplate(item, 'code')"
        />
      </div>
    </template>

    <template v-else-if="activeLayer === 'scenes'">
      <div class="mt-6 space-y-5">
        <article
          v-for="scene in sceneGroups"
          :key="scene.key"
          class="pw-panel-muted-lg"
        >
          <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-500">
                Scene Template
              </div>
              <div class="mt-1 text-lg font-semibold text-gray-900 dark:text-white">
                {{ scene.title }}
              </div>
              <p class="mt-2 max-w-4xl text-sm leading-7 text-gray-500 dark:text-dark-300">
                {{ scene.description }}
              </p>
            </div>

            <div class="pw-pill px-3 py-1.5 text-sm">
              {{ scene.items.length }} 个代表模板
            </div>
          </div>

          <div class="pw-panel mt-4 px-4 py-4 text-sm leading-7 text-gray-600 dark:text-dark-300">
            {{ scene.guidance }}
          </div>

          <div class="mt-5 grid gap-4 xl:grid-cols-2 2xl:grid-cols-3">
            <Sub2apiTemplateCard
              v-for="item in scene.items"
              :key="item.id"
              :item="item"
              @preview="openTemplate(item, 'preview')"
              @inspect="openTemplate(item, 'overview')"
              @code="openTemplate(item, 'code')"
            />
          </div>
        </article>
      </div>
    </template>

    <template v-else>
      <div class="mt-6 flex flex-wrap items-center gap-3">
        <div class="w-full lg:w-[320px]">
          <SearchInput
            v-model="searchQuery"
            :placeholder="searchPlaceholder"
          />
        </div>

        <button
          v-for="group in groupOptions"
          :key="group.key"
          type="button"
          class="pw-table-tool-button"
          :class="activeGroupKey === group.key ? 'pw-pagination-page-active' : ''"
          @click="activeGroupKey = group.key"
        >
          {{ group.label }}
        </button>
      </div>

      <div
        v-if="filteredGroups.length === 0"
        class="mt-6 rounded-2xl border border-dashed border-gray-200 bg-gray-50 px-5 py-10 text-center text-sm text-gray-500 dark:border-dark-700 dark:bg-dark-900/40 dark:text-dark-300"
      >
        没有匹配到模板，换个关键词或者切换分组看看。
      </div>

      <div
        v-else
        class="mt-6 space-y-5"
      >
        <article
          v-for="group in filteredGroups"
          :key="group.key"
          class="pw-panel-muted-lg"
        >
          <div class="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <div class="text-lg font-semibold text-gray-900 dark:text-white">
                {{ group.title }}
              </div>
              <p class="mt-2 max-w-4xl text-sm leading-7 text-gray-500 dark:text-dark-300">
                {{ group.description }}
              </p>
            </div>

            <div class="pw-pill px-3 py-1.5 text-sm">
              <BaseIcon
                name="folder"
                size="sm"
              />
              {{ group.items.length }} 个模板
            </div>
          </div>

          <div class="mt-5 grid gap-4 xl:grid-cols-2 2xl:grid-cols-3">
            <Sub2apiTemplateCard
              v-for="item in group.items"
              :key="item.id"
              :item="item"
              @preview="openTemplate(item, 'preview')"
              @inspect="openTemplate(item, 'overview')"
              @code="openTemplate(item, 'code')"
            />
          </div>
        </article>
      </div>
    </template>

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
  </article>
</template>

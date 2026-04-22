<script setup lang="ts">
import PageHeader from '@/components/layout/PageHeader.vue'
import MetricCard from '@/components/platform/MetricCard.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import Sub2apiTemplateGallery from '@/modules/examples/components/Sub2apiTemplateGallery.vue'
import {
  curatedTemplateStats,
  recommendedTemplateStats,
  teamRecommendedStats,
  templateSceneStats
} from '@/modules/examples/ui-assets-curation'

const stats = [
  {
    label: '去重模板数',
    value: curatedTemplateStats.pages,
    hint: '只保留推荐模板和场景模板去重后的页面集合，避免重复页面来回出现。',
    icon: 'folder',
    tone: 'primary'
  },
  {
    label: '推荐模板数',
    value: recommendedTemplateStats.pages,
    hint: '默认优先展示这批首选页面骨架，减少同类页面反复横跳。',
    icon: 'overview',
    tone: 'success'
  },
  {
    label: '团队推荐',
    value: teamRecommendedStats.pages,
    hint: '页面分类里被固定钉住的模板数量。',
    icon: 'check',
    tone: 'primary'
  },
  {
    label: '场景模板集',
    value: templateSceneStats.pages.sceneCount,
    hint: '后台列表、总览监控、认证引导、用户工作台这些场景已经单独收口。',
    icon: 'sparkle',
    tone: 'warning'
  }
] as const
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Resources"
      title="页面模板"
      description="这里只放页面级模板。后续开发者要找完整页面骨架、列表页节奏、看板页结构和认证页组织方式，就在这挑。"
    />

    <StateBanner
      title="页面模板已收敛为三层资源页"
      description="默认先看推荐模板，再按场景找页面骨架，最后只保留一个去重后的模板库做横向比较。重复页面不再直接铺满页面。"
      variant="info"
    />

    <div class="grid gap-4 xl:grid-cols-4">
      <MetricCard
        v-for="item in stats"
        :key="item.label"
        :label="item.label"
        :value="item.value"
        :hint="item.hint"
        :icon="item.icon"
        :tone="item.tone"
      />
    </div>

    <Sub2apiTemplateGallery
      mode="pages"
      eyebrow="Page Templates"
      title="Sub2api 页面模板库"
      description="后台管理页、运维监控页、认证页、公开页和用户工作台模板都在这里，但现在只展示推荐模板、场景模板和去重后的页面模板库，不再让人直接陷进整库 views。"
      search-placeholder="搜索页面名、源码路径或原始路由"
    />
  </section>
</template>

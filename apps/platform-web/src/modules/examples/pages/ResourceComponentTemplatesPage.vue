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
    value: curatedTemplateStats.components,
    hint: '组件层只保留去重后的可视化模板，避免同一类壳层和表格卡片反复出现。',
    icon: 'users',
    tone: 'success'
  },
  {
    label: '推荐模板数',
    value: recommendedTemplateStats.components,
    hint: '默认先给出壳层、列表体系、弹层和图表这些最值得直接借的组件骨架。',
    icon: 'folder',
    tone: 'primary'
  },
  {
    label: '团队推荐',
    value: teamRecommendedStats.components,
    hint: '组件分类里固定钉住的优先模板数量。',
    icon: 'check',
    tone: 'primary'
  },
  {
    label: '场景模板集',
    value: templateSceneStats.components.sceneCount,
    hint: '壳层系统区、列表工具栏、弹窗编辑流、图表区和认证安全组件都按场景收好了。',
    icon: 'sparkle',
    tone: 'warning'
  }
] as const
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Resources"
      title="组件模板"
      description="这里只放组件级模板。后续开发者要借 DataTable、Dialog、Pagination、领域弹窗、图表或布局壳，不要再混进页面模板里找。"
    />

    <StateBanner
      title="组件模板已收敛为三层资源页"
      description="组件模板数量最多，所以现在默认只看推荐模板、场景模板和去重后的模板库，整库源码档案不再直接铺开。"
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
      mode="components"
      eyebrow="Component Templates"
      title="Sub2api 组件模板库"
      description="通用组件、布局壳、图表、账号领域组件、用户领域组件和各类管理弹窗都在这里，但现在只保留推荐模板、场景模板和去重后的组件模板库，避免开发者面对一墙同质化卡片。"
      search-placeholder="搜索组件名、源码路径或可借用点"
    />
  </section>
</template>

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
    value: curatedTemplateStats.engineering,
    hint: '工程层现在只展示去重后的骨架模板，不再把整库辅助文件全部摊开。',
    icon: 'runtime',
    tone: 'warning'
  },
  {
    label: '推荐模板数',
    value: recommendedTemplateStats.engineering,
    hint: 'API client、状态收口、路由接线和 i18n 这批最值钱的工程骨架已被优先抽出。',
    icon: 'folder',
    tone: 'primary'
  },
  {
    label: '团队推荐',
    value: teamRecommendedStats.engineering,
    hint: '工程分类里固定钉住的优先模板数量。',
    icon: 'check',
    tone: 'primary'
  },
  {
    label: '场景模板集',
    value: templateSceneStats.engineering.sceneCount,
    hint: '接口边界、列表状态、路由导航、启动与国际化都已经按场景分好了。',
    icon: 'sparkle',
    tone: 'success'
  }
] as const
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Resources"
      title="工程模板"
      description="这里只放工程层模板。后续开发者要学 API 封装、状态管理、路由组织、composable 写法和 i18n 接线，就在这边看。"
    />

    <StateBanner
      title="工程模板已收敛为三层资源页"
      description="工程层最容易被全量文件淹没，所以现在默认先看推荐模板和场景模板，最后只保留一个去重后的模板库做横向比较。"
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
      mode="engineering"
      eyebrow="Engineering Templates"
      title="Sub2api 工程模板库"
      description="接口、store、router、composable、i18n、styles、utils 这些工程模板仍然都在，但现在只展示最值得借的骨架、场景集和去重后的工程模板库。"
      search-placeholder="搜索文件名、路径、工程标签或借用点"
    />
  </section>
</template>

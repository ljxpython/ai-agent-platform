<script setup lang="ts">
import PageHeader from '@/components/layout/PageHeader.vue'
import MetricCard from '@/components/platform/MetricCard.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import Sub2apiTemplateTopPicks from '@/modules/examples/components/Sub2apiTemplateTopPicks.vue'
import { teamRecommendedStats } from '@/modules/examples/ui-assets-curation'

const stats = [
  {
    label: '固定锚点',
    value: teamRecommendedStats.total,
    hint: '这是整个 Resources 里最优先的一批模板，默认先看这页。',
    icon: 'check',
    tone: 'primary'
  },
  {
    label: '页面模板',
    value: teamRecommendedStats.pages,
    hint: '适合直接借后台成品页和页面骨架。',
    icon: 'folder',
    tone: 'primary'
  },
  {
    label: '组件模板',
    value: teamRecommendedStats.components,
    hint: '壳层、表格、分页、弹窗这类高频组件都在这里。',
    icon: 'users',
    tone: 'success'
  },
  {
    label: '工程模板',
    value: teamRecommendedStats.engineering,
    hint: '把值钱的表格状态和工程接线模板也钉进来了。',
    icon: 'runtime',
    tone: 'warning'
  }
] as const
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Resources"
      title="团队推荐 Top 10"
      description="这页只放固定锚点模板。后续开发者如果不确定先选谁，直接先从这 10 个模板开工。"
    />

    <StateBanner
      title="固定锚点页"
      description="总览页和分类页里的 Team Picks 入口都会跳到这里。你可以把它当成团队内部的默认模板首页。"
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

    <Sub2apiTemplateTopPicks />
  </section>
</template>

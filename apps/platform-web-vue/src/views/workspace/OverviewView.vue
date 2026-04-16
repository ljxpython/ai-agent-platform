<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import StateBanner from '@/components/platform/StateBanner.vue'

const { t } = useI18n()

const cards = [
  { title: 'Platform 基座', value: 'Phase 1', description: 'Vite / Vue / TS / Tailwind 3 已接通' },
  { title: '视觉方向', value: 'Workspace', description: '左侧主导航 + 顶部上下文条 + 主内容区' },
  { title: '核心模块', value: '业务工作区', description: 'overview / projects / users / assistants 已纳入统一入口' }
]
</script>

<template>
  <section class="space-y-6">
    <PageHeader
      eyebrow="Overview"
      title="Agent Platform 总览"
      description="集中查看平台入口、工作区结构与核心能力分布，所有模块都会沿用同一套布局、主题与路由边界持续扩展。"
    />

    <div class="grid gap-4 xl:grid-cols-3">
      <SurfaceCard
        v-for="card in cards"
        :key="card.title"
      >
        <div class="text-xs font-semibold uppercase tracking-[0.16em] text-workspace-700/70 dark:text-workspace-300/70">
          {{ card.title }}
        </div>
        <div class="mt-4 text-2xl font-semibold text-surface-900 dark:text-white">
          {{ card.value }}
        </div>
        <p class="mt-3 text-sm leading-6 text-surface-600 dark:text-surface-300">
          {{ card.description }}
        </p>
      </SurfaceCard>
    </div>

    <SurfaceCard>
      <h2 class="text-lg font-semibold text-surface-900 dark:text-white">
        {{ t('brand.title') }}
      </h2>
      <p class="mt-3 max-w-3xl text-sm leading-7 text-surface-600 dark:text-surface-300">
        当前工作台已经提供登录页、工作台布局、项目切换、主题切换和核心导航，后续能力会沿用同一套体验标准持续完善。
      </p>
    </SurfaceCard>

    <StateBanner
      title="下一步"
      description="继续完善 projects、users、assistants、audit 等高频页面，并补齐 runtime、graphs、sql-agent 的使用链路。"
    />
  </section>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import StateBanner from '@/components/platform/StateBanner.vue'

const { t } = useI18n()

const cards = [
  { title: 'Platform 基座', value: 'Phase 1', description: 'Vite / Vue / TS / Tailwind 3 已接通' },
  { title: '视觉方向', value: 'Workspace', description: '左侧主导航 + 顶部上下文条 + 主内容区' },
  { title: '后续迁移', value: '业务模块', description: 'overview / projects / users / assistants 优先落地' }
]
</script>

<template>
  <section class="space-y-6">
    <PageHeader
      eyebrow="Overview"
      title="Agent Platform Console 基座"
      description="这不是最终业务页，而是 platform-web-vue 的初始化样板。后续所有模块都会在这套布局、主题和路由边界上继续迁移。"
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
        当前工作重点是先把工程化边界搭实，再逐步把 `platform-web-v2` 的真实业务迁进来。这个壳子阶段已经具备登录页、工作台布局、项目切换、主题切换和占位路由。
      </p>
    </SurfaceCard>

    <StateBanner
      title="下一步"
      description="继续优先接 projects、users、assistants、audit 这批低风险高可见页面，再进入 runtime / graphs / sql-agent。"
    />
  </section>
</template>

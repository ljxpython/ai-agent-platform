<script setup lang="ts">
import { useRoute } from 'vue-router'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import StateBanner from '@/components/platform/StateBanner.vue'

const route = useRoute()
</script>

<template>
  <section class="space-y-6">
    <PageHeader
      :eyebrow="String(route.meta.eyebrow ?? 'Workspace')"
      :title="String(route.meta.title ?? '模块概览')"
      description="这个页面已经纳入 platform-web 的路由结构，后续会补齐与当前模块对应的页面内容、组件与交互能力。"
    />

    <SurfaceCard class="border-dashed border-workspace-200 bg-white/80 text-center shadow-soft dark:border-workspace-900/60">
      <div class="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-workspace-50 text-xl font-semibold text-workspace-700 dark:bg-workspace-950/60 dark:text-workspace-300">
        PW
      </div>
      <div class="mt-6 text-lg font-semibold text-surface-900 dark:text-white">
        模块准备中
      </div>
      <p class="mx-auto mt-3 max-w-2xl text-sm leading-7 text-surface-600 dark:text-surface-300">
        这里会逐步补齐该模块的页面内容、service、store 和状态流。当前工作区骨架与基础导航已经就绪，后续会在此基础上继续完善。
      </p>
    </SurfaceCard>

    <StateBanner
      title="当前状态"
      description="路由、layout、主题、登录链路和项目上下文已经具备，剩余工作将按模块优先级补齐对应的业务页面与交互能力。"
    />
  </section>
</template>

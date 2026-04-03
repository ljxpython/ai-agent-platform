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
      :title="String(route.meta.title ?? '模块占位')"
      description="这个页面已经纳入 platform-web-vue 的路由结构，后续会按迁移清单逐步接入真实业务逻辑和对应组件。"
    />

    <SurfaceCard class="border-dashed border-workspace-200 bg-white/80 text-center shadow-soft dark:border-workspace-900/60">
      <div class="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-workspace-50 text-xl font-semibold text-workspace-700 dark:bg-workspace-950/60 dark:text-workspace-300">
        PW
      </div>
      <div class="mt-6 text-lg font-semibold text-surface-900 dark:text-white">
        模块已占位
      </div>
      <p class="mx-auto mt-3 max-w-2xl text-sm leading-7 text-surface-600 dark:text-surface-300">
        这里接下来会按迁移顺序接入真实页面、service、store 和状态流。当前目标是先把可运行的工程骨架搭稳。
      </p>
    </SurfaceCard>

    <StateBanner
      title="当前状态"
      description="路由、layout、主题、登录链路和项目上下文已经具备，剩余工作会按迁移优先级逐个接入真实业务页面。"
    />
  </section>
</template>

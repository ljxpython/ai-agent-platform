<script setup lang="ts">
import BaseIcon from '@/components/base/BaseIcon.vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <div class="relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-50 p-6 dark:bg-dark-950">
    <div class="pointer-events-none absolute inset-0 bg-mesh-gradient dark:opacity-30" />
    <div class="pointer-events-none absolute inset-0 bg-workspace-glow" />

    <div class="relative z-10 grid w-full max-w-5xl gap-8 xl:grid-cols-[1.1fr_0.9fr]">
      <div class="hidden flex-col justify-center rounded-[28px] border border-slate-200/80 bg-white/75 p-10 shadow-glass backdrop-blur xl:flex dark:border-dark-700/70 dark:bg-dark-900/75">
        <div class="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-primary-500 to-primary-600 text-white shadow-glow">
          <BaseIcon
            name="sparkle"
            size="lg"
          />
        </div>
        <div class="mt-8">
          <div class="pw-page-eyebrow">
            Platform Workspace
          </div>
          <h1 class="mt-2 text-4xl font-semibold tracking-tight text-slate-900 dark:text-white">
            更成熟的工作台基座，先把样式和结构打对。
          </h1>
          <p class="mt-4 max-w-xl text-base leading-8 text-slate-500 dark:text-dark-300">
            当前这套迁移前端会逐步承接 platform 的全部能力，但第一步先把布局、层级、筛选器、表格和状态表达拉到成熟 SaaS 后台的质感上。
          </p>
        </div>
        <div class="mt-10 grid gap-4 md:grid-cols-2">
          <div class="pw-card bg-slate-50/90 p-4 dark:bg-dark-950/70">
            <div class="flex items-center gap-2 text-sm font-semibold text-slate-900 dark:text-white">
              <BaseIcon
                name="overview"
                size="sm"
                class="text-primary-500"
              />
              统一页面母版
            </div>
            <p class="mt-2 text-sm leading-7 text-slate-500 dark:text-dark-300">
              先把左侧导航、顶部上下文条、表格页母版和状态组件收敛好。
            </p>
          </div>
          <div class="pw-card bg-slate-50/90 p-4 dark:bg-dark-950/70">
            <div class="flex items-center gap-2 text-sm font-semibold text-slate-900 dark:text-white">
              <BaseIcon
                name="assistant"
                size="sm"
                class="text-primary-500"
              />
              业务逐步迁移
            </div>
            <p class="mt-2 text-sm leading-7 text-slate-500 dark:text-dark-300">
              首批真实页面已经接通，后续会继续迁移 runtime、graphs、sql-agent 等复杂工作区。
            </p>
          </div>
        </div>
      </div>

      <div class="flex items-center">
        <div class="w-full rounded-[28px] border border-slate-200/80 bg-white/82 p-8 shadow-glass backdrop-blur dark:border-dark-700/70 dark:bg-dark-900/82">
          <div class="mb-8">
            <div class="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-primary-500 to-primary-600 text-white shadow-glow">
              PW
            </div>
            <h1 class="mt-6 text-3xl font-semibold tracking-tight text-slate-900 dark:text-white">
              {{ t('auth.title') }}
            </h1>
            <p class="mt-3 text-sm leading-6 text-slate-500 dark:text-dark-300">
              {{ t('auth.description') }}
            </p>
          </div>

          <router-view />
        </div>
      </div>
    </div>
  </div>
</template>

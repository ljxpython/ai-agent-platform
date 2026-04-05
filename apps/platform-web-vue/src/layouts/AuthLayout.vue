<script setup lang="ts">
import BaseIcon from '@/components/base/BaseIcon.vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <div class="relative flex min-h-screen items-center justify-center overflow-hidden bg-gray-50 p-4 dark:bg-dark-950">
    <div class="absolute inset-0 bg-gradient-to-br from-gray-50 via-primary-50/30 to-gray-100 dark:from-dark-950 dark:via-dark-900 dark:to-dark-950" />

    <div class="pointer-events-none absolute inset-0 overflow-hidden">
      <div class="absolute -right-40 -top-40 h-80 w-80 rounded-full bg-primary-400/20 blur-3xl" />
      <div class="absolute -bottom-40 -left-40 h-80 w-80 rounded-full bg-primary-500/15 blur-3xl" />
      <div class="absolute left-1/2 top-1/2 h-96 w-96 -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary-300/10 blur-3xl" />
      <div class="absolute inset-0 bg-[linear-gradient(rgba(20,184,166,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(20,184,166,0.03)_1px,transparent_1px)] bg-[size:64px_64px]" />
    </div>

    <div class="relative z-10 grid w-full max-w-6xl gap-10 xl:grid-cols-[1.1fr_0.9fr]">
      <div class="hidden flex-col justify-center xl:flex">
        <div class="mb-6 inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-primary text-white shadow-glow">
          <BaseIcon
            name="sparkle"
            size="lg"
          />
        </div>
        <div>
          <div class="pw-page-eyebrow">
            Platform Workspace
          </div>
          <h1 class="mt-3 text-5xl font-semibold tracking-tight text-gray-900 dark:text-white">
            平台前端要先把壳子搭对，再谈业务规模化迁移。
          </h1>
          <p class="mt-5 max-w-xl text-base leading-8 text-gray-500 dark:text-dark-400">
            新工作台不会再走临时后台那种凑合路线。先把布局、层级、卡片、表格和状态表达拉到成熟 SaaS 后台的基准线上，再把全部 platform 能力稳稳迁进去。
          </p>
        </div>
        <div class="mt-10 grid gap-4 md:grid-cols-2">
          <div class="card-glass p-5">
            <div class="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
              <BaseIcon
                name="overview"
                size="sm"
                class="text-primary-500"
              />
              左侧主导航
            </div>
            <p class="mt-3 text-sm leading-7 text-gray-500 dark:text-dark-400">
              用更成熟的侧栏层级和信息密度，承载 overview、projects、users、assistants 以及后续复杂工作区。
            </p>
          </div>
          <div class="card-glass p-5">
            <div class="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
              <BaseIcon
                name="assistant"
                size="sm"
                class="text-primary-500"
              />
              真实平台链路
            </div>
            <p class="mt-3 text-sm leading-7 text-gray-500 dark:text-dark-400">
              登录、用户、项目、审计已经接上真实接口，后面会继续迁移 runtime、graphs、sql-agent、chat 和 testcase。
            </p>
          </div>
        </div>
      </div>

      <div class="flex items-center justify-center">
        <div class="w-full max-w-md">
          <div class="mb-8 text-center">
            <div class="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-primary text-white shadow-glow">
              PW
            </div>
            <div class="mt-5 text-3xl font-bold text-gray-900 dark:text-white">
              Platform Workspace
            </div>
            <p class="mt-2 text-sm text-gray-500 dark:text-dark-400">
              Mature admin console baseline
            </p>
          </div>

          <div class="card-glass rounded-[28px] p-8">
            <div class="mb-8">
              <div class="pw-page-eyebrow">
                Sign In
              </div>
              <h1 class="mt-3 text-3xl font-semibold tracking-tight text-gray-900 dark:text-white">
                {{ t('auth.title') }}
              </h1>
              <p class="mt-3 text-sm leading-7 text-gray-500 dark:text-dark-400">
                {{ t('auth.description') }}
              </p>
            </div>

            <router-view />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

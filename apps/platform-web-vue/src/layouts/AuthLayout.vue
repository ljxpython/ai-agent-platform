<script setup lang="ts">
import BrandMark from '@/components/layout/BrandMark.vue'
import { appMeta } from '@/config/app-meta'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <div class="relative flex min-h-screen items-center justify-center overflow-hidden p-4 dark:bg-dark-950">
    <div class="absolute inset-0 bg-gradient-to-br from-gray-50 via-primary-50/30 to-gray-100 dark:from-dark-950 dark:via-dark-900 dark:to-dark-950" />

    <div class="pointer-events-none absolute inset-0 overflow-hidden">
      <div class="absolute -right-40 -top-40 h-80 w-80 rounded-full bg-primary-400/20 blur-3xl" />
      <div class="absolute -bottom-40 -left-40 h-80 w-80 rounded-full bg-primary-500/15 blur-3xl" />
      <div class="absolute left-1/2 top-1/2 h-96 w-96 -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary-300/10 blur-3xl" />
      <div class="absolute inset-0 bg-[linear-gradient(rgba(20,184,166,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(20,184,166,0.03)_1px,transparent_1px)] bg-[size:64px_64px]" />
    </div>

    <div class="relative z-10 w-full max-w-md">
      <div class="mb-8 text-center">
        <div class="mb-4 inline-flex h-16 w-16 items-center justify-center overflow-hidden rounded-2xl shadow-lg shadow-primary-500/30">
          <BrandMark alt="Agent Platform mark" />
        </div>
        <h1 class="mb-2 bg-gradient-to-r from-primary-600 to-primary-500 bg-clip-text text-3xl font-bold text-transparent">
          {{ appMeta.name }}
        </h1>
        <p class="text-sm text-gray-500 dark:text-dark-400">
          {{ t('brand.subtitle') }}
        </p>
      </div>

      <div class="card-glass rounded-2xl p-8 shadow-glass">
        <div class="mb-8 text-center">
          <h2 class="text-2xl font-bold text-gray-900 dark:text-white">
            {{ t('auth.title') }}
          </h2>
          <p class="mt-2 text-sm text-gray-500 dark:text-dark-400">
            {{ t('auth.description') }}
          </p>
        </div>

        <router-view />
      </div>
    </div>
  </div>
</template>

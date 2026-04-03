<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import BaseIcon from '@/components/base/BaseIcon.vue'
import ThemeToggle from '@/components/base/ThemeToggle.vue'
import WorkspaceProjectSwitcher from '@/components/platform/WorkspaceProjectSwitcher.vue'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const route = useRoute()
const { t } = useI18n()

const routeTitle = computed(() => String(route.meta.title || t('brand.title')))
const routeEyebrow = computed(() => String(route.meta.eyebrow || t('common.workspace')))
</script>

<template>
  <header class="pw-topbar px-4 py-3 md:px-6 lg:px-8">
    <div class="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
      <div class="flex min-w-0 items-center gap-4">
        <div class="hidden h-10 w-px bg-slate-200 lg:block dark:bg-dark-800" />
        <div class="min-w-0">
          <div class="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-dark-400">
            {{ routeEyebrow }}
          </div>
          <div class="truncate text-base font-semibold text-slate-900 dark:text-white">
            {{ routeTitle }}
          </div>
        </div>
        <div class="hidden flex-wrap items-center gap-2 lg:flex">
          <span class="pw-pill">
            <BaseIcon
              name="user"
              size="xs"
            />
            {{ authStore.user?.username ?? t('common.loading') }}
          </span>
          <span class="pw-pill">
            <BaseIcon
              name="shield"
              size="xs"
            />
            {{ authStore.roleLabel }}
          </span>
        </div>
      </div>

      <div class="flex flex-wrap items-center gap-3">
        <WorkspaceProjectSwitcher />
        <ThemeToggle />
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AnnouncementCenter from '@/components/layout/AnnouncementCenter.vue'
import LocaleSwitcher from '@/components/layout/LocaleSwitcher.vue'
import UserMenu from '@/components/layout/UserMenu.vue'
import WorkspaceProjectSwitcher from '@/components/platform/WorkspaceProjectSwitcher.vue'
const route = useRoute()
const { t } = useI18n()

const routeTitle = computed(() => String(route.meta.title || t('brand.title')))
const routeEyebrow = computed(() => String(route.meta.eyebrow || t('common.workspace')))
</script>

<template>
  <header class="pw-topbar">
    <div class="flex h-full items-center justify-between gap-4 px-4 md:px-6">
      <div class="flex min-w-0 flex-1 items-center gap-3">
        <div class="min-w-0">
          <div class="text-[10px] font-semibold uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
            {{ routeEyebrow }}
          </div>
          <div class="mt-0.5 truncate text-[17px] font-semibold tracking-[-0.01em] text-gray-900 dark:text-white md:text-lg">
            {{ routeTitle }}
          </div>
        </div>
      </div>

      <div class="flex min-w-0 shrink-0 items-center justify-end gap-1.5 overflow-x-auto md:gap-2">
        <WorkspaceProjectSwitcher />
        <LocaleSwitcher />
        <AnnouncementCenter />
        <UserMenu />
      </div>
    </div>
  </header>
</template>

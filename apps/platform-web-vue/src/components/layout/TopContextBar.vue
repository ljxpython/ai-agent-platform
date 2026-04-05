<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AnnouncementCenter from '@/components/layout/AnnouncementCenter.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import LocaleSwitcher from '@/components/layout/LocaleSwitcher.vue'
import UserMenu from '@/components/layout/UserMenu.vue'
import WorkspaceProjectSwitcher from '@/components/platform/WorkspaceProjectSwitcher.vue'
import { useAuthStore } from '@/stores/auth'
import { useWorkspaceStore } from '@/stores/workspace'

const authStore = useAuthStore()
const workspaceStore = useWorkspaceStore()
const route = useRoute()
const { t } = useI18n()

const routeTitle = computed(() => String(route.meta.title || t('brand.title')))
const routeEyebrow = computed(() => String(route.meta.eyebrow || t('common.workspace')))
const routeSubtitle = computed(() =>
  workspaceStore.currentProject?.name
    ? t('topbar.projectContext', { project: workspaceStore.currentProject.name })
    : t('topbar.globalContext')
)
const roleLabel = computed(() => (authStore.user?.is_super_admin ? t('common.admin') : t('common.member')))
</script>

<template>
  <header class="pw-topbar">
    <div class="flex min-h-16 flex-wrap items-start justify-between gap-3 px-4 py-3 md:px-6 lg:px-8">
      <div class="flex min-w-0 flex-1 items-center gap-4">
        <div class="min-w-0">
          <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-500">
            {{ routeEyebrow }}
          </div>
          <div class="mt-1 truncate text-lg font-semibold text-gray-900 dark:text-white">
            {{ routeTitle }}
          </div>
          <p class="text-xs text-gray-500 dark:text-dark-400">
            {{ routeSubtitle }}
          </p>
        </div>
      </div>

      <div class="flex min-w-0 w-full flex-wrap items-center justify-end gap-2 md:w-auto md:flex-nowrap md:gap-3">
        <WorkspaceProjectSwitcher />
        <div class="pw-topbar-chip pw-topbar-chip-primary hidden sm:flex">
          <BaseIcon
            name="shield"
            size="sm"
            class="text-primary-600 dark:text-primary-400"
          />
          <span class="text-sm font-semibold">
            {{ roleLabel }}
          </span>
        </div>
        <LocaleSwitcher />
        <AnnouncementCenter />
        <UserMenu />
      </div>
    </div>
  </header>
</template>

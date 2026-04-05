<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import BaseIcon from '@/components/base/BaseIcon.vue'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { useUiStore } from '@/stores/ui'

const route = useRoute()
const { t } = useI18n()
const uiStore = useUiStore()
const authStore = useAuthStore()
const themeStore = useThemeStore()
const isDev = import.meta.env.DEV
const roleLabel = computed(() => (authStore.user?.is_super_admin ? t('common.admin') : t('common.member')))

type SidebarItem = {
  to: string
  label: string
  icon: string
  exact?: boolean
}

type SidebarGroup = {
  label: string
  items: SidebarItem[]
}

const groups = computed(() => {
  const baseGroups: SidebarGroup[] = [
    {
      label: 'Workspace',
      items: [
        { to: '/workspace/overview', label: t('nav.overview'), icon: 'overview' },
        { to: '/workspace/projects', label: t('nav.projects'), icon: 'folder' },
        { to: '/workspace/users', label: t('nav.users'), icon: 'users' },
        { to: '/workspace/assistants', label: t('nav.assistants'), icon: 'assistant' }
      ]
    },
    {
      label: 'Agent',
      items: [
        { to: '/workspace/runtime', label: t('nav.runtime'), icon: 'runtime' },
        { to: '/workspace/graphs', label: t('nav.graphs'), icon: 'graph' },
        { to: '/workspace/sql-agent', label: t('nav.sqlAgent'), icon: 'sql-agent' },
        { to: '/workspace/threads', label: t('nav.threads'), icon: 'threads' },
        { to: '/workspace/chat', label: t('nav.chat'), icon: 'chat' }
      ]
    },
    {
      label: 'Quality',
      items: [
        { to: '/workspace/testcase', label: t('nav.testcase'), icon: 'testcase' },
        { to: '/workspace/announcements', label: t('nav.announcements'), icon: 'bell' },
        { to: '/workspace/me', label: t('nav.me'), icon: 'user' },
        { to: '/workspace/security', label: t('nav.security'), icon: 'lock' },
        { to: '/workspace/audit', label: t('nav.audit'), icon: 'audit' }
      ]
    }
  ]

  if (isDev) {
    baseGroups.push({
      label: 'Resources',
      items: [
        { to: '/workspace/resources', label: t('nav.resourcesOverview'), icon: 'sparkle', exact: true },
        { to: '/workspace/resources/playbook', label: t('nav.resourcePlaybook'), icon: 'overview' },
        { to: '/workspace/resources/pages', label: t('nav.resourcePages'), icon: 'folder' },
        { to: '/workspace/resources/components', label: t('nav.resourceComponents'), icon: 'users' },
        { to: '/workspace/resources/engineering', label: t('nav.resourceEngineering'), icon: 'runtime' }
      ]
    })
  }

  return baseGroups
})

function isActive(path: string, exact = false): boolean {
  if (exact) {
    return route.path === path
  }

  return route.path === path || route.path.startsWith(`${path}/`)
}

const initials = computed(() => (authStore.user?.username || 'PW').slice(0, 2).toUpperCase())
</script>

<template>
  <aside
    class="pw-sidebar transition-[width] duration-300"
    :class="uiStore.sidebarCollapsed ? 'w-[72px]' : 'w-64'"
  >
    <div class="pw-sidebar-header">
      <div class="flex h-9 w-9 items-center justify-center overflow-hidden rounded-xl bg-gradient-primary text-sm font-semibold text-white shadow-glow">
        {{ uiStore.sidebarCollapsed ? 'P' : 'PW' }}
      </div>
      <div
        v-if="!uiStore.sidebarCollapsed"
        class="flex min-w-0 flex-col"
      >
        <div class="truncate text-base font-bold text-gray-900 dark:text-white">
          Platform Workspace
        </div>
        <div class="mt-0.5 text-xs uppercase tracking-[0.16em] text-gray-400 dark:text-dark-500">
          platform console
        </div>
      </div>
    </div>

    <nav class="pw-sidebar-nav">
      <section
        v-for="group in groups"
        :key="group.label"
        class="mb-6"
      >
        <div
          v-if="!uiStore.sidebarCollapsed"
          class="pw-sidebar-section-title"
        >
          {{ group.label }}
        </div>
        <div
          v-else
          class="mx-3 my-3 h-px bg-gray-200 dark:bg-dark-700"
        />
        <div class="space-y-1">
          <router-link
            v-for="item in group.items"
            :key="item.to"
            :to="item.to"
            class="pw-sidebar-link"
            :class="isActive(item.to, item.exact) ? 'pw-sidebar-link-active' : ''"
            :title="uiStore.sidebarCollapsed ? item.label : undefined"
          >
            <BaseIcon
              :name="item.icon as never"
              size="sm"
            />
            <span v-if="!uiStore.sidebarCollapsed">{{ item.label }}</span>
          </router-link>
        </div>
      </section>
    </nav>

    <div class="mt-auto border-t border-gray-100 p-3 dark:border-dark-800">
      <div
        v-if="!uiStore.sidebarCollapsed"
        class="mb-3 rounded-2xl border border-white/60 bg-white/70 p-3 shadow-soft backdrop-blur dark:border-dark-700 dark:bg-dark-900/70"
      >
        <div class="flex items-center gap-3">
          <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-primary text-sm font-semibold text-white shadow-sm shadow-primary-500/25">
            {{ initials }}
          </div>
          <div class="min-w-0">
            <div class="truncate text-sm font-semibold text-gray-900 dark:text-white">
              {{ authStore.user?.username || t('common.loading') }}
            </div>
            <div class="text-xs text-gray-500 dark:text-dark-400">
              {{ roleLabel }}
            </div>
          </div>
        </div>
      </div>

      <button
        type="button"
        class="pw-sidebar-link mb-2 w-full"
        :title="uiStore.sidebarCollapsed ? (themeStore.mode === 'dark' ? t('common.lightMode') : t('common.darkMode')) : undefined"
        @click="themeStore.toggleMode"
      >
        <BaseIcon
          :name="themeStore.mode === 'dark' ? 'sun' : 'moon'"
          size="sm"
          :class="themeStore.mode === 'dark' ? 'text-amber-500' : ''"
        />
        <span v-if="!uiStore.sidebarCollapsed">
          {{ themeStore.mode === 'dark' ? t('common.lightMode') : t('common.darkMode') }}
        </span>
      </button>

      <button
        type="button"
        class="pw-sidebar-link w-full"
        :title="uiStore.sidebarCollapsed ? '展开' : '收起'"
        @click="uiStore.toggleSidebar"
      >
        <BaseIcon
          :name="uiStore.sidebarCollapsed ? 'expand' : 'collapse'"
          size="sm"
        />
        <span v-if="!uiStore.sidebarCollapsed">
          {{ uiStore.sidebarCollapsed ? '展开' : '收起' }}
        </span>
      </button>
    </div>
  </aside>
</template>

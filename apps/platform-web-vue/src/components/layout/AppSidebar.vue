<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import BaseIcon from '@/components/base/BaseIcon.vue'
import { appMeta } from '@/config/app-meta'
import BrandMark from '@/components/layout/BrandMark.vue'
import { useThemeStore } from '@/stores/theme'
import { useUiStore } from '@/stores/ui'

const route = useRoute()
const { t } = useI18n()
const uiStore = useUiStore()
const themeStore = useThemeStore()
const isDev = import.meta.env.DEV

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
        { to: '/workspace/runtime/policies', label: t('nav.runtimePolicies'), icon: 'shield' },
        { to: '/workspace/graphs', label: t('nav.graphs'), icon: 'graph' },
        { to: '/workspace/sql-agent', label: t('nav.sqlAgent'), icon: 'sql-agent' },
        { to: '/workspace/threads', label: t('nav.threads'), icon: 'threads' },
        { to: '/workspace/chat', label: t('nav.chat'), icon: 'chat' }
      ]
    },
    {
      label: 'Governance',
      items: [
        { to: '/workspace/operations', label: t('nav.operations'), icon: 'activity' },
        { to: '/workspace/announcements', label: t('nav.announcements'), icon: 'bell' },
        { to: '/workspace/platform-config', label: t('nav.platformConfig'), icon: 'lock' },
        { to: '/workspace/audit', label: t('nav.audit'), icon: 'audit' }
      ]
    },
    {
      label: 'Quality',
      items: [
        { to: '/workspace/testcase', label: t('nav.testcase'), icon: 'testcase' },
        { to: '/workspace/me', label: t('nav.me'), icon: 'user' },
        { to: '/workspace/security', label: t('nav.security'), icon: 'lock' }
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
</script>

<template>
  <aside
    class="pw-sidebar transition-[width] duration-300"
    :class="uiStore.sidebarCollapsed ? 'w-[72px]' : 'w-64'"
  >
    <div class="pw-sidebar-header">
      <div class="flex h-9 w-9 items-center justify-center overflow-hidden rounded-xl shadow-glow">
        <BrandMark alt="Agent Platform Console mark" />
      </div>
      <div
        v-if="!uiStore.sidebarCollapsed"
        class="flex min-w-0 flex-col"
      >
        <div class="truncate text-base font-bold text-gray-900 dark:text-white">
          {{ appMeta.name }}
        </div>
        <div class="mt-0.5 text-xs uppercase tracking-[0.16em] text-gray-400 dark:text-dark-500">
          {{ appMeta.versionLabel }}
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

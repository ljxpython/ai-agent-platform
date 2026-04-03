<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import { useUiStore } from '@/stores/ui'

const route = useRoute()
const { t } = useI18n()
const uiStore = useUiStore()

const groups = computed(() => [
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
      { to: '/workspace/me', label: t('nav.me'), icon: 'user' },
      { to: '/workspace/security', label: t('nav.security'), icon: 'lock' },
      { to: '/workspace/audit', label: t('nav.audit'), icon: 'audit' }
    ]
  }
])

function isActive(path: string): boolean {
  return route.path === path || route.path.startsWith(`${path}/`)
}
</script>

<template>
  <aside
    class="pw-sidebar shadow-sm transition-[width] duration-300"
    :class="uiStore.sidebarCollapsed ? 'w-20' : 'w-64'"
  >
    <div class="pw-sidebar-header">
      <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-primary-500 to-primary-600 text-sm font-semibold text-white shadow-glow">
        PW
      </div>
      <div v-if="!uiStore.sidebarCollapsed">
        <div class="text-sm font-semibold tracking-wide text-slate-900 dark:text-white">
          Platform Workspace
        </div>
        <div class="mt-1 text-xs uppercase tracking-[0.18em] text-slate-400 dark:text-dark-400">
          workspace console
        </div>
      </div>
    </div>

    <nav class="pw-sidebar-nav space-y-6">
      <section
        v-for="group in groups"
        :key="group.label"
        class="space-y-2"
      >
        <div
          v-if="!uiStore.sidebarCollapsed"
          class="pw-sidebar-section-title"
        >
          {{ group.label }}
        </div>
        <div class="space-y-1">
          <router-link
            v-for="item in group.items"
            :key="item.to"
            :to="item.to"
            class="pw-sidebar-link"
            :class="isActive(item.to) ? 'pw-sidebar-link-active' : ''"
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

    <div class="mt-auto border-t border-slate-100 p-3 dark:border-dark-800">
      <BaseButton
        variant="ghost"
        block
        @click="uiStore.toggleSidebar"
      >
        <BaseIcon
          :name="uiStore.sidebarCollapsed ? 'expand' : 'collapse'"
          size="sm"
        />
        <span v-if="!uiStore.sidebarCollapsed">
          {{ uiStore.sidebarCollapsed ? '展开' : '收起' }}
        </span>
      </BaseButton>
    </div>
  </aside>
</template>

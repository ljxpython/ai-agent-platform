<script setup lang="ts">
import { watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import BaseIcon from '@/components/base/BaseIcon.vue'
import { useNavigation } from '@/composables/useNavigation'
import { appMeta } from '@/config/app-meta'
import BrandMark from '@/components/layout/BrandMark.vue'
import { useThemeStore } from '@/stores/theme'
import { useUiStore } from '@/stores/ui'

const route = useRoute()
const { t } = useI18n()
const uiStore = useUiStore()
const themeStore = useThemeStore()

const groups = useNavigation()

function isActive(path: string, exact = false): boolean {
  if (exact) {
    return route.path === path
  }

  return route.path === path || route.path.startsWith(`${path}/`)
}

function isGroupExpanded(groupId: string): boolean {
  if (uiStore.sidebarCollapsed) {
    return true
  }

  return uiStore.isSidebarGroupExpanded(groupId)
}

function isGroupActive(group: (typeof groups.value)[number]): boolean {
  return group.items.some((item) => isActive(item.to, item.exact))
}

function toggleGroup(groupId: string) {
  if (uiStore.sidebarCollapsed) {
    return
  }

  uiStore.toggleSidebarGroup(groupId)
}

watch(
  groups,
  (nextGroups) => {
    uiStore.ensureSidebarExpandedGroups(nextGroups.map((group) => group.id))
  },
  { immediate: true },
)
</script>

<template>
  <aside
    class="pw-sidebar transition-[width] duration-300"
    :class="uiStore.sidebarCollapsed ? 'w-[72px]' : 'w-64'"
  >
    <div class="pw-sidebar-header">
      <div class="flex h-9 w-9 items-center justify-center overflow-hidden rounded-xl shadow-glow">
        <BrandMark
          alt="Agent Platform mark"
          class="scale-[1.08]"
        />
      </div>
      <div
        v-if="!uiStore.sidebarCollapsed"
        class="flex min-w-0 flex-col"
      >
        <div class="truncate text-[17px] font-semibold tracking-[-0.01em] text-gray-900 dark:text-white">
          {{ appMeta.name }}
        </div>
        <div class="mt-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
          {{ appMeta.versionLabel }}
        </div>
      </div>
    </div>

    <nav class="pw-sidebar-nav">
      <section
        v-for="group in groups"
        :key="group.id"
        class="mb-6"
      >
        <button
          v-if="!uiStore.sidebarCollapsed"
          type="button"
          class="mb-2 flex w-full items-center px-3 pb-1 pt-0.5 text-left transition-colors duration-150 hover:text-gray-700 dark:hover:text-dark-200"
          :class="isGroupActive(group) ? 'text-gray-700 dark:text-dark-100' : 'text-gray-400 dark:text-dark-500'"
          :aria-expanded="isGroupExpanded(group.id)"
          @click="toggleGroup(group.id)"
        >
          <span class="pw-sidebar-section-title mb-0 px-0">
            {{ group.label }}
          </span>
        </button>
        <div
          v-else
          class="mx-4 my-3 h-px bg-gray-200 dark:bg-dark-800"
        />
        <div
          v-show="isGroupExpanded(group.id)"
          class="space-y-1"
        >
          <template
            v-for="item in group.items"
            :key="item.to"
          >
            <div
              v-if="!uiStore.sidebarCollapsed && item.sectionTitle"
              class="pw-sidebar-subsection-title"
            >
              {{ item.sectionTitle }}
            </div>
            <router-link
              :to="item.to"
              class="pw-sidebar-link"
              :class="isActive(item.to, item.exact) ? 'pw-sidebar-link-active' : ''"
              :title="uiStore.sidebarCollapsed ? item.label : undefined"
            >
              <BaseIcon
                :name="item.icon as never"
                size="md"
                class="shrink-0"
              />
              <span v-if="!uiStore.sidebarCollapsed">{{ item.label }}</span>
            </router-link>
          </template>
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
          size="md"
          class="shrink-0"
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
          :name="uiStore.sidebarCollapsed ? 'chevron-right' : 'chevron-left'"
          size="md"
          class="shrink-0"
        />
        <span v-if="!uiStore.sidebarCollapsed">
          收起
        </span>
      </button>
    </div>
  </aside>
</template>

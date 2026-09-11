<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AnnouncementCenter from '@/components/layout/AnnouncementCenter.vue'
import LocaleSwitcher from '@/components/layout/LocaleSwitcher.vue'
import UserMenu from '@/components/layout/UserMenu.vue'
import WorkspaceProjectSwitcher from '@/components/platform/WorkspaceProjectSwitcher.vue'
import BaseDialog from '@/components/base/BaseDialog.vue'
import { useNavigation } from '@/composables/useNavigation'
import { useThemeStore } from '@/stores/theme'
const navigation = useNavigation()
const menuOpen = ref(false)
const theme = useThemeStore()
const route = useRoute()
watch(() => route.fullPath, () => { menuOpen.value = false })
const { t } = useI18n()

const routeTitle = computed(() => String(route.meta.title || t('brand.title')))
const routeEyebrow = computed(() => String(route.meta.eyebrow || t('common.workspace')))
</script>

<template>
  <header class="pw-topbar">
    <div class="flex h-full items-center justify-between gap-4 px-4 md:px-6">
      <div class="flex min-w-0 shrink-0 items-center gap-3 md:flex-1">
        <button
          class="pw-topbar-action lg:hidden"
          aria-label="打开导航"
          @click="menuOpen = true"
        >
          ☰
        </button>
        <div class="hidden min-w-0 md:block">
          <div class="text-[10px] font-semibold uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
            {{ routeEyebrow }}
          </div>
          <div class="mt-0.5 truncate text-[17px] font-semibold tracking-[-0.01em] text-gray-900 dark:text-white md:text-lg">
            {{ routeTitle }}
          </div>
        </div>
      </div>

      <div class="flex min-w-0 flex-1 items-center justify-end gap-1.5 overflow-x-auto md:flex-none md:gap-2">
        <WorkspaceProjectSwitcher />
        <LocaleSwitcher />
        <AnnouncementCenter />
        <UserMenu />
      </div>
    </div>
  </header>
  <BaseDialog
    :show="menuOpen"
    title="平台导航"
    @close="menuOpen = false"
  >
    <nav
      aria-label="移动端导航"
      class="space-y-4"
    >
      <section
        v-for="group in navigation"
        :key="group.id"
      >
        <h2 class="mb-2 text-xs text-gray-500">
          {{ group.label }}
        </h2>
        <RouterLink
          v-for="item in group.items"
          :key="item.to"
          :to="item.to"
          class="block rounded-lg px-3 py-2 hover:bg-gray-100 dark:hover:bg-dark-800"
        >
          {{ item.label }}
        </RouterLink>
      </section>
    </nav>
    <button
      class="pw-table-tool-button mt-4"
      @click="theme.toggleMode"
    >
      切换浅色/深色
    </button>
  </BaseDialog>
</template>

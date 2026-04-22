<script setup lang="ts">
import { storeToRefs } from 'pinia'
import AppSidebar from '@/components/layout/AppSidebar.vue'
import TopContextBar from '@/components/layout/TopContextBar.vue'
import { useUiStore } from '@/stores/ui'

const uiStore = useUiStore()
const { sidebarCollapsed } = storeToRefs(uiStore)
</script>

<template>
  <div class="min-h-screen bg-gray-50 text-gray-900 dark:bg-dark-950 dark:text-white">
    <div class="pointer-events-none fixed inset-0 bg-mesh-gradient" />

    <AppSidebar />

    <div
      class="relative flex min-h-screen min-w-0 flex-col transition-all duration-300"
      :class="sidebarCollapsed ? 'lg:ml-[72px]' : 'lg:ml-64'"
    >
      <TopContextBar />
      <main class="pw-workspace-main flex min-h-0 flex-1 flex-col">
        <div class="min-h-0 w-full flex-1">
          <router-view />
        </div>
      </main>
    </div>
  </div>
</template>

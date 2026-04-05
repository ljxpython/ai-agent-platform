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
    <div class="pointer-events-none fixed inset-0 bg-mesh-gradient opacity-80 dark:opacity-40" />
    <div class="pointer-events-none fixed inset-0 bg-workspace-glow" />

    <AppSidebar />

    <div
      class="relative flex min-h-screen min-w-0 flex-col transition-all duration-300"
      :class="sidebarCollapsed ? 'lg:ml-[72px]' : 'lg:ml-64'"
    >
      <TopContextBar />
      <main class="min-w-0 flex-1 px-4 py-4 md:px-6 md:py-6 lg:px-8 lg:py-8">
        <div class="min-w-0 w-full">
          <router-view />
        </div>
      </main>
    </div>
  </div>
</template>

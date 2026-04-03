<script setup lang="ts">
import { storeToRefs } from 'pinia'
import AppSidebar from '@/components/layout/AppSidebar.vue'
import TopContextBar from '@/components/layout/TopContextBar.vue'
import { useUiStore } from '@/stores/ui'

const uiStore = useUiStore()
const { sidebarCollapsed } = storeToRefs(uiStore)
</script>

<template>
  <div class="min-h-screen bg-slate-50 text-surface-900 dark:bg-dark-950 dark:text-white">
    <div class="pointer-events-none fixed inset-0 bg-mesh-gradient dark:opacity-30" />
    <div class="pointer-events-none fixed inset-0 bg-workspace-glow" />

    <AppSidebar />

    <div
      class="relative min-h-screen transition-all duration-300"
      :class="sidebarCollapsed ? 'lg:ml-20' : 'lg:ml-64'"
    >
      <TopContextBar />
      <main class="w-full px-4 py-6 md:px-6 lg:px-8">
        <router-view />
      </main>
    </div>
  </div>
</template>

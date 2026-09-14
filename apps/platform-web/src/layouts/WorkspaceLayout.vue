<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'
import AppSidebar from '@/components/layout/AppSidebar.vue'
import TopContextBar from '@/components/layout/TopContextBar.vue'
import { useUiStore } from '@/stores/ui'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const uiStore = useUiStore()
const authStore = useAuthStore()
const { sidebarCollapsed } = storeToRefs(uiStore)

const isImmersive = computed(() => route.name === 'workspace-chat' || Boolean(route.meta?.immersive))
</script>

<template>
  <div class="flex h-screen h-[100dvh] overflow-hidden bg-gray-50 text-gray-900 dark:bg-dark-950 dark:text-white">
    <div class="pointer-events-none fixed inset-0 bg-mesh-gradient" />

    <AppSidebar />

    <div
      class="relative flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden transition-all duration-300"
      :class="sidebarCollapsed ? 'lg:ml-[72px]' : 'lg:ml-64'"
    >
      <TopContextBar
        v-if="!isImmersive"
        class="shrink-0"
      />
      <main
        class="flex min-h-0 flex-1 flex-col overflow-hidden"
        :class="isImmersive ? 'p-0 m-0' : 'pw-workspace-main'"
      >
        <div
          class="flex min-h-0 w-full flex-1 flex-col"
          :class="isImmersive ? 'overflow-hidden' : 'overflow-y-auto'"
        >
          <router-view :key="authStore.sessionEpoch" />
        </div>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import NavigationProgress from '@/components/feedback/NavigationProgress.vue'
import { RouterView } from 'vue-router'
import ToastStack from '@/components/feedback/ToastStack.vue'
</script>

<template>
  <NavigationProgress />
  <RouterView />
  <ToastStack />
</template>

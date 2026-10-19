<script setup lang="ts">
import NavigationProgress from "@/components/feedback/NavigationProgress.vue";
import { RouterView } from "vue-router";
import ToastStack from "@/components/feedback/ToastStack.vue";
import ErrorBoundary from "@/components/feedback/ErrorBoundary.vue";
</script>

<template>
  <NavigationProgress />
  <ErrorBoundary>
    <RouterView />
  </ErrorBoundary>
  <ToastStack />
</template>

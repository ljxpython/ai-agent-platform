<script setup lang="ts">
import { ref, useSlots } from "vue";

const element = ref<HTMLElement | null>(null);
const slots = useSlots();
defineExpose({ element, slots });
</script>

<template>
  <div ref="element" class="flex min-h-0 min-w-0 flex-1 flex-col" />
</template>

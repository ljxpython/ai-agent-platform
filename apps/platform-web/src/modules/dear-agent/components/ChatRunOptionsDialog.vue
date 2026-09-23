<script lang="ts">
export * from "@/modules/chat/components/ChatRunOptionsDialog.vue";
</script>
<script setup lang="ts">
import TargetComponent from "@/modules/chat/components/ChatRunOptionsDialog.vue";

defineOptions({ inheritAttrs: false });
</script>

<template>
  <TargetComponent v-bind="($attrs as any)">
    <template v-for="(_, name) in $slots" #[name]="slotData">
      <slot :name="name" v-bind="slotData || {}" />
    </template>
  </TargetComponent>
</template>

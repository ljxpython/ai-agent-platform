<script lang="ts">
</script>
<script setup lang="ts">
import TargetComponent from "@/modules/chat/components/ChatContextDrawer.vue";

defineOptions({ inheritAttrs: false });
</script>

<template>
  <TargetComponent v-bind="($attrs as any)">
    <template v-for="(_, name) in $slots" #[name]="slotData">
      <slot :name="name" v-bind="slotData || {}" />
    </template>
  </TargetComponent>
</template>

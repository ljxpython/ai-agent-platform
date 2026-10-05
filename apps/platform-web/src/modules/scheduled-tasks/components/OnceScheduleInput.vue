<script setup lang="ts">
import { ref, watch } from "vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import { formatZonedIsoString, toDateTimeLocalValue } from "../utils/timezone";

const props = defineProps<{
  modelValue?: string | null;
  timezone: string;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  (e: "update:modelValue", value: string): void;
}>();

const localWallTime = ref(toDateTimeLocalValue(props.modelValue));

watch(
  () => props.modelValue,
  (val) => {
    localWallTime.value = toDateTimeLocalValue(val);
  },
);

function onTimeChange() {
  if (!localWallTime.value) {
    emit("update:modelValue", "");
    return;
  }
  const isoWithOffset = formatZonedIsoString(
    localWallTime.value,
    props.timezone || "Asia/Shanghai",
  );
  emit("update:modelValue", isoWithOffset);
}
</script>

<template>
  <div class="space-y-2.5">
    <div class="relative">
      <input
        v-model="localWallTime"
        type="datetime-local"
        step="1"
        class="h-9.5 px-3.5 text-xs border rounded-xl bg-surface border-border/80 focus:border-primary focus:ring-2 focus:ring-primary/20 w-full font-mono transition-all"
        :disabled="disabled"
        @change="onTimeChange"
      />
    </div>
    <div
      class="flex items-center justify-between text-xs text-muted-foreground px-1"
    >
      <div class="flex items-center gap-1 font-mono text-[11px]">
        <BaseIcon name="globe" size="xs" />
        <span>基准: {{ timezone }}</span>
      </div>
      <div
        class="flex items-center gap-1 text-amber-500 font-medium text-[11px]"
      >
        <BaseIcon name="alert" size="xs" />
        <span>需设定未来时间</span>
      </div>
    </div>
  </div>
</template>

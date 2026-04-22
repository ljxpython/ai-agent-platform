<script setup lang="ts">
import { useAttrs } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import HelpTooltip from '@/components/platform/HelpTooltip.vue'

defineOptions({
  inheritAttrs: false
})

withDefaults(
  defineProps<{
    tooltip: string
    tooltipLabel?: string
    tooltipAlign?: 'left' | 'center' | 'right'
    buttonClass?: string
  }>(),
  {
    tooltipLabel: '帮助说明',
    tooltipAlign: 'center',
    buttonClass: ''
  }
)

const attrs = useAttrs()
</script>

<template>
  <div class="relative inline-flex">
    <BaseButton
      v-bind="attrs"
      :class="['pr-10', buttonClass]"
    >
      <slot />
    </BaseButton>
    <div class="absolute right-1 top-1/2 -translate-y-1/2">
      <HelpTooltip
        :text="tooltip"
        :label="tooltipLabel"
        :align="tooltipAlign"
      />
    </div>
  </div>
</template>

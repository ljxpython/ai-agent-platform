<script setup lang="ts">
import { computed } from 'vue'
import markWorkspaceFrame from '@/assets/brand/mark-workspace-frame.svg'
import markPanelStack from '@/assets/brand/mark-panel-stack.svg'
import markMonogram from '@/assets/brand/mark-monogram.svg'
import markControlPlaneGrid from '@/assets/brand/mark-control-plane-grid.svg'
import markSplitDock from '@/assets/brand/mark-split-dock.svg'
import markBeaconFrame from '@/assets/brand/mark-beacon-frame.svg'

type BrandMarkVariant =
  | 'workspace-frame'
  | 'panel-stack'
  | 'monogram'
  | 'control-plane-grid'
  | 'split-dock'
  | 'beacon-frame'

const props = withDefaults(
  defineProps<{
    variant?: BrandMarkVariant
    alt?: string
  }>(),
  {
    variant: 'panel-stack',
    alt: 'Agent Platform brand mark'
  }
)

const variants: Record<BrandMarkVariant, string> = {
  'workspace-frame': markWorkspaceFrame,
  'panel-stack': markPanelStack,
  monogram: markMonogram,
  'control-plane-grid': markControlPlaneGrid,
  'split-dock': markSplitDock,
  'beacon-frame': markBeaconFrame
}

const src = computed(() => variants[props.variant])
</script>

<template>
  <img
    :src="src"
    :alt="alt"
    class="h-full w-full object-contain"
    draggable="false"
  >
</template>

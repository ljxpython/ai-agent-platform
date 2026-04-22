<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    values: number[]
    stroke?: string
    fill?: string
    height?: number
  }>(),
  {
    stroke: '#0f766e',
    fill: 'rgba(13, 148, 136, 0.12)',
    height: 72
  }
)

const width = 240

const normalizedPoints = computed(() => {
  if (props.values.length === 0) {
    return ''
  }
  if (props.values.length === 1) {
    const y = props.height / 2
    return `0,${y} ${width},${y}`
  }

  const max = Math.max(...props.values, 1)
  const min = Math.min(...props.values, 0)
  const range = Math.max(max - min, 1)

  return props.values
    .map((value, index) => {
      const x = (index / Math.max(props.values.length - 1, 1)) * width
      const normalized = (value - min) / range
      const y = props.height - normalized * props.height
      return `${x},${Math.max(4, Math.min(props.height - 4, y))}`
    })
    .join(' ')
})

const fillPoints = computed(() => {
  if (!normalizedPoints.value) {
    return ''
  }
  return `0,${props.height} ${normalizedPoints.value} ${width},${props.height}`
})
</script>

<template>
  <svg
    :viewBox="`0 0 ${width} ${height}`"
    class="h-[72px] w-full"
    preserveAspectRatio="none"
    role="img"
    aria-label="trend"
  >
    <polyline
      v-if="fillPoints"
      :points="fillPoints"
      :fill="fill"
      stroke="none"
    />
    <polyline
      v-if="normalizedPoints"
      :points="normalizedPoints"
      fill="none"
      :stroke="stroke"
      stroke-width="2.5"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
  </svg>
</template>

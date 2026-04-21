<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import BaseIcon from '@/components/base/BaseIcon.vue'

const props = withDefaults(
  defineProps<{
    text: string
    label?: string
    align?: 'left' | 'center' | 'right'
  }>(),
  {
    label: '帮助说明',
    align: 'center'
  }
)

const isOpen = ref(false)
const rootRef = ref<HTMLElement | null>(null)
const tooltipRef = ref<HTMLElement | null>(null)
const tooltipStyle = ref<Record<string, string>>({})
let closeTimer: number | null = null

function open() {
  if (closeTimer !== null && typeof window !== 'undefined') {
    window.clearTimeout(closeTimer)
    closeTimer = null
  }
  isOpen.value = true
}

function close() {
  if (closeTimer !== null && typeof window !== 'undefined') {
    window.clearTimeout(closeTimer)
    closeTimer = null
  }
  isOpen.value = false
}

function toggle() {
  isOpen.value = !isOpen.value
}

function scheduleClose() {
  if (typeof window === 'undefined') {
    close()
    return
  }

  if (closeTimer !== null) {
    window.clearTimeout(closeTimer)
  }
  closeTimer = window.setTimeout(() => {
    close()
  }, 80)
}

function updatePosition() {
  const trigger = rootRef.value
  const tooltip = tooltipRef.value
  if (!trigger || !tooltip || typeof window === 'undefined') {
    return
  }

  const rect = trigger.getBoundingClientRect()
  const tooltipWidth = tooltip.offsetWidth
  const tooltipHeight = tooltip.offsetHeight
  const viewportWidth = window.innerWidth
  const viewportHeight = window.innerHeight
  const gap = 8
  const viewportPadding = 16

  let left = rect.left
  if (props.align === 'center') {
    left = rect.left + rect.width / 2 - tooltipWidth / 2
  } else if (props.align === 'right') {
    left = rect.right - tooltipWidth
  }

  const maxLeft = Math.max(viewportPadding, viewportWidth - tooltipWidth - viewportPadding)
  left = Math.min(Math.max(viewportPadding, left), maxLeft)

  let top = rect.bottom + gap
  if (top + tooltipHeight > viewportHeight - viewportPadding) {
    top = Math.max(viewportPadding, rect.top - tooltipHeight - gap)
  }

  tooltipStyle.value = {
    top: `${top}px`,
    left: `${left}px`
  }
}

function handleClickOutside(event: MouseEvent) {
  const target = event.target as Node
  if (rootRef.value?.contains(target) || tooltipRef.value?.contains(target)) {
    return
  }

  close()
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  window.addEventListener('resize', updatePosition)
  window.addEventListener('scroll', updatePosition, true)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
  window.removeEventListener('resize', updatePosition)
  window.removeEventListener('scroll', updatePosition, true)
  if (closeTimer !== null && typeof window !== 'undefined') {
    window.clearTimeout(closeTimer)
  }
})

watch(isOpen, async (nextValue) => {
  if (!nextValue) {
    return
  }

  await nextTick()
  updatePosition()
})
</script>

<template>
  <span
    ref="rootRef"
    class="inline-flex"
    @mouseenter="open"
    @mouseleave="scheduleClose"
  >
    <button
      type="button"
      class="inline-flex h-8 w-8 items-center justify-center rounded-full text-gray-400 transition hover:bg-gray-100 hover:text-gray-700 dark:text-dark-400 dark:hover:bg-dark-800 dark:hover:text-dark-100"
      :aria-label="label"
      @click.stop="toggle"
    >
      <BaseIcon
        name="info"
        size="xs"
      />
    </button>

    <Teleport to="body">
      <Transition
        enter-active-class="transition duration-150 ease-out"
        enter-from-class="translate-y-1 opacity-0"
        enter-to-class="translate-y-0 opacity-100"
        leave-active-class="transition duration-120 ease-in"
        leave-from-class="translate-y-0 opacity-100"
        leave-to-class="translate-y-1 opacity-0"
      >
        <div
          v-if="isOpen"
          ref="tooltipRef"
          class="fixed z-[160] w-[min(280px,calc(100vw-2rem))] rounded-2xl border border-gray-200 bg-white px-3 py-3 text-xs leading-6 text-gray-600 shadow-lg dark:border-dark-700 dark:bg-dark-900 dark:text-dark-200"
          :style="tooltipStyle"
          @mouseenter="open"
          @mouseleave="scheduleClose"
        >
          {{ text }}
        </div>
      </Transition>
    </Teleport>
  </span>
</template>

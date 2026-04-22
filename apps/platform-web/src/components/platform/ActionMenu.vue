<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch, type CSSProperties } from 'vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import type { ActionMenuItem } from '@/components/platform/data-table'

const props = defineProps<{
  items: ActionMenuItem[]
}>()

const menuOpen = ref(false)
const triggerRef = ref<HTMLButtonElement | null>(null)
const menuRef = ref<HTMLElement | null>(null)
const menuPlacement = ref<'top' | 'bottom'>('bottom')
const menuStyle = ref<CSSProperties>({})

const visibleItems = computed(() => props.items.filter((item) => item))

function closeMenu() {
  menuOpen.value = false
}

function toggleMenu() {
  menuOpen.value = !menuOpen.value
}

function updateMenuPosition() {
  if (!menuOpen.value || !triggerRef.value) {
    return
  }

  const rect = triggerRef.value.getBoundingClientRect()
  const viewportPadding = 12
  const fallbackWidth = 208
  const menuWidth = Math.max(menuRef.value?.offsetWidth ?? 0, fallbackWidth)
  const menuHeight = menuRef.value?.offsetHeight ?? 240
  const spaceBelow = window.innerHeight - rect.bottom - viewportPadding
  const spaceAbove = rect.top - viewportPadding
  const placeOnTop = spaceBelow < menuHeight && spaceAbove > spaceBelow
  const alignedLeft = rect.right - menuWidth
  const clampedLeft = Math.min(
    Math.max(alignedLeft, viewportPadding),
    Math.max(viewportPadding, window.innerWidth - menuWidth - viewportPadding)
  )

  menuPlacement.value = placeOnTop ? 'top' : 'bottom'
  menuStyle.value = {
    position: 'fixed',
    left: `${clampedLeft}px`,
    top: placeOnTop ? 'auto' : `${rect.bottom + 8}px`,
    bottom: placeOnTop ? `${window.innerHeight - rect.top + 8}px` : 'auto',
    minWidth: `${Math.max(rect.width, 180)}px`,
    maxWidth: `${Math.max(240, window.innerWidth - viewportPadding * 2)}px`
  }
}

async function handleSelect(item: ActionMenuItem) {
  if (item.disabled) {
    return
  }

  closeMenu()
  await item.onSelect()
}

function handleClickOutside(event: MouseEvent) {
  const target = event.target as Node
  const clickedInsideTrigger = triggerRef.value?.contains(target)
  const clickedInsideMenu = menuRef.value?.contains(target)

  if (!clickedInsideTrigger && !clickedInsideMenu) {
    closeMenu()
  }
}

function handleViewportChange() {
  updateMenuPosition()
}

watch(menuOpen, (openState) => {
  if (!openState) {
    return
  }

  nextTick(() => {
    updateMenuPosition()
  })
})

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  window.addEventListener('resize', handleViewportChange)
  window.addEventListener('scroll', handleViewportChange, true)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
  window.removeEventListener('resize', handleViewportChange)
  window.removeEventListener('scroll', handleViewportChange, true)
})
</script>

<template>
  <div
    v-if="visibleItems.length"
    class="relative flex justify-end"
  >
    <button
      ref="triggerRef"
      type="button"
      class="pw-table-tool-button h-9 w-9 px-0"
      aria-label="更多操作"
      @click="toggleMenu"
    >
      <BaseIcon
        name="ellipsis-horizontal"
        size="sm"
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
          v-if="menuOpen"
          ref="menuRef"
          class="pw-data-table-menu"
          :class="menuPlacement === 'top' ? 'origin-bottom' : 'origin-top'"
          :style="menuStyle"
        >
          <button
            v-for="item in visibleItems"
            :key="item.key"
            type="button"
            class="pw-data-table-menu-item"
            :class="item.danger ? 'text-rose-600 dark:text-rose-300' : ''"
            :disabled="item.disabled"
            @click="handleSelect(item)"
          >
            <BaseIcon
              v-if="item.icon"
              :name="item.icon as never"
              size="sm"
            />
            <span>{{ item.label }}</span>
          </button>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

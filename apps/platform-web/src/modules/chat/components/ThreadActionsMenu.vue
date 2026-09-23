<script setup lang="ts">
import BaseIcon from '@/components/base/BaseIcon.vue'
import { useTopbarDropdown } from '@/composables/useTopbarDropdown'

withDefaults(
  defineProps<{
    focusMode?: boolean
    canTakeover?: boolean
    canDelete?: boolean
  }>(),
  {
    focusMode: false,
    canTakeover: false,
    canDelete: false
  }
)

const emit = defineEmits<{
  'toggle-focus': []
  'open-drawer': []
  'open-options': []
  'open-takeover': []
  'delete-thread': []
}>()

const {
  close,
  dropdownPlacement,
  dropdownRef,
  dropdownStyle,
  isOpen,
  rootRef,
  toggle,
  triggerRef
} = useTopbarDropdown({
  alignment: 'end',
  fallbackWidth: 176,
  minWidth: 176,
  offset: 6
})

function handleAction(action: 'focus' | 'drawer' | 'options' | 'takeover' | 'delete') {
  close()
  if (action === 'focus') emit('toggle-focus')
  else if (action === 'drawer') emit('open-drawer')
  else if (action === 'options') emit('open-options')
  else if (action === 'takeover') emit('open-takeover')
  else if (action === 'delete') emit('delete-thread')
}
</script>

<template>
  <div
    ref="rootRef"
    class="relative shrink-0"
  >
    <button
      ref="triggerRef"
      type="button"
      class="inline-flex h-7 w-7 items-center justify-center rounded-md border border-gray-200/70 bg-white text-gray-500 shadow-2xs hover:bg-gray-50 hover:text-gray-800 dark:border-dark-700/80 dark:bg-dark-900 dark:text-dark-300 dark:hover:text-white transition-colors"
      :class="isOpen ? 'bg-gray-100 dark:bg-dark-800 text-gray-800 dark:text-white' : ''"
      title="更多操作"
      aria-label="更多操作"
      @click="toggle"
    >
      <BaseIcon
        name="ellipsis-horizontal"
        size="xs"
      />
    </button>

    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="translate-y-1 opacity-0"
      enter-to-class="translate-y-0 opacity-100"
      leave-active-class="transition duration-120 ease-in"
      leave-from-class="translate-y-0 opacity-100"
      leave-to-class="translate-y-1 opacity-0"
    >
      <Teleport to="body">
        <div
          v-if="isOpen"
          ref="dropdownRef"
          class="pw-topbar-dropdown p-1"
          :class="dropdownPlacement === 'top' ? 'origin-bottom' : 'origin-top'"
          :style="dropdownStyle"
        >
          <button
            type="button"
            class="pw-dropdown-item text-xs"
            @click="handleAction('drawer')"
          >
            <BaseIcon
              name="overview"
              size="xs"
            />
            <span>会话详情与上下文</span>
          </button>

          <button
            type="button"
            class="pw-dropdown-item text-xs"
            @click="handleAction('options')"
          >
            <BaseIcon
              name="runtime"
              size="xs"
            />
            <span>运行参数配置</span>
          </button>

          <button
            type="button"
            class="pw-dropdown-item text-xs"
            @click="handleAction('focus')"
          >
            <BaseIcon
              name="focus"
              size="xs"
            />
            <span>{{ focusMode ? '退出专注模式' : '进入专注模式' }}</span>
          </button>

          <button
            v-if="canTakeover"
            type="button"
            class="pw-dropdown-item text-xs text-amber-700 dark:text-amber-300"
            @click="handleAction('takeover')"
          >
            <BaseIcon
              name="shield"
              size="xs"
            />
            <span>管理员临时接管</span>
          </button>

          <div
            v-if="canDelete"
            class="my-1 border-t border-gray-100 dark:border-dark-800"
          />

          <button
            v-if="canDelete"
            type="button"
            class="pw-dropdown-item text-xs text-rose-600 hover:bg-rose-50 dark:text-rose-400 dark:hover:bg-rose-950/30"
            @click="handleAction('delete')"
          >
            <BaseIcon
              name="trash"
              size="xs"
            />
            <span>删除当前会话</span>
          </button>
        </div>
      </Teleport>
    </Transition>
  </div>
</template>

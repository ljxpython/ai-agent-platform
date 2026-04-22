<script setup lang="ts">
import { computed, onMounted } from 'vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import { useGuidesStore } from '@/stores/guides'

const props = withDefaults(
  defineProps<{
    guideId: string
    title: string
    description: string
    tone?: 'info' | 'warning' | 'success'
    dismissible?: boolean
  }>(),
  {
    tone: 'info',
    dismissible: true
  }
)

const guidesStore = useGuidesStore()

onMounted(() => {
  guidesStore.init()
})

const visible = computed(() => !guidesStore.isDismissed(props.guideId))

function toneClass() {
  if (props.tone === 'warning') {
    return {
      wrapper: 'border-amber-100 bg-amber-50/75 dark:border-amber-900/40 dark:bg-amber-950/20',
      icon: 'text-amber-600 dark:text-amber-300',
      chip: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-200'
    }
  }
  if (props.tone === 'success') {
    return {
      wrapper: 'border-emerald-100 bg-emerald-50/75 dark:border-emerald-900/40 dark:bg-emerald-950/20',
      icon: 'text-emerald-600 dark:text-emerald-300',
      chip: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-200'
    }
  }
  return {
    wrapper: 'border-sky-100 bg-sky-50/75 dark:border-sky-900/40 dark:bg-sky-950/20',
    icon: 'text-sky-600 dark:text-sky-300',
    chip: 'bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-200'
  }
}

function dismiss() {
  guidesStore.dismiss(props.guideId)
}
</script>

<template>
  <div
    v-if="visible"
    class="rounded-2xl border px-4 py-4 shadow-sm"
    :class="toneClass().wrapper"
  >
    <div class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
      <div class="min-w-0 flex-1">
        <div class="flex items-center gap-3">
          <div class="flex h-9 w-9 items-center justify-center rounded-xl border border-white/70 bg-white dark:border-white/10 dark:bg-dark-900">
            <BaseIcon
              name="info"
              size="sm"
              :class="toneClass().icon"
            />
          </div>
          <div>
            <div class="text-sm font-semibold text-gray-900 dark:text-white">
              {{ title }}
            </div>
            <div
              class="mt-1 inline-flex rounded-full px-2.5 py-1 text-[11px] font-semibold"
              :class="toneClass().chip"
            >
              引导
            </div>
          </div>
        </div>
        <p class="mt-3 text-sm leading-7 text-gray-600 dark:text-dark-200">
          {{ description }}
        </p>
        <div
          v-if="$slots.actions"
          class="mt-4 flex flex-wrap gap-2.5"
        >
          <slot name="actions" />
        </div>
      </div>

      <button
        v-if="dismissible"
        type="button"
        class="inline-flex h-9 w-9 items-center justify-center rounded-xl text-gray-400 transition-colors hover:bg-white hover:text-gray-700 dark:hover:bg-dark-900 dark:hover:text-dark-100"
        aria-label="关闭引导"
        @click="dismiss"
      >
        <BaseIcon
          name="x"
          size="sm"
        />
      </button>
    </div>
  </div>
</template>

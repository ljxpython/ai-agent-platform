<script setup lang="ts">
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import SurfaceCard from '@/components/base/SurfaceCard.vue'

withDefaults(
  defineProps<{
    title: string
    description: string
    icon?: string
    actionLabel?: string
  }>(),
  {
    icon: 'sparkle',
    actionLabel: ''
  }
)

defineEmits<{
  action: []
}>()
</script>

<template>
  <SurfaceCard>
    <div class="pw-empty-state">
      <div class="pw-empty-state-icon">
        <BaseIcon
          :name="icon as never"
          size="lg"
        />
      </div>
      <h2 class="text-lg font-semibold text-slate-900 dark:text-white">
        {{ title }}
      </h2>
      <p class="mt-3 max-w-md text-sm leading-7 text-slate-500 dark:text-dark-300">
        {{ description }}
      </p>
      <BaseButton
        v-if="actionLabel"
        class="mt-6"
        @click="$emit('action')"
      >
        {{ actionLabel }}
      </BaseButton>
    </div>
  </SurfaceCard>
</template>

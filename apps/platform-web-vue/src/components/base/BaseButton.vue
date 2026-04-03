<script setup lang="ts">
withDefaults(
  defineProps<{
    type?: 'button' | 'submit' | 'reset'
    variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
    block?: boolean
    disabled?: boolean
  }>(),
  {
    type: 'button',
    variant: 'primary',
    block: false,
    disabled: false
  }
)
</script>

<template>
  <button
    :type="type"
    :disabled="disabled"
    class="pw-btn"
    :class="[
      block ? 'w-full' : '',
      variant === 'primary'
        ? 'pw-btn-primary'
        : variant === 'secondary'
          ? 'pw-btn-secondary'
          : variant === 'danger'
            ? 'pw-btn-danger'
            : 'pw-btn-ghost'
    ]"
  >
    <slot />
  </button>
</template>

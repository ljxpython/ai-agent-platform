<script setup lang="ts">
withDefaults(
  defineProps<{
    type?: "button" | "submit" | "reset";
    variant?: "primary" | "secondary" | "ghost" | "danger";
    size?: "xs" | "sm" | "md" | "lg";
    block?: boolean;
    disabled?: boolean;
  }>(),
  {
    type: "button",
    variant: "primary",
    size: "md",
    block: false,
    disabled: false,
  },
);
</script>

<template>
  <button
    :type="type"
    :disabled="disabled"
    class="pw-btn whitespace-nowrap shrink-0"
    :class="[
      block ? 'w-full' : '',
      size === 'xs'
        ? '!px-2 !py-1 !text-xs !gap-1 !rounded-lg'
        : size === 'sm'
          ? '!px-3 !py-1.5 !text-xs !gap-1.5 !rounded-lg'
          : size === 'lg'
            ? '!px-5 !py-3 !text-base !gap-2.5 !rounded-2xl'
            : '',
      variant === 'primary'
        ? 'pw-btn-primary'
        : variant === 'secondary'
          ? 'pw-btn-secondary'
          : variant === 'danger'
            ? 'pw-btn-danger'
            : 'pw-btn-ghost',
    ]"
  >
    <slot />
  </button>
</template>

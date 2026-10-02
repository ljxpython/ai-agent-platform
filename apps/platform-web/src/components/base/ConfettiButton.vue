<script setup lang="ts">
import confetti from "canvas-confetti";

const props = withDefaults(
  defineProps<{
    angle?: number;
    particleCount?: number;
    startVelocity?: number;
    spread?: number;
    disabled?: boolean;
    type?: "button" | "submit" | "reset";
  }>(),
  {
    angle: 90,
    particleCount: 65,
    startVelocity: 32,
    spread: 65,
    disabled: false,
    type: "button",
  },
);

const emit = defineEmits<{
  click: [event: MouseEvent];
}>();

function handleClick(event: MouseEvent) {
  if (props.disabled) return;
  const target = event.currentTarget as HTMLElement | null;
  if (target && typeof window !== "undefined") {
    const rect = target.getBoundingClientRect();
    confetti({
      particleCount: props.particleCount,
      startVelocity: props.startVelocity,
      angle: props.angle,
      spread: props.spread,
      origin: {
        x: (rect.left + rect.width / 2) / window.innerWidth,
        y: (rect.top + rect.height / 2) / window.innerHeight,
      },
      colors: [
        "#3b82f6",
        "#10b981",
        "#f59e0b",
        "#ef4444",
        "#8b5cf6",
        "#ec4899",
      ],
      disableForReducedMotion: true,
    });
  }
  emit("click", event);
}
</script>

<template>
  <button
    :type="type"
    :disabled="disabled"
    class="inline-flex items-center justify-center transition-all select-none disabled:opacity-50 disabled:cursor-not-allowed active:scale-95 cursor-pointer"
    @click="handleClick"
  >
    <slot />
  </button>
</template>

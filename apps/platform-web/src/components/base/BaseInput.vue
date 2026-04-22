<script setup lang="ts">
defineProps<{
  modelValue: string
  type?: string
  placeholder?: string
  autocomplete?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()
</script>

<template>
  <input
    :value="modelValue"
    :type="type || 'text'"
    :placeholder="placeholder"
    :autocomplete="autocomplete"
    class="pw-input"
    @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
  >
</template>

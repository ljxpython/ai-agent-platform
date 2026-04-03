<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseIcon from '@/components/base/BaseIcon.vue'
import { useThemeStore } from '@/stores/theme'

const { t } = useI18n()
const themeStore = useThemeStore()

const label = computed(() =>
  themeStore.mode === 'dark' ? t('common.lightMode') : t('common.darkMode')
)
</script>

<template>
  <button
    type="button"
    class="pw-btn pw-btn-secondary"
    @click="themeStore.toggleMode"
  >
    <BaseIcon
      :name="themeStore.mode === 'dark' ? 'sun' : 'moon'"
      size="sm"
    />
    <span>{{ label }}</span>
  </button>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseIcon from '@/components/base/BaseIcon.vue'
import { useTopbarDropdown } from '@/composables/useTopbarDropdown'
import { availableLocales, setLocale, type LocaleCode } from '@/i18n'
import { useUiStore } from '@/stores/ui'

const { locale, t } = useI18n()
const uiStore = useUiStore()
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
  minWidth: 176
})
const currentLocale = computed(() => availableLocales.find((item) => item.code === locale.value) ?? availableLocales[0])

function selectLocale(localeCode: LocaleCode) {
  if (localeCode === locale.value) {
    close()
    return
  }

  setLocale(localeCode)
  uiStore.pushToast({
    type: 'success',
    title: t('toast.localeUpdated'),
    message: t('toast.localeUpdatedDesc')
  })
  close()
}
</script>

<template>
  <div
    ref="rootRef"
    class="relative"
  >
    <button
      ref="triggerRef"
      type="button"
      class="pw-topbar-action"
      :class="isOpen ? 'pw-topbar-action-active' : ''"
      :aria-label="t('topbar.language')"
      @click="toggle"
    >
      <BaseIcon
        name="globe"
        size="sm"
        class="text-gray-400 dark:text-dark-400"
      />
      <span class="hidden text-sm font-medium sm:inline">{{ currentLocale.shortLabel }}</span>
      <BaseIcon
        name="chevron-down"
        size="xs"
        class="text-gray-400 transition"
        :class="isOpen ? 'rotate-180' : ''"
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
          class="pw-topbar-dropdown"
          :class="dropdownPlacement === 'top' ? 'origin-bottom' : 'origin-top'"
          :style="dropdownStyle"
        >
          <button
            v-for="item in availableLocales"
            :key="item.code"
            type="button"
            class="pw-dropdown-item"
            @click="selectLocale(item.code)"
          >
            <span class="font-medium">{{ item.name }}</span>
            <BaseIcon
              v-if="item.code === locale"
              name="check"
              size="sm"
              class="ml-auto text-primary-500"
            />
          </button>
        </div>
      </Teleport>
    </Transition>
  </div>
</template>

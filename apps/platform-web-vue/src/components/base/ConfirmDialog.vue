<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseDialog from '@/components/base/BaseDialog.vue'

const props = withDefaults(
  defineProps<{
    show: boolean
    title: string
    message: string
    confirmText?: string
    cancelText?: string
    danger?: boolean
  }>(),
  {
    confirmText: '',
    cancelText: '',
    danger: false
  }
)

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()

const { t } = useI18n()

const resolvedConfirmText = computed(() => props.confirmText || t('common.confirm'))
const resolvedCancelText = computed(() => props.cancelText || t('common.cancel'))
</script>

<template>
  <BaseDialog
    :show="show"
    :title="title"
    width="narrow"
    @close="emit('cancel')"
  >
    <p class="text-sm leading-7 text-gray-600 dark:text-dark-300">
      {{ message }}
    </p>

    <template #footer>
      <div class="flex items-center gap-3">
        <BaseButton
          variant="secondary"
          @click="emit('cancel')"
        >
          {{ resolvedCancelText }}
        </BaseButton>
        <BaseButton
          :variant="danger ? 'danger' : 'primary'"
          @click="emit('confirm')"
        >
          {{ resolvedConfirmText }}
        </BaseButton>
      </div>
    </template>
  </BaseDialog>
</template>

<template>
  <Teleport to="body">
    <Transition name="sora-modal">
      <div v-if="visible && generation" class="sora-download-overlay" @click.self="emit('close')">
        <div class="sora-download-backdrop" />
        <div class="sora-download-modal" @click.stop>
          <div class="sora-download-modal-icon">📥</div>
          <h3 class="sora-download-modal-title">{{ t('sora.downloadTitle') }}</h3>
          <p class="sora-download-modal-desc">{{ t('sora.downloadExpirationWarning') }}</p>

          <!-- 倒计时 -->
          <div v-if="remainingText" class="sora-download-countdown">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span :class="{ expired: isExpired }">
              {{ isExpired ? t('sora.upstreamExpired') : t('sora.upstreamCountdown', { time: remainingText }) }}
            </span>
          </div>

          <div class="sora-download-modal-actions">
            <a
              v-if="generation.media_url"
              :href="generation.media_url"
              target="_blank"
              download
              class="sora-download-btn primary"
            >
              {{ t('sora.downloadNow') }}
            </a>
            <button class="sora-download-btn ghost" @click="emit('close')">
              {{ t('sora.closePreview') }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import type { SoraGeneration } from '@/api/sora'

const EXPIRATION_MINUTES = 15

const props = defineProps<{
  visible: boolean
  generation: SoraGeneration | null
}>()

const emit = defineEmits<{ close: [] }>()
const { t } = useI18n()

const now = ref(Date.now())
let timer: ReturnType<typeof setInterval> | null = null

const expiresAt = computed(() => {
  if (!props.generation?.completed_at) return null
  return new Date(props.generation.completed_at).getTime() + EXPIRATION_MINUTES * 60 * 1000
})

const isExpired = computed(() => {
  if (!expiresAt.value) return false
  return now.value >= expiresAt.value
})

const remainingText = computed(() => {
  if (!expiresAt.value) return ''
  const diff = expiresAt.value - now.value
  if (diff <= 0) return ''
  const minutes = Math.floor(diff / 60000)
  const seconds = Math.floor((diff % 60000) / 1000)
  return `${minutes}:${String(seconds).padStart(2, '0')}`
})

watch(
  () => props.visible,
  (v) => {
    if (v) {
      now.value = Date.now()
      timer = setInterval(() => { now.value = Date.now() }, 1000)
    } else if (timer) {
      clearInterval(timer)
      timer = null
    }
  },
  { immediate: true }
)

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.sora-download-overlay {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
}

.sora-download-backdrop {
  position: absolute;
  inset: 0;
  background: var(--sora-modal-backdrop, rgba(0, 0, 0, 0.4));
  backdrop-filter: blur(4px);
}

.sora-download-modal {
  position: relative;
  z-index: 10;
  background: var(--sora-bg-secondary, #FFF);
  border: 1px solid var(--sora-border-color, #E5E7EB);
  border-radius: 20px;
  padding: 32px;
  max-width: 420px;
  width: 90%;
  text-align: center;
  animation: sora-modal-in 0.3s ease;
}

@keyframes sora-modal-in {
  from { transform: scale(0.95); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}

.sora-download-modal-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.sora-download-modal-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--sora-text-primary, #111827);
  margin-bottom: 8px;
}

.sora-download-modal-desc {
  font-size: 14px;
  color: var(--sora-text-secondary, #6B7280);
  margin-bottom: 20px;
  line-height: 1.6;
}

.sora-download-countdown {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: 14px;
  color: var(--sora-text-secondary, #6B7280);
  margin-bottom: 24px;
}

.sora-download-countdown svg {
  color: var(--sora-text-tertiary, #9CA3AF);
}

.sora-download-countdown .expired {
  color: #EF4444;
}

.sora-download-modal-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}

.sora-download-btn {
  padding: 10px 24px;
  border-radius: 9999px;
  font-size: 14px;
  font-weight: 500;
  border: none;
  cursor: pointer;
  transition: all 150ms ease;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.sora-download-btn.primary {
  background: var(--sora-accent-gradient);
  color: white;
}

.sora-download-btn.primary:hover {
  box-shadow: var(--sora-shadow-glow);
}

.sora-download-btn.ghost {
  background: var(--sora-bg-tertiary, #F3F4F6);
  color: var(--sora-text-secondary, #6B7280);
}

.sora-download-btn.ghost:hover {
  background: var(--sora-bg-hover, #E5E7EB);
  color: var(--sora-text-primary, #111827);
}

/* 过渡 */
.sora-modal-enter-active,
.sora-modal-leave-active {
  transition: opacity 0.2s ease;
}
.sora-modal-enter-from,
.sora-modal-leave-to {
  opacity: 0;
}
</style>

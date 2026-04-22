<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const visible = ref(false)

let hideTimer: number | null = null
let safetyTimer: number | null = null
let removeBeforeEach: (() => void) | null = null
let removeAfterEach: (() => void) | null = null
let removeOnError: (() => void) | null = null

function clearTimers() {
  if (typeof window === 'undefined') {
    return
  }

  if (hideTimer !== null) {
    window.clearTimeout(hideTimer)
    hideTimer = null
  }

  if (safetyTimer !== null) {
    window.clearTimeout(safetyTimer)
    safetyTimer = null
  }
}

function startProgress() {
  if (typeof window === 'undefined') {
    return
  }

  clearTimers()
  visible.value = true
  safetyTimer = window.setTimeout(() => {
    visible.value = false
    safetyTimer = null
  }, 1800)
}

function finishProgress() {
  if (typeof window === 'undefined') {
    visible.value = false
    return
  }

  clearTimers()
  hideTimer = window.setTimeout(() => {
    visible.value = false
    hideTimer = null
  }, 220)
}

function resetProgress() {
  clearTimers()
  visible.value = false
}

onMounted(() => {
  removeBeforeEach = router.beforeEach(() => {
    startProgress()
  })

  removeAfterEach = router.afterEach(() => {
    finishProgress()
  })

  removeOnError = router.onError(() => {
    resetProgress()
  })
})

onBeforeUnmount(() => {
  clearTimers()
  removeBeforeEach?.()
  removeAfterEach?.()
  removeOnError?.()
})
</script>

<template>
  <Transition
    enter-active-class="transition duration-150 ease-out"
    enter-from-class="opacity-0"
    enter-to-class="opacity-100"
    leave-active-class="transition duration-200 ease-out"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0"
  >
    <div
      v-if="visible"
      class="pw-navigation-progress"
      role="progressbar"
      aria-label="Navigation loading"
    >
      <div class="pw-navigation-progress-bar" />
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseIcon from '@/components/base/BaseIcon.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import { useWorkspaceProjectContext } from '@/composables/useWorkspaceProjectContext'
import { useAnnouncementsStore } from '@/stores/announcements'
import { useUiStore } from '@/stores/ui'

const { t } = useI18n()
const announcementsStore = useAnnouncementsStore()
const uiStore = useUiStore()
const { workspaceStore, activeProjectId } = useWorkspaceProjectContext()

const isOpen = ref(false)
const rootRef = ref<HTMLElement | null>(null)
const selectedAnnouncementId = ref('')

const items = computed(() => announcementsStore.items)
const unreadCount = computed(() => announcementsStore.unreadCount)
const loading = computed(() => announcementsStore.loading)
const sourceHint = computed(() => {
  if (announcementsStore.mode === 'initial') {
    return ''
  }

  return announcementsStore.mode === 'remote'
    ? t('topbar.announcementsLiveHint')
    : t('topbar.announcementsDemoHint')
})
const selectedAnnouncement = computed(() => {
  const selectedId = selectedAnnouncementId.value || items.value[0]?.id || ''
  return items.value.find((item) => item.id === selectedId) || null
})

function formatAnnouncementTime(value: string) {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }
  return parsed.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function toneClasses(tone: 'info' | 'warning' | 'success'): {
  dot: string
  card: string
  icon: 'alert' | 'check' | 'info'
} {
  if (tone === 'warning') {
    return {
      dot: 'bg-amber-500',
      card: 'border-amber-100 bg-amber-50/80 text-amber-800 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-100',
      icon: 'alert'
    }
  }
  if (tone === 'success') {
    return {
      dot: 'bg-emerald-500',
      card: 'border-emerald-100 bg-emerald-50/80 text-emerald-800 dark:border-emerald-900/40 dark:bg-emerald-950/20 dark:text-emerald-100',
      icon: 'check'
    }
  }
  return {
    dot: 'bg-sky-500',
    card: 'border-sky-100 bg-sky-50/80 text-sky-800 dark:border-sky-900/40 dark:bg-sky-950/20 dark:text-sky-100',
    icon: 'info'
  }
}

function close() {
  isOpen.value = false
}

function toggle() {
  isOpen.value = !isOpen.value
  if (isOpen.value) {
    selectedAnnouncementId.value = items.value[0]?.id || ''
  }
}

function handleClickOutside(event: MouseEvent) {
  if (rootRef.value && !rootRef.value.contains(event.target as Node)) {
    close()
  }
}

onMounted(() => {
  if (!workspaceStore.projects.length) {
    void workspaceStore.hydrateContext().then(() =>
      announcementsStore.init(activeProjectId.value)
    )
  } else {
    void announcementsStore.init(activeProjectId.value)
  }
  document.addEventListener('click', handleClickOutside)
})

watch(
  activeProjectId,
  (projectId) => {
    void announcementsStore.load(String(projectId || ''))
  }
)

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
})

async function selectAnnouncement(id: string) {
  selectedAnnouncementId.value = id
  await announcementsStore.markRead(id)
}

async function markAllRead() {
  await announcementsStore.markAllRead(activeProjectId.value)
  uiStore.pushToast({
    type: 'success',
    title: t('topbar.announcementsMarked'),
    message: t('topbar.announcementsMarkedDesc')
  })
}
</script>

<template>
  <div
    ref="rootRef"
    class="relative"
  >
    <button
      type="button"
      class="pw-topbar-action w-9 px-0"
      :class="isOpen ? 'pw-topbar-action-active' : ''"
      :aria-label="t('topbar.announcements')"
      @click="toggle"
    >
      <span class="relative flex items-center justify-center">
        <BaseIcon
          name="bell"
          size="sm"
        />
        <span
          v-if="unreadCount > 0"
          class="absolute -right-1 -top-1 flex min-h-4 min-w-4 items-center justify-center rounded-full bg-sky-500 px-1 text-[10px] font-semibold text-white ring-2 ring-white dark:ring-dark-900"
        >
          {{ unreadCount > 9 ? '9+' : unreadCount }}
        </span>
      </span>
    </button>

    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="translate-y-1 opacity-0"
      enter-to-class="translate-y-0 opacity-100"
      leave-active-class="transition duration-120 ease-in"
      leave-from-class="translate-y-0 opacity-100"
      leave-to-class="translate-y-1 opacity-0"
    >
      <div
        v-if="isOpen"
        class="pw-topbar-dropdown right-0 mt-3 w-[min(360px,calc(100vw-1.5rem))] p-0"
      >
        <div class="border-b border-gray-100 px-4 py-3 dark:border-dark-800">
          <div class="flex items-center justify-between gap-3">
            <div>
              <div class="text-sm font-semibold text-gray-900 dark:text-white">
                {{ t('topbar.announcements') }}
              </div>
              <div class="mt-1 text-xs text-gray-500 dark:text-dark-400">
                {{
                  unreadCount > 0
                    ? t('topbar.announcementsUnread', { count: unreadCount })
                    : t('topbar.noUnread')
                }}
              </div>
              <div
                v-if="sourceHint"
                class="mt-1 text-[11px] text-gray-400 dark:text-dark-500"
              >
                {{ sourceHint }}
              </div>
            </div>
            <BaseButton
              variant="ghost"
              :disabled="loading || unreadCount === 0"
              @click="markAllRead"
            >
              {{ t('topbar.markAllRead') }}
            </BaseButton>
          </div>
        </div>
        <div class="grid gap-4 px-4 py-4">
          <div
            v-if="loading"
            class="rounded-2xl border border-dashed border-gray-200 px-4 py-6 text-sm leading-7 text-gray-500 dark:border-dark-700 dark:text-dark-300"
          >
            正在同步公告列表...
          </div>
          <div
            v-else-if="items.length"
            class="grid gap-2"
          >
            <button
              v-for="item in items"
              :key="item.id"
              type="button"
              class="rounded-xl border px-4 py-3 text-left transition-colors"
              :class="
                selectedAnnouncement?.id === item.id
                  ? 'border-primary-200 bg-primary-50 dark:border-primary-900/40 dark:bg-primary-950/20'
                  : 'border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50 dark:border-dark-700 dark:bg-dark-900 dark:hover:bg-dark-800'
              "
              @click="selectAnnouncement(item.id)"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <div class="truncate text-sm font-semibold text-gray-900 dark:text-white">
                    {{ item.title }}
                  </div>
                  <div class="mt-1 text-xs leading-6 text-gray-500 dark:text-dark-300">
                    {{ item.summary }}
                  </div>
                </div>
                <span
                  class="mt-1 inline-flex h-2.5 w-2.5 shrink-0 rounded-full"
                  :class="announcementsStore.isRead(item.id) ? 'bg-gray-300 dark:bg-dark-500' : toneClasses(item.tone).dot"
                />
              </div>
              <div class="mt-2 text-[11px] text-gray-400 dark:text-dark-500">
                {{ formatAnnouncementTime(item.createdAt) }}
              </div>
            </button>
          </div>
          <div
            v-else
            class="rounded-2xl border border-dashed border-gray-200 px-4 py-6 text-sm leading-7 text-gray-500 dark:border-dark-700 dark:text-dark-300"
          >
            <div class="font-semibold text-gray-900 dark:text-white">
              {{ t('topbar.announcementsEmptyTitle') }}
            </div>
            <p class="mt-2">
              {{ t('topbar.announcementsEmptyDescription') }}
            </p>
          </div>

          <div
            v-if="!loading && selectedAnnouncement"
            class="rounded-2xl border px-4 py-4 shadow-sm"
            :class="toneClasses(selectedAnnouncement.tone).card"
          >
            <div class="flex items-start gap-3">
              <div class="mt-0.5 flex h-10 w-10 items-center justify-center rounded-2xl bg-white/60 text-current dark:bg-black/10">
                <BaseIcon
                  :name="toneClasses(selectedAnnouncement.tone).icon"
                  size="sm"
                />
              </div>
              <div class="min-w-0">
                <div class="text-sm font-semibold text-gray-900 dark:text-white">
                  {{ selectedAnnouncement.title }}
                </div>
                <p class="mt-1 text-sm leading-6 text-gray-500 dark:text-dark-300">
                  {{ selectedAnnouncement.body }}
                </p>
                <div class="mt-3 text-[11px] text-gray-400 dark:text-dark-500">
                  {{ sourceHint || t('topbar.announcements') }} · {{ formatAnnouncementTime(selectedAnnouncement.createdAt) }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

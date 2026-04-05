<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { toPrettyJson } from '@/utils/threads'

type ArtifactEntry = {
  id?: string
  metadata?: Record<string, unknown>
  [key: string]: unknown
}

const props = defineProps<{
  values?: Record<string, unknown> | null
}>()

const selectedEntryId = ref('')

const entries = computed<ArtifactEntry[]>(() => {
  const rawEntries = props.values?.ui
  return Array.isArray(rawEntries)
    ? rawEntries.filter((item): item is ArtifactEntry => Boolean(item && typeof item === 'object'))
    : []
})

const selectedEntry = computed(() => {
  return (
    entries.value.find((item, index) => {
      const currentId = typeof item.id === 'string' && item.id.trim() ? item.id : `ui-${index + 1}`
      return currentId === selectedEntryId.value
    }) || entries.value[0] || null
  )
})

watch(
  () => entries.value,
  (nextEntries) => {
    if (nextEntries.length === 0) {
      selectedEntryId.value = ''
      return
    }

    const hasMatched = nextEntries.some((item, index) => {
      const currentId = typeof item.id === 'string' && item.id.trim() ? item.id : `ui-${index + 1}`
      return currentId === selectedEntryId.value
    })

    if (!hasMatched) {
      const first = nextEntries[0]
      selectedEntryId.value =
        typeof first.id === 'string' && first.id.trim() ? first.id : 'ui-1'
    }
  },
  { immediate: true, deep: true }
)

function entryId(entry: ArtifactEntry, index: number) {
  return typeof entry.id === 'string' && entry.id.trim() ? entry.id : `ui-${index + 1}`
}

function entryTitle(entry: ArtifactEntry, index: number) {
  const metadata = entry.metadata && typeof entry.metadata === 'object' ? entry.metadata : {}
  const title = (metadata as Record<string, unknown>).title
  if (typeof title === 'string' && title.trim()) {
    return title.trim()
  }

  const messageId = (metadata as Record<string, unknown>).message_id
  if (typeof messageId === 'string' && messageId.trim()) {
    return `Message ${messageId.slice(0, 8)}`
  }

  return `Artifact ${index + 1}`
}
</script>

<template>
  <aside class="flex h-full min-h-0 flex-col border-l border-gray-100 bg-slate-50/65 dark:border-dark-800 dark:bg-dark-950/55">
    <div class="border-b border-gray-100 px-5 py-4 dark:border-dark-800">
      <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
        Artifacts
      </div>
      <div class="mt-1 text-sm font-semibold text-gray-900 dark:text-white">
        生成式 UI 承载位
      </div>
      <div class="mt-1 text-xs leading-6 text-gray-500 dark:text-dark-300">
        当前先展示线程状态里的 `ui` 条目与元信息，后面继续往这里挂更完整的 artifact 视图。
      </div>
    </div>

    <div class="grid min-h-0 flex-1 lg:grid-cols-[180px_minmax(0,1fr)]">
      <div class="min-h-0 overflow-y-auto border-b border-gray-100 px-3 py-3 dark:border-dark-800 lg:border-b-0 lg:border-r">
        <div class="space-y-2">
          <button
            v-for="(entry, index) in entries"
            :key="entryId(entry, index)"
            type="button"
            class="block w-full rounded-2xl border px-3 py-3 text-left transition"
            :class="
              entryId(entry, index) === selectedEntryId
                ? 'border-primary-200 bg-white text-gray-900 shadow-soft dark:border-primary-900/40 dark:bg-dark-800 dark:text-white'
                : 'border-transparent text-gray-500 hover:border-gray-200 hover:bg-white/70 hover:text-gray-900 dark:text-dark-300 dark:hover:border-dark-700 dark:hover:bg-dark-800 dark:hover:text-white'
            "
            @click="selectedEntryId = entryId(entry, index)"
          >
            <div class="truncate text-sm font-semibold">
              {{ entryTitle(entry, index) }}
            </div>
            <div class="mt-1 truncate text-xs opacity-70">
              {{ entryId(entry, index) }}
            </div>
          </button>
        </div>
      </div>

      <div class="min-h-0 overflow-y-auto px-4 py-4">
        <div
          v-if="selectedEntry"
          class="space-y-4"
        >
          <div class="rounded-2xl border border-white/80 bg-white/90 p-4 dark:border-dark-700 dark:bg-dark-900/80">
            <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
              Metadata
            </div>
            <pre class="mt-3 overflow-auto whitespace-pre-wrap break-words text-xs leading-6 text-gray-700 dark:text-dark-100">{{ toPrettyJson(selectedEntry.metadata || {}) }}</pre>
          </div>

          <div class="rounded-2xl border border-white/80 bg-white/90 p-4 dark:border-dark-700 dark:bg-dark-900/80">
            <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
              Raw Payload
            </div>
            <pre class="mt-3 overflow-auto whitespace-pre-wrap break-words text-xs leading-6 text-gray-700 dark:text-dark-100">{{ toPrettyJson(selectedEntry) }}</pre>
          </div>
        </div>

        <div
          v-else
          class="text-sm leading-7 text-gray-500 dark:text-dark-300"
        >
          当前线程还没有可展示的 artifact。
        </div>
      </div>
    </div>
  </aside>
</template>

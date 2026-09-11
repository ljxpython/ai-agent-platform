<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import type { ChatThreadStatusFilter, ChatThreadSummaryGroup } from '../thread-list-view-model'

type ThreadStatusFilterOption = {
  value: ChatThreadStatusFilter
  label: string
}

const props = defineProps<{
  showContextBar: boolean
  targetText: string
  targetTypeText: string
  search: string
  statusFilter: ChatThreadStatusFilter
  filters: readonly ThreadStatusFilterOption[]
  loading: boolean
  threadCount: number
  filteredCount: number
  canStartThread: boolean
  activeThreadId: string
  deletingThreadId: string
  groups: ChatThreadSummaryGroup[]
  hasMore?: boolean
  canDelete?: boolean
}>()

const emit = defineEmits<{
  'update:search': [value: string]
  'update:statusFilter': [value: ChatThreadStatusFilter]
  'start-new-thread': []
  'select-thread': [threadId: string]
  'delete-thread': [threadId: string]
  'collapse': []
  'load-more': []
}>()

const searchModel = computed({
  get: () => props.search,
  set: (value: string) => emit('update:search', value)
})

const currentPage = ref(1)
const pageSize = 10

watch(() => props.filteredCount, () => { currentPage.value = Math.min(currentPage.value, Math.max(1, Math.ceil(props.filteredCount / pageSize))) })

const totalPages = computed(() => Math.max(1, Math.ceil(props.filteredCount / pageSize)))

watch([() => props.search, () => props.statusFilter], () => {
  currentPage.value = 1
})

const paginatedGroups = computed(() => {
  let currentItemIndex = 0
  const start = (currentPage.value - 1) * pageSize
  const end = start + pageSize
  const result: ChatThreadSummaryGroup[] = []

  for (const group of props.groups) {
    const groupItems: typeof group.items = []
    for (const item of group.items) {
      if (currentItemIndex >= start && currentItemIndex < end) {
        groupItems.push(item)
      }
      currentItemIndex++
    }
    if (groupItems.length > 0) {
      result.push({
        ...group,
        items: groupItems
      })
    }
  }
  return result
})
</script>

<template>
  <aside
    aria-label="对话列表"
    class="w-72 lg:w-80 border-r border-gray-200 dark:border-dark-800 bg-white dark:bg-dark-900 flex flex-col h-full shrink-0"
  >
    <!-- Header: Search and New Thread -->
    <div class="p-4 border-b border-gray-200 dark:border-dark-800 shrink-0">
      <div class="flex items-center gap-2 mb-3">
        <BaseInput
          v-model="searchModel"
          placeholder="搜索会话..."
          class="flex-1"
        />
        <button
          type="button"
          class="pw-topbar-action h-9 px-2.5 shrink-0"
          :disabled="!canStartThread"
          title="新建会话"
          @click="emit('start-new-thread')"
        >
          <BaseIcon
            name="chat"
            size="sm"
          />
        </button>
        <button
          type="button"
          class="pw-topbar-action h-9 px-2.5 shrink-0 text-gray-500 hover:text-gray-900 dark:text-dark-400 dark:hover:text-white"
          title="收起历史会话"
          @click="emit('collapse')"
        >
          <BaseIcon
            name="chevron-left"
            size="sm"
          />
        </button>
      </div>
      
      <div class="flex flex-wrap gap-2">
        <button
          v-for="filter in filters"
          :key="filter.value"
          type="button"
          class="pw-table-tool-button text-[11px] px-2 py-1"
          :class="statusFilter === filter.value ? 'bg-gray-100 dark:bg-dark-800 text-gray-900 dark:text-white font-medium' : ''"
          @click="emit('update:statusFilter', filter.value)"
        >
          {{ filter.label }}
        </button>
      </div>
    </div>

    <!-- Scrollable Thread List -->
    <div class="flex-1 overflow-y-auto p-3 space-y-4">
      <div
        v-if="loading && threadCount === 0"
        class="space-y-3"
      >
        <div
          v-for="index in 4"
          :key="index"
          class="pw-panel-muted h-20 animate-pulse rounded-lg"
        />
      </div>

      <div
        v-else-if="threadCount === 0"
        class="p-4 text-center text-sm text-gray-500 dark:text-dark-400"
      >
        无会话记录，发送消息将自动创建。
      </div>

      <div
        v-else-if="filteredCount === 0"
        class="p-4 text-center text-sm text-gray-500 dark:text-dark-400"
      >
        没有匹配的会话。
      </div>

      <div
        v-else
        class="space-y-5"
      >
        <div
          v-for="group in paginatedGroups"
          :key="group.key"
          class="space-y-2"
        >
          <div class="px-2 text-[10px] font-bold uppercase tracking-wider text-gray-400 dark:text-dark-500">
            {{ group.label }}
          </div>

          <div class="space-y-1">
            <div
              v-for="item in group.items"
              :key="item.id"
              class="group relative"
            >
              <button
                type="button"
                class="w-full rounded-lg px-3 py-2.5 text-left transition-colors flex flex-col gap-1"
                :class="
                  item.id === activeThreadId
                    ? 'bg-primary-50 dark:bg-primary-950/30 border border-primary-100 dark:border-primary-900/50'
                    : 'border border-transparent hover:bg-gray-50 dark:hover:bg-dark-800/50'
                "
                :aria-label="item.title"
                @click="emit('select-thread', item.id)"
              >
                <div class="flex items-start justify-between gap-2">
                  <div
                    class="truncate text-sm font-medium"
                    :class="item.id === activeThreadId ? 'text-primary-900 dark:text-primary-100' : 'text-gray-900 dark:text-gray-100'"
                  >
                    {{ item.title }}
                  </div>
                </div>
                
                <div class="line-clamp-2 text-xs text-gray-500 dark:text-dark-400 min-h-[1.5rem]">
                  {{ item.preview || '(无内容)' }}
                </div>
                
                <div class="flex items-center justify-between text-[10px] text-gray-400 dark:text-dark-500 uppercase tracking-wide mt-1">
                  <span>{{ item.time }}</span>
                  <div class="flex items-center gap-1">
                    <span
                      v-if="item.status === 'interrupted'"
                      class="w-2 h-2 rounded-full bg-amber-500"
                      title="等待确认"
                    />
                    <span
                      v-else-if="item.status === 'error'"
                      class="w-2 h-2 rounded-full bg-red-500"
                      title="错误"
                    />
                    <span
                      v-else-if="item.status === 'busy'"
                      class="w-2 h-2 rounded-full bg-blue-500 animate-pulse"
                      title="运行中"
                    />
                  </div>
                </div>
              </button>

              <button
                v-if="canDelete"
                type="button"
                class="absolute right-2 top-2 rounded p-1 text-gray-400 opacity-0 transition hover:bg-red-50 hover:text-red-600 group-hover:opacity-100 focus:opacity-100 dark:hover:bg-red-900/30 dark:hover:text-red-400"
                :class="deletingThreadId === item.id ? 'opacity-100' : ''"
                :disabled="deletingThreadId === item.id"
                :aria-label="`删除会话：${item.title}`"
                title="删除会话"
                @click.stop="emit('delete-thread', item.id)"
              >
                <BaseIcon
                  name="x"
                  size="xs"
                />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <button
      v-if="hasMore"
      type="button"
      class="pw-table-tool-button mx-3 mb-2"
      :disabled="loading"
      @click="emit('load-more')"
    >
      加载更多
    </button>
    <!-- Pagination Footer -->
    <div
      v-if="filteredCount > 0"
      class="border-t border-gray-200 dark:border-dark-800 px-3 py-2 flex items-center justify-between text-xs text-gray-500 dark:text-dark-400 shrink-0 bg-gray-50/50 dark:bg-dark-900/50"
    >
      <button
        type="button"
        class="pw-table-tool-button px-2 py-1 text-xs disabled:opacity-40 disabled:cursor-not-allowed"
        :disabled="currentPage <= 1"
        @click="currentPage--"
      >
        上一页
      </button>

      <span class="text-[11px] font-medium text-gray-600 dark:text-dark-300">
        {{ currentPage }} / {{ totalPages }} 页 (共 {{ filteredCount }} 条已加载)
      </span>

      <button
        type="button"
        class="pw-table-tool-button px-2 py-1 text-xs disabled:opacity-40 disabled:cursor-not-allowed"
        :disabled="currentPage >= totalPages"
        @click="currentPage++"
      >
        下一页
      </button>
    </div>
  </aside>
</template>

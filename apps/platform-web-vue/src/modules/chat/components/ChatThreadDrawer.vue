<script setup lang="ts">
import { computed } from 'vue'
import BaseDrawer from '@/components/base/BaseDrawer.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import type { ChatThreadStatusFilter, ChatThreadSummaryGroup } from '../thread-list-view-model'

type ThreadStatusFilterOption = {
  value: ChatThreadStatusFilter
  label: string
}

const props = defineProps<{
  show: boolean
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
}>()

const emit = defineEmits<{
  close: []
  'update:search': [value: string]
  'update:statusFilter': [value: ChatThreadStatusFilter]
  'start-new-thread': []
  'select-thread': [threadId: string]
  'delete-thread': [threadId: string]
}>()

const searchModel = computed({
  get: () => props.search,
  set: (value: string) => emit('update:search', value)
})
</script>

<template>
  <BaseDrawer
    :show="show"
    title="会话列表"
    side="left"
    width="narrow"
    @close="emit('close')"
  >
    <div class="space-y-4">
      <div
        v-if="showContextBar"
        class="pw-card-glass p-4"
      >
        <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
          Current Target
        </div>
        <div class="mt-2 text-sm font-semibold text-gray-900 dark:text-white">
          {{ targetText }}
        </div>
        <div class="mt-1 text-xs leading-6 text-gray-500 dark:text-dark-300">
          {{ targetTypeText }} 模式会继续复用当前项目里的 thread 历史。
        </div>
      </div>

      <div class="flex items-center gap-2">
        <BaseInput
          v-model="searchModel"
          placeholder="搜索会话标题、预览或状态"
        />
        <button
          type="button"
          class="pw-topbar-action h-11 px-3"
          :disabled="!canStartThread"
          @click="emit('start-new-thread')"
        >
          <BaseIcon
            name="chat"
            size="sm"
          />
        </button>
      </div>

      <div class="flex flex-wrap gap-2">
        <button
          v-for="filter in filters"
          :key="filter.value"
          type="button"
          class="rounded-full border px-3 py-1.5 text-xs font-medium transition"
          :class="
            statusFilter === filter.value
              ? 'border-primary-200 bg-primary-50 text-primary-700 dark:border-primary-900/40 dark:bg-primary-950/25 dark:text-primary-100'
              : 'border-gray-200 bg-white text-gray-500 hover:border-gray-300 hover:text-gray-900 dark:border-dark-700 dark:bg-dark-900 dark:text-dark-300 dark:hover:text-white'
          "
          @click="emit('update:statusFilter', filter.value)"
        >
          {{ filter.label }}
        </button>
      </div>

      <div
        v-if="loading && threadCount === 0"
        class="space-y-3"
      >
        <div
          v-for="index in 4"
          :key="index"
          class="pw-card-glass h-24 animate-pulse"
        />
      </div>

      <div
        v-else-if="threadCount === 0"
        class="pw-card-glass p-4 text-sm leading-7 text-gray-500 dark:text-dark-300"
      >
        还没有会话。第一条消息发出去时会自动创建 thread，你也可以先手动新建一个空白对话。
      </div>

      <div
        v-else-if="filteredCount === 0"
        class="pw-card-glass p-4 text-sm leading-7 text-gray-500 dark:text-dark-300"
      >
        没有命中当前筛选条件。
      </div>

      <div
        v-else
        class="space-y-4"
      >
        <div
          v-for="group in groups"
          :key="group.key"
          class="space-y-2"
        >
          <div class="px-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
            {{ group.label }}
          </div>

          <div class="space-y-2">
            <div
              v-for="item in group.items"
              :key="item.id"
              class="group relative"
            >
              <button
                type="button"
                class="w-full rounded-2xl border px-4 py-3 pr-12 text-left transition"
                :class="
                  item.id === activeThreadId
                    ? 'border-primary-200 bg-primary-50/85 shadow-soft dark:border-primary-900/40 dark:bg-primary-950/25'
                    : 'border-transparent bg-transparent hover:border-gray-200 hover:bg-gray-50 dark:hover:border-dark-700 dark:hover:bg-dark-900/60'
                "
                @click="emit('select-thread', item.id)"
              >
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0">
                    <div class="truncate text-sm font-semibold text-gray-900 dark:text-white">
                      {{ item.title }}
                    </div>
                    <div class="mt-1 line-clamp-2 text-xs leading-6 text-gray-500 dark:text-dark-300">
                      {{ item.preview || '当前 thread 还没有可展示的消息预览。' }}
                    </div>
                  </div>
                  <BaseIcon
                    v-if="item.id === activeThreadId"
                    name="check"
                    size="sm"
                    class="mt-1 shrink-0 text-primary-500"
                  />
                </div>
                <div class="mt-3 flex items-center justify-between gap-3 text-[11px] uppercase tracking-[0.14em] text-gray-400 dark:text-dark-400">
                  <span>{{ item.time }}</span>
                  <span>{{ item.status }}</span>
                </div>
              </button>

              <button
                type="button"
                class="absolute right-3 top-3 rounded-full border border-transparent px-2 py-1 text-[11px] font-medium text-gray-400 opacity-0 transition hover:border-rose-200 hover:bg-rose-50 hover:text-rose-600 group-hover:opacity-100 dark:hover:border-rose-900/40 dark:hover:bg-rose-950/20 dark:hover:text-rose-300"
                :class="deletingThreadId === item.id ? 'opacity-100' : ''"
                :disabled="deletingThreadId === item.id"
                @click.stop="emit('delete-thread', item.id)"
              >
                {{ deletingThreadId === item.id ? '删除中' : '删除' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </BaseDrawer>
</template>

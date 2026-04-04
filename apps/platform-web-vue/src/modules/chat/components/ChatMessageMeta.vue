<script setup lang="ts">
import type { Message } from '@langchain/langgraph-sdk'
import { computed, ref, watch } from 'vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import { buildChatMessageMetaView } from '../message-meta-view-model'

const props = defineProps<{
  message: Message
  allMessages: Message[]
  defaultExpanded?: boolean
}>()

const toolOpenMap = ref<Record<string, boolean>>({})
const subAgentOpenMap = ref<Record<string, boolean>>({})

const metaView = computed(() => buildChatMessageMetaView(props.message, props.allMessages))

watch(
  () => props.message.id,
  () => {
    toolOpenMap.value = {}
    subAgentOpenMap.value = {}
  },
  { immediate: true }
)
</script>

<template>
  <div
    v-if="metaView.toolCalls.length > 0 || metaView.subAgentCards.length > 0"
    class="mt-4 space-y-3"
  >
    <div
      v-if="metaView.toolCalls.length > 0"
      class="space-y-2"
    >
      <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
        Tool Calls
      </div>

      <div
        v-for="item in metaView.toolCalls"
        :key="item.key"
        class="overflow-hidden rounded-2xl border border-slate-200/80 bg-slate-50/80 dark:border-dark-700 dark:bg-dark-800/70"
      >
        <button
          type="button"
          class="flex w-full items-center justify-between gap-3 px-3 py-3 text-left transition hover:bg-white/70 dark:hover:bg-dark-700/70"
          @click="toolOpenMap[item.key] = !(toolOpenMap[item.key] ?? defaultExpanded ?? true)"
        >
          <div class="flex min-w-0 items-center gap-3">
            <span
              class="inline-flex h-2.5 w-2.5 rounded-full"
              :class="item.status === 'completed' ? 'bg-emerald-500' : 'animate-pulse bg-sky-500'"
            />
            <div class="min-w-0">
              <div class="truncate text-sm font-semibold text-slate-900 dark:text-white">
                {{ item.name }}
              </div>
              <div class="mt-1 text-xs text-slate-500 dark:text-dark-300">
                {{ item.idLabel }}
              </div>
            </div>
          </div>

          <BaseIcon
            :name="toolOpenMap[item.key] ?? defaultExpanded ?? true ? 'chevron-down' : 'chevron-right'"
            size="sm"
            class="shrink-0 text-slate-400"
          />
        </button>

        <div
          v-if="toolOpenMap[item.key] ?? defaultExpanded ?? true"
          class="border-t border-slate-200/80 px-3 py-3 dark:border-dark-700"
        >
          <div
            v-if="item.argsEntries.length > 0"
            class="space-y-2"
          >
            <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
              Args
            </div>
            <div class="space-y-2">
              <div
                v-for="arg in item.argsEntries"
                :key="arg.key"
                class="rounded-2xl bg-white px-3 py-3 dark:bg-dark-900/80"
              >
                <div class="text-xs font-semibold text-slate-900 dark:text-white">
                  {{ arg.key }}
                </div>
                <pre class="mt-2 overflow-auto whitespace-pre-wrap break-words text-xs leading-6 text-slate-600 dark:text-dark-100">{{ arg.valueText }}</pre>
              </div>
            </div>
          </div>

          <div
            v-if="item.resultText"
            class="mt-3 space-y-2"
          >
            <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
              Result
            </div>
            <pre class="overflow-auto whitespace-pre-wrap break-words rounded-2xl bg-white px-3 py-3 text-xs leading-6 text-slate-600 dark:bg-dark-900/80 dark:text-dark-100">{{ item.resultText }}</pre>
          </div>
        </div>
      </div>
    </div>

    <div
      v-if="metaView.subAgentCards.length > 0"
      class="space-y-2"
    >
      <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
        Sub Agents
      </div>

      <div
        v-for="item in metaView.subAgentCards"
        :key="item.id"
        class="overflow-hidden rounded-2xl border border-slate-200/80 bg-slate-50/80 dark:border-dark-700 dark:bg-dark-800/70"
      >
        <button
          type="button"
          class="flex w-full items-center justify-between gap-3 px-3 py-3 text-left transition hover:bg-white/70 dark:hover:bg-dark-700/70"
          @click="subAgentOpenMap[item.id] = !(subAgentOpenMap[item.id] ?? false)"
        >
          <div class="flex min-w-0 items-center gap-3">
            <span
              class="inline-flex h-2.5 w-2.5 rounded-full"
              :class="item.status === 'completed' ? 'bg-emerald-500' : 'animate-pulse bg-amber-400'"
            />
            <div class="min-w-0">
              <div class="truncate text-sm font-semibold text-slate-900 dark:text-white">
                {{ item.name }}
              </div>
              <div class="mt-1 text-xs text-slate-500 dark:text-dark-300">
                {{ item.status === 'completed' ? 'completed' : 'running' }}
              </div>
            </div>
          </div>

          <BaseIcon
            :name="subAgentOpenMap[item.id] ? 'chevron-down' : 'chevron-right'"
            size="sm"
            class="shrink-0 text-slate-400"
          />
        </button>

        <div
          v-if="subAgentOpenMap[item.id]"
          class="space-y-3 border-t border-slate-200/80 px-3 py-3 dark:border-dark-700"
        >
          <div>
            <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
              Input
            </div>
            <pre class="mt-2 overflow-auto whitespace-pre-wrap break-words rounded-2xl bg-white px-3 py-3 text-xs leading-6 text-slate-600 dark:bg-dark-900/80 dark:text-dark-100">{{ item.input || '<empty>' }}</pre>
          </div>

          <div v-if="item.output">
            <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
              Output
            </div>
            <pre class="mt-2 overflow-auto whitespace-pre-wrap break-words rounded-2xl bg-white px-3 py-3 text-xs leading-6 text-slate-600 dark:bg-dark-900/80 dark:text-dark-100">{{ item.output }}</pre>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

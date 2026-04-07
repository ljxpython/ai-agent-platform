<script setup lang="ts">
import type { Message } from '@langchain/langgraph-sdk'
import { computed, ref, watch } from 'vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import { buildChatMessageMetaView } from '../message-meta-view-model'

const props = withDefaults(
  defineProps<{
    message: Message
    allMessages: Message[]
    defaultExpanded?: boolean
  }>(),
  {
    defaultExpanded: false
  }
)

const metaView = computed(() => buildChatMessageMetaView(props.message, props.allMessages))
const toolCount = computed(() => metaView.value.toolCalls.length)
const subAgentCount = computed(() => metaView.value.subAgentCards.length)
const hasPendingTool = computed(() => metaView.value.toolCalls.some((item) => item.status === 'pending'))
const hasPendingSubAgent = computed(() =>
  metaView.value.subAgentCards.some((item) => item.status === 'pending')
)
const hasMetaSummary = computed(() => toolCount.value > 0 || subAgentCount.value > 0)
const isExpanded = ref(props.defaultExpanded)

function summarizeNames(names: string[], limit = 3) {
  const normalizedNames = names
    .map((item) => item.trim())
    .filter(Boolean)

  if (normalizedNames.length === 0) {
    return ''
  }

  const visibleNames = normalizedNames.slice(0, limit)
  const hiddenCount = normalizedNames.length - visibleNames.length
  return hiddenCount > 0 ? `${visibleNames.join(' / ')} +${hiddenCount}` : visibleNames.join(' / ')
}

const toolSummaryText = computed(() =>
  summarizeNames(metaView.value.toolCalls.map((item) => item.name))
)
const subAgentSummaryText = computed(() =>
  summarizeNames(metaView.value.subAgentCards.map((item) => item.name), 2)
)

watch(
  () => props.defaultExpanded,
  (nextValue) => {
    if (nextValue) {
      isExpanded.value = true
    }
  }
)

function toggleExpanded() {
  isExpanded.value = !isExpanded.value
}
</script>

<template>
  <div
    v-if="hasMetaSummary"
    class="mt-4 rounded-2xl border border-slate-200/80 bg-slate-50/80 px-3 py-3 dark:border-dark-700 dark:bg-dark-800/70"
  >
    <button
      type="button"
      class="flex w-full flex-wrap items-center justify-between gap-3 text-left"
      @click="toggleExpanded"
    >
      <span class="flex flex-wrap items-center gap-2">
        <span
          v-if="toolCount > 0"
          class="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium"
          :class="
            hasPendingTool
              ? 'border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900/40 dark:bg-sky-950/20 dark:text-sky-200'
              : 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/40 dark:bg-emerald-950/20 dark:text-emerald-200'
          "
        >
          <span
            class="inline-flex h-2 w-2 rounded-full"
            :class="hasPendingTool ? 'animate-pulse bg-sky-500' : 'bg-emerald-500'"
          />
          工具调用 {{ toolCount }}
          <span
            v-if="toolSummaryText"
            class="max-w-[240px] truncate border-l border-current/20 pl-2"
          >
            {{ toolSummaryText }}
          </span>
        </span>

        <span
          v-if="subAgentCount > 0"
          class="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium"
          :class="
            hasPendingSubAgent
              ? 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-200'
              : 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/40 dark:bg-emerald-950/20 dark:text-emerald-200'
          "
        >
          <span
            class="inline-flex h-2 w-2 rounded-full"
            :class="hasPendingSubAgent ? 'animate-pulse bg-amber-500' : 'bg-emerald-500'"
          />
          子任务 {{ subAgentCount }}
          <span
            v-if="subAgentSummaryText"
            class="max-w-[220px] truncate border-l border-current/20 pl-2"
          >
            {{ subAgentSummaryText }}
          </span>
        </span>
      </span>

      <span class="inline-flex items-center gap-2 text-xs font-medium text-slate-500 dark:text-dark-300">
        <span>{{ isExpanded ? '收起详情' : '查看详情' }}</span>
        <BaseIcon
          name="chevron-down"
          size="xs"
          class="transition"
          :class="isExpanded ? 'rotate-180' : ''"
        />
      </span>
    </button>

    <div class="mt-3 flex items-start gap-2 text-xs leading-6 text-slate-500 dark:text-dark-300">
      <BaseIcon
        name="info"
        size="xs"
        class="mt-0.5 shrink-0"
      />
      <span>当前回合的工具调用与子任务会挂在这条消息下，点开即可查看参数、结果和状态。</span>
    </div>

    <div
      v-if="isExpanded"
      class="mt-4 space-y-4 border-t border-slate-200/80 pt-4 dark:border-dark-700"
    >
      <div
        v-if="metaView.toolCalls.length > 0"
        class="space-y-3"
      >
        <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
          Tool Calls
        </div>

        <div
          v-for="tool in metaView.toolCalls"
          :key="tool.key"
          class="pw-panel"
        >
          <div class="flex items-center justify-between gap-3">
            <div>
              <div class="text-sm font-semibold text-gray-900 dark:text-white">
                {{ tool.name }}
              </div>
              <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                {{ tool.idLabel }}
              </div>
            </div>
            <span
              class="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium"
              :class="
                tool.status === 'pending'
                  ? 'border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900/40 dark:bg-sky-950/20 dark:text-sky-100'
                  : 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/40 dark:bg-emerald-950/20 dark:text-emerald-100'
              "
            >
              <span
                class="inline-flex h-2 w-2 rounded-full"
                :class="tool.status === 'pending' ? 'animate-pulse bg-sky-500' : 'bg-emerald-500'"
              />
              {{ tool.status === 'pending' ? '运行中' : '已完成' }}
            </span>
          </div>

          <div
            v-if="tool.argsEntries.length > 0"
            class="mt-3 space-y-2"
          >
            <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
              Args
            </div>
            <div class="space-y-2">
              <div
                v-for="arg in tool.argsEntries"
                :key="arg.key"
                class="pw-panel-muted px-3 py-3"
              >
                <div class="text-xs font-semibold text-gray-900 dark:text-white">
                  {{ arg.key }}
                </div>
                <pre class="mt-2 overflow-auto whitespace-pre-wrap break-words text-xs leading-6 text-gray-600 dark:text-dark-100">{{ arg.valueText }}</pre>
              </div>
            </div>
          </div>

          <div
            v-if="tool.resultText"
            class="mt-3 space-y-2"
          >
            <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
              Result
            </div>
            <pre class="pw-panel-muted overflow-auto whitespace-pre-wrap break-words px-3 py-3 text-xs leading-6 text-gray-600 dark:text-dark-100">{{ tool.resultText }}</pre>
          </div>
        </div>
      </div>

      <div
        v-if="metaView.subAgentCards.length > 0"
        class="space-y-3"
      >
        <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
          Sub Agents
        </div>

        <div
          v-for="item in metaView.subAgentCards"
          :key="item.id"
          class="pw-panel"
        >
          <div class="flex items-center justify-between gap-3">
            <div>
              <div class="text-sm font-semibold text-gray-900 dark:text-white">
                {{ item.name }}
              </div>
              <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                {{ item.id }}
              </div>
            </div>
            <span
              class="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium"
              :class="
                item.status === 'pending'
                  ? 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-100'
                  : 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/40 dark:bg-emerald-950/20 dark:text-emerald-100'
              "
            >
              <span
                class="inline-flex h-2 w-2 rounded-full"
                :class="item.status === 'pending' ? 'animate-pulse bg-amber-500' : 'bg-emerald-500'"
              />
              {{ item.status === 'pending' ? '运行中' : '已完成' }}
            </span>
          </div>

          <div class="mt-3">
            <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
              Input
            </div>
            <pre class="pw-panel-muted mt-2 overflow-auto whitespace-pre-wrap break-words px-3 py-3 text-xs leading-6 text-gray-600 dark:text-dark-100">{{ item.input || '<empty>' }}</pre>
          </div>

          <div
            v-if="item.output"
            class="mt-3"
          >
            <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
              Output
            </div>
            <pre class="pw-panel-muted mt-2 overflow-auto whitespace-pre-wrap break-words px-3 py-3 text-xs leading-6 text-gray-600 dark:text-dark-100">{{ item.output }}</pre>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

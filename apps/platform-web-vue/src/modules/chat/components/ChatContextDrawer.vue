<script setup lang="ts">
import BaseButton from '@/components/base/BaseButton.vue'
import BaseDrawer from '@/components/base/BaseDrawer.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import type { ChatRunOptions } from '../types'
import type { RuntimeModelItem, RuntimeToolItem, ThreadHistoryEntry } from '@/types/management'
import { getHistoryEntryId, getHistoryEntryTime, toPrettyJson } from '@/utils/threads'

defineProps<{
  show: boolean
  allowRunOptions: boolean
  showHistory: boolean
  showArtifacts: boolean
  allowResetTarget: boolean
  targetText: string
  projectName: string
  activeThreadId: string
  lastRunId: string
  selectedBranch: string
  latestMessagePreview: string
  selectedToolsLabel: string
  draftRunOptions: ChatRunOptions
  runtimeModels: RuntimeModelItem[]
  runtimeTools: RuntimeToolItem[]
  loadingRuntime: boolean
  historyItems: ThreadHistoryEntry[]
  isViewingBranch: boolean
}>()

const emit = defineEmits<{
  close: []
  'update:model-id': [value: string]
  'update:enable-tools': [value: boolean]
  'toggle-tool': [toolKey: string]
  'update:debug-mode': [value: boolean]
  'update:temperature': [value: string]
  'update:max-tokens': [value: string]
  'select-branch': [branchId: string]
  'reset-target': []
  restore: []
  apply: []
}>()

function getInputValue(event: Event) {
  return (event.target as HTMLInputElement | HTMLSelectElement | null)?.value || ''
}

function getCheckedValue(event: Event) {
  return Boolean((event.target as HTMLInputElement | null)?.checked)
}
</script>

<template>
  <BaseDrawer
    :show="show"
    title="运行上下文与参数"
    side="right"
    width="wide"
    @close="emit('close')"
  >
    <div class="space-y-5">
      <div class="pw-card-glass p-4">
        <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
          当前上下文
        </div>
        <div class="mt-3 space-y-3 text-sm leading-7 text-gray-600 dark:text-dark-300">
          <div class="flex items-start justify-between gap-3">
            <span>Target</span>
            <span class="max-w-[220px] break-all text-right font-semibold text-gray-900 dark:text-white">{{ targetText }}</span>
          </div>
          <div class="flex items-start justify-between gap-3">
            <span>项目</span>
            <span class="max-w-[220px] text-right font-semibold text-gray-900 dark:text-white">{{ projectName || '--' }}</span>
          </div>
          <div class="flex items-start justify-between gap-3">
            <span>Thread</span>
            <span class="max-w-[220px] break-all text-right font-semibold text-gray-900 dark:text-white">{{ activeThreadId || '--' }}</span>
          </div>
          <div class="flex items-start justify-between gap-3">
            <span>Run</span>
            <span class="max-w-[220px] break-all text-right font-semibold text-gray-900 dark:text-white">{{ lastRunId || '--' }}</span>
          </div>
          <div class="flex items-start justify-between gap-3">
            <span>Branch</span>
            <span class="max-w-[220px] break-all text-right font-semibold text-gray-900 dark:text-white">
              {{ selectedBranch || 'latest' }}
            </span>
          </div>
          <div class="flex items-start justify-between gap-3">
            <span>最近消息</span>
            <span class="max-w-[220px] text-right text-gray-500 dark:text-dark-300">{{ latestMessagePreview || '暂无' }}</span>
          </div>
        </div>
      </div>

      <div
        v-if="allowRunOptions"
        class="space-y-4"
      >
        <div class="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
          <BaseIcon
            name="runtime"
            size="sm"
            class="text-primary-500"
          />
          Run Options
        </div>

        <label class="block">
          <span class="pw-input-label">模型</span>
          <select
            :value="draftRunOptions.modelId"
            class="pw-select"
            @change="emit('update:model-id', getInputValue($event))"
          >
            <option value="">
              使用默认模型
            </option>
            <option
              v-for="model in runtimeModels"
              :key="model.id"
              :value="model.model_id"
            >
              {{ model.display_name || model.model_id }}
            </option>
          </select>
        </label>

        <div class="pw-card-glass p-4">
          <label class="flex items-center justify-between gap-3">
            <div>
              <div class="text-sm font-semibold text-gray-900 dark:text-white">
                工具开关
              </div>
              <div class="mt-1 text-xs leading-6 text-gray-500 dark:text-dark-300">
                {{ selectedToolsLabel }}
              </div>
            </div>
            <input
              :checked="draftRunOptions.enableTools"
              type="checkbox"
              class="pw-table-checkbox"
              @change="emit('update:enable-tools', getCheckedValue($event))"
            >
          </label>

          <div
            v-if="draftRunOptions.enableTools"
            class="mt-4 max-h-56 space-y-2 overflow-y-auto"
          >
            <label
              v-for="tool in runtimeTools"
              :key="tool.id"
              class="flex items-start gap-3 rounded-2xl border border-white/70 bg-white/80 px-3 py-3 text-sm dark:border-dark-700 dark:bg-dark-900/70"
            >
              <input
                :checked="draftRunOptions.toolNames.includes(tool.tool_key)"
                type="checkbox"
                class="pw-table-checkbox mt-1"
                @change="emit('toggle-tool', tool.tool_key)"
              >
              <div class="min-w-0">
                <div class="font-semibold text-gray-900 dark:text-white">
                  {{ tool.name || tool.tool_key }}
                </div>
                <div class="mt-1 text-xs leading-6 text-gray-500 dark:text-dark-300">
                  {{ tool.description || tool.source || '暂无描述' }}
                </div>
              </div>
            </label>

            <div
              v-if="runtimeTools.length === 0 && !loadingRuntime"
              class="text-xs leading-6 text-gray-400 dark:text-dark-400"
            >
              当前没有可选工具目录。
            </div>
          </div>
        </div>

        <div class="pw-card-glass p-4">
          <label class="flex items-center justify-between gap-3">
            <div>
              <div class="text-sm font-semibold text-gray-900 dark:text-white">
                Debug Mode
              </div>
              <div class="mt-1 text-xs leading-6 text-gray-500 dark:text-dark-300">
                打开后，发送消息会先在工具执行前暂停，你可以逐步继续执行。
              </div>
            </div>
            <input
              :checked="draftRunOptions.debugMode"
              type="checkbox"
              class="pw-table-checkbox"
              @change="emit('update:debug-mode', getCheckedValue($event))"
            >
          </label>
        </div>

        <div class="grid gap-4 md:grid-cols-2">
          <label class="block">
            <span class="pw-input-label">Temperature</span>
            <input
              :value="draftRunOptions.temperature"
              class="pw-input"
              placeholder="例如 0.2"
              @input="emit('update:temperature', getInputValue($event))"
            >
          </label>
          <label class="block">
            <span class="pw-input-label">Max Tokens</span>
            <input
              :value="draftRunOptions.maxTokens"
              class="pw-input"
              placeholder="例如 4096"
              @input="emit('update:max-tokens', getInputValue($event))"
            >
          </label>
        </div>
      </div>

      <div
        v-if="showHistory"
        class="space-y-3"
      >
        <details class="pw-card-glass overflow-hidden p-4">
          <summary class="cursor-pointer list-none">
            <div class="flex items-center justify-between gap-3">
              <div class="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
                <BaseIcon
                  name="threads"
                  size="sm"
                  class="text-primary-500"
                />
                最近历史
              </div>
              <div class="text-xs text-gray-400 dark:text-dark-400">
                调试用
              </div>
            </div>
          </summary>

          <div class="mt-4 space-y-3">
            <div
              v-if="isViewingBranch"
              class="flex items-center justify-between gap-3 rounded-2xl border border-primary-200 bg-primary-50/70 px-3 py-3 text-sm dark:border-primary-900/40 dark:bg-primary-950/20"
            >
              <div class="min-w-0">
                <div class="font-semibold text-gray-900 dark:text-white">
                  当前正在查看历史分支
                </div>
                <div class="mt-1 break-all text-xs leading-6 text-gray-500 dark:text-dark-300">
                  {{ selectedBranch }}
                </div>
              </div>
              <BaseButton
                variant="ghost"
                @click="emit('select-branch', '')"
              >
                返回最新
              </BaseButton>
            </div>

            <div
              v-if="historyItems.length === 0"
              class="text-sm leading-7 text-gray-500 dark:text-dark-300"
            >
              当前 thread 还没有 checkpoint 历史，或者还没开始对话。
            </div>

            <details
              v-for="(entry, historyIndex) in historyItems"
              :key="getHistoryEntryId(entry, historyIndex)"
              class="rounded-2xl border border-white/70 bg-white/80 p-4 dark:border-dark-700 dark:bg-dark-900/70"
            >
              <summary class="cursor-pointer list-none">
                <div class="flex items-center justify-between gap-3">
                  <div class="text-sm font-semibold text-gray-900 dark:text-white">
                    {{ getHistoryEntryId(entry, historyIndex) }}
                  </div>
                  <div class="text-xs text-gray-400 dark:text-dark-400">
                    {{ getHistoryEntryTime(entry) }}
                  </div>
                </div>
              </summary>
              <div class="mt-3 flex justify-end">
                <BaseButton
                  variant="ghost"
                  @click="emit('select-branch', getHistoryEntryId(entry, historyIndex))"
                >
                  查看此分支
                </BaseButton>
              </div>
              <pre class="mt-3 max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-2xl bg-gray-950 px-3 py-3 text-xs leading-6 text-gray-100 dark:bg-black/50">{{ toPrettyJson(entry) }}</pre>
            </details>
          </div>
        </details>
      </div>

      <div
        v-if="showArtifacts"
        class="pw-card-glass p-4 text-sm leading-7 text-gray-500 dark:text-dark-300"
      >
        <div class="text-sm font-semibold text-gray-900 dark:text-white">
          Artifact 侧栏
        </div>
        <p class="mt-2">
          当前 thread 如果存在 `values.ui` 条目，会在主画布右侧直接展开 artifact 侧栏。没有数据时，这里只保留口径说明，不再继续放空占位。
        </p>
      </div>

      <div
        v-if="allowResetTarget"
        class="pw-card-glass p-4"
      >
        <div class="text-sm font-semibold text-gray-900 dark:text-white">
          默认聊天目标
        </div>
        <p class="mt-2 text-sm leading-7 text-gray-500 dark:text-dark-300">
          这个动作只会清掉当前项目保存的默认聊天入口，不会删除任何 thread、消息或后端运行数据。
        </p>
        <div class="mt-4">
          <BaseButton
            variant="ghost"
            @click="emit('reset-target')"
          >
            重置默认聊天目标
          </BaseButton>
        </div>
      </div>
    </div>

    <template
      v-if="allowRunOptions"
      #footer
    >
      <div class="flex flex-wrap items-center gap-3">
        <BaseButton
          variant="ghost"
          @click="emit('restore')"
        >
          还原
        </BaseButton>
        <BaseButton @click="emit('apply')">
          确定
        </BaseButton>
      </div>
    </template>
  </BaseDrawer>
</template>

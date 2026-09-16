<script setup lang="ts">
import { computed } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseDialog from '@/components/base/BaseDialog.vue'
import BaseSelect from '@/components/base/BaseSelect.vue'
type ExecutionMode = 'flash' | 'standard' | 'pro' | 'ultra'
type ChatRunOptions = { modelId: string; temperature: string; maxTokens: string; recursionLimit?: string; executionMode?: ExecutionMode }
import type { RuntimeModelItem } from '@/types/management'

const props = withDefaults(
  defineProps<{
    show: boolean
    draftRunOptions: ChatRunOptions
    runtimeModels: RuntimeModelItem[]
    error?: string
    modeDisabled?: boolean
  }>(),
  {
    modeDisabled: false
  }
)

const emit = defineEmits<{
  close: []
  'update:model-id': [value: string]
  'update:temperature': [value: string]
  'update:max-tokens': [value: string]
  'update:recursion-limit': [value: string]
  'update:execution-mode': [value: ExecutionMode]
  restore: []
  apply: []
}>()

function getInputValue(event: Event) {
  return (event.target as HTMLInputElement | HTMLSelectElement | null)?.value || ''
}

const currentMode = computed<ExecutionMode>(() => props.draftRunOptions.executionMode || 'standard')

const modes: Array<{ mode: ExecutionMode; title: string; badge: string; desc: string; note: string }> = [
  {
    mode: 'standard',
    title: 'Standard 标准模式',
    badge: '默认推荐',
    desc: '通用 Agent 规划与执行，平衡深度与响应时延。',
    note: '通用步数'
  },
  {
    mode: 'flash',
    title: 'Flash 极速模式',
    badge: '低时延',
    desc: '极简快速响应，减少思考开销。',
    note: '若模型不支持推理控制则保持默认'
  },
  {
    mode: 'pro',
    title: 'Pro 深度模式',
    badge: '规划与研究',
    desc: '开启多步骤规划、深度搜索、正文抓取与交叉核实。',
    note: '有界预算 100 步'
  },
  {
    mode: 'ultra',
    title: 'Ultra 超级委派',
    badge: '子 Agent 委派',
    desc: '支持向多子任务 Agent 委派复杂分析与研究。',
    note: '有界预算 100 步'
  }
]
</script>

<template>
  <BaseDialog
    :show="show"
    title="运行参数与执行模式"
    width="wide"
    @close="emit('close')"
  >
    <div class="space-y-5">
      <p
        v-if="error"
        role="alert"
        class="text-sm text-red-600"
      >
        {{ error }}
      </p>
      <div class="pw-card-highlight px-4 py-3 text-xs leading-6 text-primary-900 dark:text-primary-100">
        这里的设置影响下一次新发起的对话或运行。执行中或中断恢复时模式将严格锁定。
      </div>

      <!-- 执行模式选择区 -->
      <div>
        <div class="flex items-center justify-between mb-2">
          <span class="pw-input-label !mb-0">执行模式 (Execution Mode)</span>
          <span
            v-if="modeDisabled"
            class="text-[11px] text-amber-600 dark:text-amber-400"
          >
            当前运行中或处于审批，模式已锁定
          </span>
        </div>
        <div class="grid gap-2.5 sm:grid-cols-2">
          <div
            v-for="item in modes"
            :key="item.mode"
            class="relative flex flex-col justify-between rounded-xl border p-3 cursor-pointer transition-all"
            :class="[
              currentMode === item.mode
                ? 'border-primary-500 bg-primary-50/70 ring-1 ring-primary-500/30 dark:bg-primary-950/40 dark:border-primary-500'
                : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50/60 dark:border-dark-700 dark:hover:bg-dark-800/50',
              modeDisabled ? 'opacity-60 cursor-not-allowed pointer-events-none' : ''
            ]"
            role="button"
            :aria-pressed="currentMode === item.mode"
            tabindex="0"
            @click="!modeDisabled && emit('update:execution-mode', item.mode)"
            @keydown.enter.prevent="!modeDisabled && emit('update:execution-mode', item.mode)"
            @keydown.space.prevent="!modeDisabled && emit('update:execution-mode', item.mode)"
          >
            <div>
              <div class="flex items-center justify-between gap-1">
                <span class="text-xs font-semibold text-gray-900 dark:text-white">
                  {{ item.title }}
                </span>
                <span
                  class="rounded px-1.5 py-0.5 text-[10px] font-medium"
                  :class="currentMode === item.mode ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-600 dark:bg-dark-700 dark:text-dark-300'"
                >
                  {{ item.badge }}
                </span>
              </div>
              <p class="mt-1 text-[11px] leading-4 text-gray-500 dark:text-dark-400">
                {{ item.desc }}
              </p>
            </div>
            <div class="mt-2.5 pt-2 border-t border-gray-100 dark:border-dark-800 text-[10px] text-gray-400 dark:text-dark-400 font-mono flex items-center justify-between">
              <span>{{ item.note }}</span>
              <span v-if="currentMode === item.mode" class="text-primary-600 dark:text-primary-400 font-semibold">✓ 已选</span>
            </div>
          </div>
        </div>
      </div>

      <label class="block">
        <span class="pw-input-label">模型</span>
        <BaseSelect
          :model-value="props.draftRunOptions.modelId"
          @update:model-value="emit('update:model-id', $event)"
        >
          <option value="">
            使用默认模型
          </option>
          <option
            v-for="model in props.runtimeModels"
            :key="model.id"
            :value="model.id"
          >
            {{ model.display_name || model.model }}
          </option>
        </BaseSelect>
      </label>


      <div class="grid gap-4 md:grid-cols-2">
        <label class="block">
          <span class="pw-input-label">Temperature</span>
          <input
            :value="props.draftRunOptions.temperature"
            class="pw-input"
            placeholder="例如 0.2"
            @input="emit('update:temperature', getInputValue($event))"
          >
        </label>
        <label class="block">
          <span class="pw-input-label">Max Tokens</span>
          <input
            :value="props.draftRunOptions.maxTokens"
            class="pw-input"
            placeholder="例如 4096"
            @input="emit('update:max-tokens', getInputValue($event))"
          >
        </label>
      </div>

      <label class="block">
        <span class="pw-input-label">最大步数预算 (Recursion Limit)</span>
        <input
          :value="props.draftRunOptions.recursionLimit"
          class="pw-input"
          placeholder="默认 1000，支持 1..1000"
          @input="emit('update:recursion-limit', getInputValue($event))"
        >
        <span class="mt-1 block text-xs text-gray-400 dark:text-dark-400">
          控制单次运行允许的最大图执行步数（1~1000）。Dear Agent 执行方案设计、深度研究、画图建议保持 1000 步充裕预算。
        </span>
      </label>
    </div>

    <template #footer>
      <div class="flex flex-wrap justify-end gap-3">
        <BaseButton
          variant="ghost"
          @click="emit('restore')"
        >
          还原
        </BaseButton>
        <BaseButton
          variant="secondary"
          @click="emit('close')"
        >
          取消
        </BaseButton>
        <BaseButton @click="emit('apply')">
          确认
        </BaseButton>
      </div>
    </template>
  </BaseDialog>
</template>

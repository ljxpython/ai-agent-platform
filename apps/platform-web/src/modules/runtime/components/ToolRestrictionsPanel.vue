<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseDialog from '@/components/base/BaseDialog.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import BaseSelect from '@/components/base/BaseSelect.vue'
import ConfirmDialog from '@/components/base/ConfirmDialog.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import StatusPill from '@/components/platform/StatusPill.vue'
import { listProjectMembers } from '@/services/members/members.service'
import { listRuntimeGraphs } from '@/services/runtime/runtime.service'
import {
  createToolRestriction,
  deleteToolRestriction,
  listToolRestrictions
} from '@/services/runtime-policies/runtime-policies.service'
import type {
  CreateToolRestrictionPayload,
  ManagementProjectMember,
  RuntimeToolItem,
  ToolRestrictionItem,
  ToolRestrictionSubjectType
} from '@/types/management'

const props = defineProps<{
  show: boolean
  projectId: string
  tools: RuntimeToolItem[]
  canManage: boolean
}>()

const emit = defineEmits<{
  close: []
}>()

const restrictions = ref<ToolRestrictionItem[]>([])
const members = ref<ManagementProjectMember[]>([])
const directGraphs = ref<string[]>([])
const loading = ref(false)
const saving = ref(false)
const deletingId = ref<string | null>(null)
const error = ref('')
const notice = ref('')

// 表单字段
const formGraphId = ref('')
const formToolNames = ref<string[]>([]) // 严格绑定 tool_key，支持多选
const toolDropdownOpen = ref(false)
const toolSearchQuery = ref('')
const formSubjectType = ref<ToolRestrictionSubjectType>('project')
const formSubjectId = ref('')
const formReason = ref('')

// 计算可用的 graph_ids（双重合并：直接查询的 graph + 工具上声明的 graph）
const availableGraphs = computed(() => {
  const set = new Set<string>()
  for (const gid of directGraphs.value) {
    if (gid && gid.trim()) set.add(gid.trim())
  }
  for (const t of props.tools) {
    for (const gid of t.graph_ids || []) {
      if (gid && gid.trim()) set.add(gid.trim())
    }
  }
  return Array.from(set).sort()
})

// 监听 availableGraphs 变化，当有可用 Graph 且表单为空时自动赋默认值
watch(
  availableGraphs,
  (graphs) => {
    if (!formGraphId.value && graphs.length) {
      formGraphId.value = graphs[0]
    }
  },
  { immediate: true }
)

// 根据选中的 graph_id 过滤工具列表
const availableToolsForGraph = computed(() => {
  if (!formGraphId.value) return []
  return props.tools.filter((t) => (t.graph_ids || []).includes(formGraphId.value))
})

// 下拉搜索过滤工具列表
const filteredToolsForSelection = computed(() => {
  const list = availableToolsForGraph.value
  const q = toolSearchQuery.value.trim().toLowerCase()
  if (!q) return list
  return list.filter(
    (t) => (t.name && t.name.toLowerCase().includes(q)) || t.tool_key.toLowerCase().includes(q)
  )
})

function toggleToolSelection(key: string) {
  if (formToolNames.value.includes(key)) {
    formToolNames.value = formToolNames.value.filter((k) => k !== key)
  } else {
    formToolNames.value = [...formToolNames.value, key]
  }
}

function selectAllFilteredTools() {
  const set = new Set(formToolNames.value)
  for (const t of filteredToolsForSelection.value) {
    set.add(t.tool_key)
  }
  formToolNames.value = Array.from(set)
}

function deselectAllTools() {
  formToolNames.value = []
}

function removeSelectedTool(key: string) {
  formToolNames.value = formToolNames.value.filter((k) => k !== key)
}

// 成员查找 map
const memberNameMap = computed(() => {
  const map = new Map<string, string>()
  for (const m of members.value) {
    map.set(m.user_id, m.username)
  }
  return map
})

function formatCreator(creator: string): string {
  if (!creator) return '-'
  if (memberNameMap.value.has(creator)) {
    return memberNameMap.value.get(creator)!
  }
  if (creator.length > 12) {
    return `${creator.slice(0, 8)}…`
  }
  return creator
}

function formatDateTime(iso: string): string {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    if (isNaN(d.getTime())) return iso
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    const h = String(d.getHours()).padStart(2, '0')
    const min = String(d.getMinutes()).padStart(2, '0')
    return `${y}/${m}/${day} ${h}:${min}`
  } catch {
    return iso
  }
}

const graphOptions = computed(() => {
  return availableGraphs.value.map((gid) => ({
    value: gid,
    label: gid
  }))
})

const memberOptions = computed(() => {
  return members.value.map((m) => ({
    value: m.user_id,
    label: `${m.username} (${m.role})`
  }))
})

const toolDropdownContainerRef = ref<HTMLElement | null>(null)

function handleDocumentClick(e: MouseEvent) {
  if (!toolDropdownOpen.value) return
  const target = e.target as Node | null
  if (toolDropdownContainerRef.value && target && !toolDropdownContainerRef.value.contains(target)) {
    toolDropdownOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleDocumentClick)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleDocumentClick)
})

// 计算存在全员禁用的 (graph_id + tool_name) 集合
const projectDisabledKeys = computed(() => {
  const set = new Set<string>()
  for (const r of restrictions.value) {
    if (r.subject_type === 'project') {
      set.add(`${r.graph_id}::${r.tool_name}`)
    }
  }
  return set
})

function isProjectAlsoDisabled(item: ToolRestrictionItem): boolean {
  if (item.subject_type !== 'user') return false
  return projectDisabledKeys.value.has(`${item.graph_id}::${item.tool_name}`)
}

async function loadRestrictions() {
  if (!props.projectId || !props.canManage) return
  loading.value = true
  error.value = ''
  try {
    const res = await listToolRestrictions(props.projectId)
    restrictions.value = res.items
  } catch (err: any) {
    error.value = err?.message || '读取工具禁用规则失败'
  } finally {
    loading.value = false
  }
}

async function loadMembers() {
  if (!props.projectId || !props.canManage) return
  try {
    members.value = await listProjectMembers(props.projectId)
  } catch {
    // 成员列表读取失败不阻塞规则主展示
  }
}

async function loadGraphs() {
  if (!props.projectId || !props.canManage) return
  try {
    const res = await listRuntimeGraphs(props.projectId)
    if (res?.graphs) {
      directGraphs.value = res.graphs.map((g) => g.graph_id).filter(Boolean)
    }
  } catch {
    // 忽略异常，降级依赖 props.tools
  }
}

function resetForm() {
  formGraphId.value = availableGraphs.value[0] || ''
  formToolNames.value = []
  toolDropdownOpen.value = false
  toolSearchQuery.value = ''
  formSubjectType.value = 'project'
  formSubjectId.value = props.projectId
  formReason.value = ''
  error.value = ''
  notice.value = ''
}

watch(
  () => props.show,
  (visible) => {
    if (visible && props.canManage) {
      resetForm()
      void loadRestrictions()
      void loadMembers()
      void loadGraphs()
    }
  },
  { immediate: true }
)

watch(formGraphId, () => {
  formToolNames.value = []
  toolSearchQuery.value = ''
})

watch(formSubjectType, (type) => {
  if (type === 'project') {
    formSubjectId.value = props.projectId
  } else {
    formSubjectId.value = members.value[0]?.user_id || ''
  }
})

async function handleCreate() {
  if (!props.canManage || saving.value) return
  error.value = ''
  notice.value = ''

  if (!formGraphId.value.trim()) {
    error.value = '请选择适用的 Graph'
    return
  }
  if (!formToolNames.value.length) {
    error.value = '请至少选择一个要禁用的工具'
    return
  }
  if (formSubjectType.value === 'user' && !formSubjectId.value.trim()) {
    error.value = '请选择目标成员'
    return
  }
  if (!formReason.value.trim()) {
    error.value = '请填写禁用原因'
    return
  }

  saving.value = true
  let successCount = 0
  const failedTools: string[] = []
  let firstErrorMessage = ''

  try {
    const results = await Promise.allSettled(
      formToolNames.value.map(async (toolName) => {
        const payload: CreateToolRestrictionPayload = {
          graph_id: formGraphId.value.trim(),
          subject_type: formSubjectType.value,
          subject_id: formSubjectType.value === 'project' ? props.projectId : formSubjectId.value.trim(),
          tool_name: toolName.trim(),
          reason: formReason.value.trim()
        }
        return createToolRestriction(props.projectId, payload)
      })
    )

    results.forEach((res, index) => {
      const tool = formToolNames.value[index]
      if (res.status === 'fulfilled') {
        successCount++
      } else {
        failedTools.push(tool)
        if (!firstErrorMessage) {
          const err = res.reason
          const code = err?.response?.data?.code || err?.code
          if (code === 'tool_restriction_exists') {
            firstErrorMessage = `工具 ${tool} 已存在禁用规则`
          } else if (code === 'tool_not_declared') {
            firstErrorMessage = `工具 ${tool} 未在 Graph 中声明`
          } else {
            firstErrorMessage = err?.response?.data?.message || err?.message || `工具 ${tool} 添加失败`
          }
        }
      }
    })

    if (successCount > 0) {
      notice.value = failedTools.length
        ? `成功添加 ${successCount} 条规则，${failedTools.length} 个工具跳过或失败（${firstErrorMessage}）`
        : `已成功添加 ${successCount} 条工具禁用规则`
      formToolNames.value = failedTools
      toolDropdownOpen.value = false
      toolSearchQuery.value = ''
      if (!failedTools.length) {
        formReason.value = ''
      }
      await loadRestrictions()
    } else {
      error.value = firstErrorMessage || '添加禁用规则失败'
    }
  } finally {
    saving.value = false
  }
}

const pendingDeleteItem = ref<ToolRestrictionItem | null>(null)
const showConfirmDelete = ref(false)

function openDeleteConfirm(item: ToolRestrictionItem) {
  if (!props.canManage || deletingId.value) return
  pendingDeleteItem.value = item
  showConfirmDelete.value = true
}

async function executeDelete() {
  const item = pendingDeleteItem.value
  showConfirmDelete.value = false
  if (!item || !props.canManage || deletingId.value) return

  deletingId.value = item.id
  error.value = ''
  notice.value = ''
  try {
    await deleteToolRestriction(props.projectId, item.id)
    notice.value = `已解除对工具 ${item.tool_name} 的禁用规则`
    await loadRestrictions()
  } catch (err: any) {
    const code = err?.response?.data?.code || err?.code
    if (code === 'tool_restriction_not_found') {
      error.value = '该禁用规则已被删除'
    } else {
      error.value = err?.response?.data?.message || err?.message || '删除规则失败'
    }
  } finally {
    deletingId.value = null
    pendingDeleteItem.value = null
  }
}
</script>

<template>
  <BaseDialog
    :show="show"
    title="工具禁用规则管理"
    width="wide"
    @close="emit('close')"
  >
    <div class="space-y-6">
      <!-- 顶部说明横幅 -->
      <StateBanner
        variant="info"
        title="并集生效说明"
        description="项目全员规则与指定成员规则取并集生效。若项目全员已禁用某工具，即使删除单人规则，该成员依然无法调用此工具。"
      />

      <!-- 错误 / 成功通知 -->
      <StateBanner
        v-if="error"
        variant="danger"
        title="操作未完成"
        :description="error"
      />
      <StateBanner
        v-if="notice"
        variant="info"
        title="提示"
        :description="notice"
      />

      <!-- 新增规则表单 -->
      <section
        v-if="canManage"
        class="rounded-xl border border-gray-200 bg-gray-50/60 p-4 dark:border-dark-800 dark:bg-dark-950/40"
      >
        <h3 class="text-sm font-semibold text-gray-900 dark:text-white">
          添加工具禁用规则
        </h3>
        <p class="mt-0.5 text-xs text-gray-500 dark:text-dark-400">
          通过拒绝名单明确禁止某些工具在指定 Agent/Graph 中执行。
        </p>

        <div class="mt-4 grid gap-4 sm:grid-cols-2">
          <!-- 适用 Graph -->
          <div>
            <label class="block text-xs font-semibold text-gray-700 dark:text-dark-300">
              适用 Graph <span class="text-rose-500">*</span>
            </label>
            <div class="mt-1.5">
              <BaseSelect
                v-model="formGraphId"
                :options="graphOptions"
                :disabled="saving || !availableGraphs.length"
                :placeholder="availableGraphs.length ? '请选择适用 Graph' : '暂无可用 Graph (请先同步工具或 Graph)'"
              />
            </div>
          </div>

          <!-- 禁用工具 (支持多选) -->
          <div ref="toolDropdownContainerRef">
            <div class="flex items-center justify-between">
              <label class="block text-xs font-semibold text-gray-700 dark:text-dark-300">
                禁用工具 <span class="text-rose-500">*</span>
                <span class="ml-1 text-[11px] font-normal text-gray-400">（支持多选）</span>
              </label>
              <span
                v-if="formToolNames.length"
                class="text-[11px] font-medium text-primary-600 dark:text-primary-400"
              >
                已选 {{ formToolNames.length }} 项
              </span>
            </div>

            <div class="relative mt-1.5">
              <!-- 触发器按钮 -->
              <button
                type="button"
                class="flex h-10 w-full items-center justify-between rounded-xl border border-gray-200 bg-white px-3.5 text-left text-sm font-medium shadow-2xs outline-none transition-all duration-150 hover:border-gray-300 focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-400 dark:border-dark-700 dark:bg-dark-900 dark:text-dark-100 dark:hover:border-dark-600 dark:disabled:bg-dark-950"
                :disabled="saving || !formGraphId"
                @click="toolDropdownOpen = !toolDropdownOpen"
              >
                <span class="truncate">
                  <template v-if="!formGraphId">请先选择适用 Graph</template>
                  <template v-else-if="!availableToolsForGraph.length">当前 Graph 下无声明工具</template>
                  <template v-else-if="!formToolNames.length">
                    <span class="text-gray-400 dark:text-dark-400">请选择要禁用的工具（支持多选）</span>
                  </template>
                  <template v-else>
                    已选择 {{ formToolNames.length }} 项工具
                  </template>
                </span>
                <BaseIcon
                  name="chevron-down"
                  size="xs"
                  class="shrink-0 text-gray-400 transition-transform duration-150"
                  :class="toolDropdownOpen ? 'rotate-180' : ''"
                />
              </button>

              <!-- 下拉复选菜单面板 -->
              <div
                v-if="toolDropdownOpen && formGraphId && availableToolsForGraph.length"
                class="absolute left-0 right-0 top-full z-20 mt-1.5 max-h-64 overflow-hidden rounded-xl border border-gray-200 bg-white shadow-lg dark:border-dark-700 dark:bg-dark-900 flex flex-col"
              >
                <!-- 头部过滤与快捷操作 -->
                <div class="border-b border-gray-100 bg-gray-50/70 p-2 dark:border-dark-800 dark:bg-dark-950/40">
                  <div class="flex items-center gap-1.5">
                    <input
                      v-model="toolSearchQuery"
                      type="text"
                      placeholder="搜索工具名称或 tool_key..."
                      class="h-8 flex-1 rounded-lg border border-gray-200 bg-white px-2.5 text-xs text-gray-900 outline-none placeholder-gray-400 focus:border-primary-500 dark:border-dark-700 dark:bg-dark-900 dark:text-dark-100"
                    >
                    <button
                      type="button"
                      class="h-8 shrink-0 rounded-lg px-2 text-[11px] font-medium text-primary-600 hover:bg-primary-50 dark:text-primary-400 dark:hover:bg-primary-950/50"
                      @click="selectAllFilteredTools"
                    >
                      全选
                    </button>
                    <button
                      type="button"
                      class="h-8 shrink-0 rounded-lg px-2 text-[11px] font-medium text-gray-500 hover:bg-gray-100 dark:text-dark-400 dark:hover:bg-dark-800"
                      @click="deselectAllTools"
                    >
                      清空
                    </button>
                    <button
                      type="button"
                      class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-dark-800 dark:hover:text-dark-200"
                      title="收起"
                      @click="toolDropdownOpen = false"
                    >
                      <BaseIcon
                        name="x"
                        size="xs"
                      />
                    </button>
                  </div>
                </div>

                <!-- 工具选项列表 -->
                <div class="flex-1 overflow-y-auto p-1.5 space-y-0.5">
                  <div
                    v-if="!filteredToolsForSelection.length"
                    class="py-4 text-center text-xs text-gray-400"
                  >
                    未找到匹配工具
                  </div>
                  <label
                    v-for="t in filteredToolsForSelection"
                    :key="t.tool_key"
                    class="flex cursor-pointer items-center justify-between gap-2 rounded-lg px-2.5 py-1.5 text-xs transition-colors hover:bg-gray-50 dark:hover:bg-dark-800/80"
                    :class="formToolNames.includes(t.tool_key) ? 'bg-primary-50/50 dark:bg-primary-950/30' : ''"
                  >
                    <div class="flex items-center gap-2 min-w-0">
                      <input
                        type="checkbox"
                        :value="t.tool_key"
                        :checked="formToolNames.includes(t.tool_key)"
                        class="rounded border-gray-300 text-primary-600 focus:ring-primary-500 dark:border-dark-600 dark:bg-dark-800"
                        @change="toggleToolSelection(t.tool_key)"
                      >
                      <span class="truncate font-medium text-gray-900 dark:text-white">
                        {{ t.name || t.tool_key }}
                      </span>
                      <span class="font-mono text-[10px] text-gray-400 shrink-0">
                        ({{ t.tool_key }})
                      </span>
                    </div>
                    <span
                      v-if="t.source"
                      class="shrink-0 rounded bg-gray-100 px-1 py-0.2 text-[9px] text-gray-400 dark:bg-dark-800 dark:text-dark-500"
                    >
                      {{ t.source }}
                    </span>
                  </label>
                </div>

                <!-- 底部关闭栏 -->
                <div class="border-t border-gray-100 bg-gray-50/50 p-2 text-right dark:border-dark-800 dark:bg-dark-950/30">
                  <button
                    type="button"
                    class="rounded-lg bg-primary-600 px-3 py-1 text-xs font-medium text-white hover:bg-primary-700"
                    @click="toolDropdownOpen = false"
                  >
                    完成选择
                  </button>
                </div>
              </div>
            </div>

            <!-- 已选工具标签展示 -->
            <div
              v-if="formToolNames.length"
              class="mt-2 flex flex-wrap gap-1.5"
            >
              <span
                v-for="key in formToolNames"
                :key="key"
                class="inline-flex items-center gap-1 rounded-md border border-primary-200/80 bg-primary-50/70 px-2 py-0.5 text-[11px] font-medium text-primary-700 dark:border-primary-800/60 dark:bg-primary-950/40 dark:text-primary-300"
              >
                {{ key }}
                <button
                  type="button"
                  class="ml-0.5 hover:text-primary-900 dark:hover:text-white"
                  title="移除此项"
                  @click="removeSelectedTool(key)"
                >
                  <BaseIcon
                    name="x"
                    size="xs"
                  />
                </button>
              </span>
            </div>
          </div>

          <!-- 主体类型 -->
          <div>
            <label class="block text-xs font-semibold text-gray-700 dark:text-dark-300">
              禁用主体类型 <span class="text-rose-500">*</span>
            </label>
            <div class="mt-1.5 grid grid-cols-2 gap-2">
              <label
                class="flex h-10 cursor-pointer items-center justify-center gap-2 rounded-xl border px-3 text-xs font-medium transition-all"
                :class="
                  formSubjectType === 'project'
                    ? 'border-primary-500 bg-primary-50/70 text-primary-700 shadow-2xs dark:border-primary-600 dark:bg-primary-950/40 dark:text-primary-300'
                    : 'border-gray-200 bg-white text-gray-600 hover:border-gray-300 hover:bg-gray-50 dark:border-dark-700 dark:bg-dark-900 dark:text-dark-300 dark:hover:border-dark-600'
                "
              >
                <input
                  v-model="formSubjectType"
                  type="radio"
                  value="project"
                  class="sr-only"
                  :disabled="saving"
                >
                <span
                  class="h-2 w-2 rounded-full transition-colors"
                  :class="formSubjectType === 'project' ? 'bg-primary-600' : 'bg-gray-300 dark:bg-dark-600'"
                />
                项目全员
              </label>
              <label
                class="flex h-10 cursor-pointer items-center justify-center gap-2 rounded-xl border px-3 text-xs font-medium transition-all"
                :class="
                  formSubjectType === 'user'
                    ? 'border-primary-500 bg-primary-50/70 text-primary-700 shadow-2xs dark:border-primary-600 dark:bg-primary-950/40 dark:text-primary-300'
                    : 'border-gray-200 bg-white text-gray-600 hover:border-gray-300 hover:bg-gray-50 dark:border-dark-700 dark:bg-dark-900 dark:text-dark-300 dark:hover:border-dark-600'
                "
              >
                <input
                  v-model="formSubjectType"
                  type="radio"
                  value="user"
                  class="sr-only"
                  :disabled="saving"
                >
                <span
                  class="h-2 w-2 rounded-full transition-colors"
                  :class="formSubjectType === 'user' ? 'bg-primary-600' : 'bg-gray-300 dark:bg-dark-600'"
                />
                指定成员
              </label>
            </div>
          </div>

          <!-- 目标主体 -->
          <div>
            <label class="block text-xs font-semibold text-gray-700 dark:text-dark-300">
              目标对象
            </label>
            <div class="mt-1.5">
              <div
                v-if="formSubjectType === 'project'"
                class="flex h-10 items-center rounded-xl border border-dashed border-gray-200 bg-gray-50/70 px-3.5 text-xs text-gray-500 dark:border-dark-700 dark:bg-dark-900/60 dark:text-dark-400"
              >
                当前项目全员 ({{ projectId.slice(0, 8) }}…) · 并集生效
              </div>
              <div
                v-else
                class="mt-1.5"
              >
                <BaseSelect
                  v-model="formSubjectId"
                  :options="memberOptions"
                  :disabled="saving || !members.length"
                  placeholder="请选择成员"
                />
              </div>
            </div>
          </div>
        </div>

        <!-- 禁用原因 -->
        <div class="mt-4">
          <div class="flex items-center justify-between">
            <label class="block text-xs font-semibold text-gray-700 dark:text-dark-300">
              禁用原因 <span class="text-rose-500">*</span>
            </label>
            <span class="text-[11px] font-mono text-gray-400 dark:text-dark-500">
              {{ formReason.length }}/1000
            </span>
          </div>
          <textarea
            v-model="formReason"
            rows="2"
            maxlength="1000"
            placeholder="说明限制该工具使用的治理要求或合规原因（1~1000 字符）"
            class="mt-1.5 block w-full rounded-xl border border-gray-200 bg-white p-3 text-sm text-gray-900 shadow-2xs placeholder-gray-400 outline-none transition-all duration-150 hover:border-gray-300 focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 dark:border-dark-700 dark:bg-dark-900 dark:text-white dark:placeholder-dark-500 dark:hover:border-dark-600"
            :disabled="saving"
          />
        </div>

        <div class="mt-4 flex justify-end">
          <BaseButton
            variant="primary"
            size="sm"
            :disabled="saving || !formGraphId || !formToolNames.length || !formReason.trim()"
            @click="handleCreate"
          >
            <BaseIcon
              v-if="saving"
              name="refresh"
              class="animate-spin"
              size="sm"
            />
            {{ saving ? '正在添加…' : (formToolNames.length > 1 ? `批量添加 (${formToolNames.length} 项)` : '添加禁用规则') }}
          </BaseButton>
        </div>
      </section>

      <!-- 规则列表 -->
      <div>
        <div class="flex items-center justify-between">
          <h3 class="text-sm font-semibold text-gray-900 dark:text-white">
            生效中的禁用规则清单 ({{ restrictions.length }})
          </h3>
          <BaseButton
            variant="ghost"
            size="sm"
            :disabled="loading"
            @click="loadRestrictions"
          >
            <BaseIcon
              name="refresh"
              size="sm"
            />
            刷新
          </BaseButton>
        </div>

        <div
          v-if="loading"
          class="py-8 text-center text-sm text-gray-500"
        >
          正在加载规则…
        </div>

        <div
          v-else-if="!restrictions.length"
          class="rounded-xl border border-dashed border-gray-200 py-10 text-center text-sm text-gray-400 dark:border-dark-800 dark:text-dark-500"
        >
          当前项目未配置任何工具禁用规则，所有声明工具默认可用。
        </div>

        <div
          v-else
          class="mt-3 overflow-x-auto rounded-xl border border-gray-200 dark:border-dark-800"
        >
          <table class="min-w-full divide-y divide-gray-200 text-left text-sm dark:divide-dark-800">
            <thead class="bg-gray-50 text-xs font-medium text-gray-500 dark:bg-dark-900 dark:text-dark-400">
              <tr>
                <th class="whitespace-nowrap px-4 py-3">
                  作用主体
                </th>
                <th class="whitespace-nowrap px-4 py-3">
                  Graph
                </th>
                <th class="whitespace-nowrap px-4 py-3">
                  禁用工具
                </th>
                <th class="whitespace-nowrap px-4 py-3">
                  禁用原因
                </th>
                <th class="whitespace-nowrap px-4 py-3">
                  创建信息
                </th>
                <th
                  v-if="canManage"
                  class="whitespace-nowrap px-4 py-3 text-right"
                >
                  操作
                </th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100 bg-white dark:divide-dark-800 dark:bg-dark-950">
              <tr
                v-for="item in restrictions"
                :key="item.id"
                class="hover:bg-gray-50/50 dark:hover:bg-dark-900/30"
              >
                <!-- 主体 -->
                <td class="whitespace-nowrap px-4 py-3">
                  <div class="flex items-center gap-2">
                    <StatusPill
                      :tone="item.subject_type === 'project' ? 'warning' : 'neutral'"
                      class="whitespace-nowrap shrink-0"
                    >
                      <span class="whitespace-nowrap">{{ item.subject_type === 'project' ? '项目全员' : '指定成员' }}</span>
                    </StatusPill>
                    <span
                      v-if="item.subject_type === 'user'"
                      class="font-mono text-xs text-gray-600 dark:text-dark-300 whitespace-nowrap"
                    >
                      {{ memberNameMap.get(item.subject_id) || item.subject_id.slice(0, 8) + '…' }}
                    </span>
                  </div>
                  <!-- 并集提示 -->
                  <div
                    v-if="isProjectAlsoDisabled(item)"
                    class="mt-1 text-[11px] text-amber-600 dark:text-amber-400 whitespace-normal"
                  >
                    ⚠️ 项目全员已禁用，删除此单人规则后该用户仍受限
                  </div>
                </td>

                <!-- Graph -->
                <td class="whitespace-nowrap px-4 py-3 font-mono text-xs text-gray-600 dark:text-dark-300">
                  {{ item.graph_id }}
                </td>

                <!-- 工具名 -->
                <td class="whitespace-nowrap px-4 py-3">
                  <span class="inline-block whitespace-nowrap rounded bg-rose-50 px-2 py-0.5 font-mono text-xs font-semibold text-rose-700 dark:bg-rose-950/40 dark:text-rose-400">
                    {{ item.tool_name }}
                  </span>
                </td>

                <!-- 原因 -->
                <td class="max-w-[200px] px-4 py-3 text-xs text-gray-600 dark:text-dark-300">
                  <span
                    class="line-clamp-1 break-words"
                    :title="item.reason"
                  >
                    {{ item.reason }}
                  </span>
                </td>

                <!-- 创建信息 -->
                <td class="whitespace-nowrap px-4 py-3 text-xs text-gray-400 dark:text-dark-500">
                  <div
                    class="font-mono text-gray-600 dark:text-dark-300"
                    :title="item.created_by"
                  >
                    {{ formatCreator(item.created_by) }}
                  </div>
                  <div class="text-[11px] text-gray-400">
                    {{ formatDateTime(item.created_at) }}
                  </div>
                </td>

                <!-- 操作 -->
                <td
                  v-if="canManage"
                  class="whitespace-nowrap px-4 py-3 text-right"
                >
                  <button
                    type="button"
                    class="inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg border border-rose-200/80 bg-rose-50/60 px-2.5 py-1 text-xs font-medium text-rose-600 shadow-2xs transition-all hover:border-rose-300 hover:bg-rose-100 hover:text-rose-700 active:scale-95 disabled:cursor-not-allowed disabled:opacity-50 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-400 dark:hover:border-rose-800 dark:hover:bg-rose-900/60 dark:hover:text-rose-200"
                    :disabled="deletingId === item.id"
                    title="解除此条工具禁用规则"
                    @click="openDeleteConfirm(item)"
                  >
                    <BaseIcon
                      v-if="deletingId === item.id"
                      name="refresh"
                      class="animate-spin"
                      size="xs"
                    />
                    <BaseIcon
                      v-else
                      name="trash"
                      size="xs"
                    />
                    <span class="whitespace-nowrap">{{ deletingId === item.id ? '正在解除…' : '解除禁用' }}</span>
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- 解除确认弹窗 -->
    <ConfirmDialog
      :show="showConfirmDelete"
      title="解除工具禁用规则"
      :message="`确定要解除该规则吗？解除后，${pendingDeleteItem?.subject_type === 'project' ? '项目全员' : (memberNameMap.get(pendingDeleteItem?.subject_id || '') || '指定成员')} 将恢复对工具【${pendingDeleteItem?.tool_name}】的调用能力。`"
      confirm-text="确认解除"
      cancel-text="取消"
      :danger="true"
      @confirm="executeDelete"
      @cancel="showConfirmDelete = false"
    />
  </BaseDialog>
</template>

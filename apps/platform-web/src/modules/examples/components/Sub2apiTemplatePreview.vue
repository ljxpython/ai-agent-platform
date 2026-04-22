<script setup lang="ts">
import { computed } from 'vue'
import { humanizeTemplateName, type Sub2apiTemplateItem } from '@/modules/examples/ui-assets-catalog'

type PreviewVariant =
  | 'auth'
  | 'table'
  | 'dashboard'
  | 'wizard'
  | 'dialog'
  | 'form'
  | 'media'
  | 'api'
  | 'state'
  | 'routing'
  | 'i18n'
  | 'engineering'
  | 'default'

const props = withDefaults(
  defineProps<{
    item: Sub2apiTemplateItem
    size?: 'compact' | 'expanded'
  }>(),
  {
    size: 'compact'
  }
)

const isExpanded = computed(() => props.size === 'expanded')

function hasTag(tag: string) {
  return props.item.tags.includes(tag)
}

const variant = computed<PreviewVariant>(() => {
  if (hasTag('auth')) return 'auth'
  if (hasTag('wizard')) return 'wizard'
  if (hasTag('dialog') && props.item.kind === 'component') return 'dialog'
  if (hasTag('media') || hasTag('upload')) return 'media'
  if (hasTag('chart') || hasTag('stats') || hasTag('ops')) return 'dashboard'
  if (hasTag('table') && hasTag('filters')) return 'table'
  if (hasTag('form')) return 'form'
  if (props.item.kind === 'engineering' && hasTag('api')) return 'api'
  if (props.item.kind === 'engineering' && hasTag('state')) return 'state'
  if (props.item.kind === 'engineering' && hasTag('routing')) return 'routing'
  if (props.item.kind === 'engineering' && hasTag('i18n')) return 'i18n'
  if (props.item.kind === 'engineering') return 'engineering'
  return 'default'
})

const title = computed(() => humanizeTemplateName(props.item.name))
const pathLabel = computed(() => props.item.previewPath || props.item.shortSource)

const kindLabel = computed(() => {
  if (props.item.kind === 'page') return 'PAGE'
  if (props.item.kind === 'component') return 'COMPONENT'
  return 'ENGINEERING'
})

const sceneLabel = computed(() => {
  if (variant.value === 'auth') return '认证流'
  if (variant.value === 'wizard') return '步骤引导'
  if (variant.value === 'table') return '列表管理'
  if (variant.value === 'dashboard') return '看板监控'
  if (variant.value === 'dialog') return '弹窗交互'
  if (variant.value === 'form') return '表单录入'
  if (variant.value === 'media') return '媒体预览'
  if (variant.value === 'api') return '接口封装'
  if (variant.value === 'state') return '状态管理'
  if (variant.value === 'routing') return '路由编排'
  if (variant.value === 'i18n') return '多语言'
  if (props.item.kind === 'page') return '页面骨架'
  if (props.item.kind === 'component') return '局部组件'
  return '工程支撑'
})

const introText = computed(() => {
  switch (variant.value) {
    case 'table':
      return '把筛选区、操作区、表格主体和分页同时放进一个真实容器里，接近后台列表页的实际视觉节奏。'
    case 'dashboard':
      return '指标卡、图表区和异常摘要一起展示，更接近成熟中台的总览或监控页，而不是几根抽象柱子。'
    case 'auth':
      return '认证页采用品牌信息和表单分栏，能直观看出登录首屏的真实布局感。'
    case 'wizard':
      return '用步骤条、表单区和操作区拼出引导流程，让预览像一个真的多步配置页面。'
    case 'dialog':
      return '保留背景页和浮层弹窗两层结构，点开就能看出它是页面内弹窗，而不是单独卡片。'
    case 'form':
      return '表单录入区、摘要区和主操作按钮会一起出现，更容易判断字段节奏和信息层级。'
    case 'media':
      return '把预览画布、文件信息和操作面板同时摆出来，方便理解媒体类页面的完整结构。'
    case 'api':
      return '按 playground 方式展示接口面板和响应区域，不再只是几根代码占位线。'
    case 'state':
      return '把状态面板、动作流和结果面板放在同一屏，更像真实的 store 调试视图。'
    case 'routing':
      return '路由列表、守卫标签和跳转关系会一起出现，更容易理解路由组织方式。'
    case 'i18n':
      return '直接把双语文案面板并排展示，能一眼看出多语言资源如何被组织。'
    case 'engineering':
      return '用文件树、代码区和工程说明拼成开发工作台，让工程模板也有“页面感”。'
    default:
      return '这是一块接近真实页面的展示舞台，不是简单放大缩略图，而是让你先看见模板到底像什么。'
  }
})

const previewTabs = computed(() => {
  switch (variant.value) {
    case 'table':
      return ['表格视图', '表单视图', '详情视图']
    case 'dashboard':
      return ['总览', '趋势', '异常']
    case 'auth':
      return ['登录', '注册']
    case 'wizard':
      return ['步骤一', '步骤二', '完成']
    case 'dialog':
      return ['列表页', '编辑弹窗']
    case 'form':
      return ['基础信息', '高级设置']
    case 'media':
      return ['预览区', '元数据']
    case 'api':
      return ['Request', 'Response']
    case 'state':
      return ['State', 'Actions']
    case 'routing':
      return ['Routes', 'Guard']
    case 'i18n':
      return ['zh-CN', 'en-US']
    case 'engineering':
      return ['结构', '源码']
    default:
      return ['概览', '细节']
  }
})

const primaryAction = computed(() => {
  switch (variant.value) {
    case 'table':
      return '新建'
    case 'dashboard':
      return '刷新'
    case 'auth':
      return '立即登录'
    case 'wizard':
      return '下一步'
    case 'dialog':
      return '编辑'
    case 'form':
      return '保存'
    case 'media':
      return '下载原件'
    case 'api':
      return '发送请求'
    case 'state':
      return '更新状态'
    case 'routing':
      return '预览路由'
    case 'i18n':
      return '切换语言'
    case 'engineering':
      return '查看结构'
    default:
      return '打开'
  }
})

const secondaryAction = computed(() => {
  switch (variant.value) {
    case 'table':
      return '导出'
    case 'dashboard':
      return '分享'
    case 'auth':
      return '帮助'
    case 'wizard':
      return '保存草稿'
    case 'dialog':
      return '关闭'
    case 'form':
      return '重置'
    case 'media':
      return '查看元数据'
    case 'api':
      return '复制 curl'
    case 'state':
      return '重置'
    case 'routing':
      return '守卫说明'
    case 'i18n':
      return '复制 key'
    case 'engineering':
      return '源码拆解'
    default:
      return '详情'
  }
})

const toolbarFilters = computed(() => {
  switch (variant.value) {
    case 'table':
      return ['状态', '负责人', '更新时间']
    case 'dashboard':
      return ['时间范围', '环境', '异常等级']
    case 'media':
      return ['文件类型', '上传人']
    case 'default':
      return ['关键词', '标签']
    default:
      return []
  }
})

const tableRows = computed(() =>
  [
    ['Agent Runtime', '运行中', 'admin', '2 分钟前'],
    ['Chat Session', '待处理', 'test', '9 分钟前'],
    ['Ops Dashboard', '已同步', 'ops', '16 分钟前'],
    ['Prompt Review', '需确认', 'pm', '34 分钟前'],
    ['Audit Export', '已完成', 'sec', '1 小时前']
  ].slice(0, isExpanded.value ? 5 : 3)
)

const dashboardStats = computed(() => [
  { label: '请求量', value: '128k', delta: '+12%' },
  { label: '成功率', value: '99.4%', delta: '+0.6%' },
  { label: '平均耗时', value: '426ms', delta: '-18ms' }
])

const alertItems = computed(() =>
  [
    ['高延迟', '2 条待处理'],
    ['令牌耗尽', '1 条警告'],
    ['同步异常', '今日 3 次']
  ].slice(0, isExpanded.value ? 3 : 2)
)

const codeLines = computed(() => {
  switch (variant.value) {
    case 'api':
      return [
        'export async function listAccounts(params) {',
        "  return client.get('/accounts', { params })",
        '}',
        '',
        'export async function updateAccount(id, payload) {',
        "  return client.patch(`/accounts/${id}`, payload)",
        '}'
      ]
    case 'routing':
      return [
        'const routes = [',
        "  { path: '/workspace/resources', meta: { title: 'Resources' } },",
        "  { path: '/workspace/resources/pages', meta: { section: 'pages' } },",
        ']',
        '',
        'router.beforeEach(applyWorkspaceGuard)'
      ]
    case 'i18n':
      return [
        "zhCN.nav.resources = '资源总览'",
        "zhCN.examples.preview = '页面展示'",
        '',
        "enUS.nav.resources = 'Resources'",
        "enUS.examples.preview = 'Preview'"
      ]
    default:
      return [
        'const workspace = defineStore(...)',
        'const pageFilters = reactive(...)',
        'const columns = buildColumns(...)',
        '',
        'export function useResourcePreview() {',
        '  return { workspace, pageFilters, columns }',
        '}'
      ]
  }
})

const fileTree = computed(() => {
  switch (variant.value) {
    case 'api':
      return ['api/', 'accounts.ts', 'client.ts']
    case 'routing':
      return ['router/', 'routes.ts', 'guards.ts']
    case 'i18n':
      return ['i18n/', 'zh-CN.ts', 'en-US.ts']
    default:
      return ['src/', 'modules/', 'preview.ts']
  }
})

const rootClass = computed(() =>
  isExpanded.value
    ? 'min-h-[540px] rounded-2xl p-5'
    : 'aspect-[16/10] rounded-2xl p-3'
)

const shellClass = computed(() =>
  isExpanded.value
    ? 'rounded-2xl p-5'
    : 'h-full rounded-xl p-3'
)

const titleClass = computed(() =>
  isExpanded.value
    ? 'mt-1 text-lg font-semibold text-slate-900 dark:text-white'
    : 'mt-1 truncate text-sm font-semibold text-slate-900 dark:text-white'
)

const browserPathClass = computed(() =>
  isExpanded.value
    ? 'px-4 py-1.5 text-xs'
    : 'px-3 py-1 text-[10px]'
)

const actionButtonClass = computed(() =>
  isExpanded.value
    ? 'rounded-xl px-3 py-2 text-xs font-medium'
    : 'rounded-lg px-2.5 py-1.5 text-[10px] font-medium'
)

const tagClass = computed(() =>
  isExpanded.value
    ? 'rounded-full border px-3 py-1 text-xs font-medium'
    : 'rounded-full border px-2 py-0.5 text-[10px] font-medium'
)

const variantToneClass = computed(() => {
  if (props.item.kind === 'page') {
    return {
      shell:
        'border-sky-200/80 bg-[radial-gradient(circle_at_top_right,rgba(56,189,248,0.18),transparent_28%),linear-gradient(180deg,rgba(240,249,255,0.98),rgba(255,255,255,0.98))] dark:border-sky-900/40 dark:bg-[radial-gradient(circle_at_top_right,rgba(56,189,248,0.14),transparent_28%),linear-gradient(180deg,rgba(15,23,42,0.98),rgba(2,6,23,0.98))]',
      chip: 'border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900/40 dark:bg-sky-950/20 dark:text-sky-300',
      primary: 'bg-[#1677ff] text-white shadow-[0_8px_18px_rgba(22,119,255,0.22)]',
      soft: 'bg-sky-50 text-sky-700 dark:bg-sky-950/25 dark:text-sky-300'
    }
  }

  if (props.item.kind === 'component') {
    return {
      shell:
        'border-emerald-200/80 bg-[radial-gradient(circle_at_top_right,rgba(16,185,129,0.16),transparent_28%),linear-gradient(180deg,rgba(236,253,245,0.98),rgba(255,255,255,0.98))] dark:border-emerald-900/40 dark:bg-[radial-gradient(circle_at_top_right,rgba(16,185,129,0.12),transparent_28%),linear-gradient(180deg,rgba(15,23,42,0.98),rgba(2,6,23,0.98))]',
      chip: 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/40 dark:bg-emerald-950/20 dark:text-emerald-300',
      primary: 'bg-emerald-600 text-white shadow-[0_8px_18px_rgba(5,150,105,0.22)]',
      soft: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/25 dark:text-emerald-300'
    }
  }

  return {
    shell:
      'border-amber-200/80 bg-[radial-gradient(circle_at_top_right,rgba(245,158,11,0.16),transparent_28%),linear-gradient(180deg,rgba(255,251,235,0.98),rgba(255,255,255,0.98))] dark:border-amber-900/40 dark:bg-[radial-gradient(circle_at_top_right,rgba(245,158,11,0.12),transparent_28%),linear-gradient(180deg,rgba(15,23,42,0.98),rgba(2,6,23,0.98))]',
    chip: 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-300',
    primary: 'bg-amber-500 text-white shadow-[0_8px_18px_rgba(245,158,11,0.22)]',
    soft: 'bg-amber-50 text-amber-700 dark:bg-amber-950/25 dark:text-amber-300'
  }
})
</script>

<template>
  <div
    class="relative overflow-hidden border shadow-sm"
    :class="[rootClass, variantToneClass.shell]"
  >
    <div class="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.65),transparent_36%)] dark:bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.06),transparent_28%)]" />

    <div
      class="relative border border-white/70 bg-white/94 shadow-[0_24px_48px_rgba(15,23,42,0.08)] dark:border-white/5 dark:bg-slate-950/92"
      :class="shellClass"
    >
      <div
        v-if="isExpanded"
        class="mb-4 flex flex-col gap-4 border-b border-slate-200/80 pb-4 dark:border-dark-800 lg:flex-row lg:items-start lg:justify-between"
      >
        <div class="min-w-0">
          <div class="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400 dark:text-dark-500">
            Playground Preview
          </div>
          <div :class="titleClass">
            {{ title }}
          </div>
          <p class="mt-2 max-w-3xl text-sm leading-7 text-slate-600 dark:text-dark-300">
            {{ introText }}
          </p>
        </div>

        <div class="flex flex-wrap gap-2">
          <span
            class="rounded-full border px-3 py-1 text-xs font-semibold"
            :class="variantToneClass.chip"
          >
            {{ sceneLabel }}
          </span>
          <span class="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-600 dark:border-dark-700 dark:bg-dark-900 dark:text-dark-200">
            {{ kindLabel }}
          </span>
        </div>
      </div>

      <div class="rounded-2xl border border-slate-200 bg-slate-50/90 shadow-[inset_0_1px_0_rgba(255,255,255,0.8)] dark:border-dark-800 dark:bg-dark-950/70">
        <div class="flex items-center gap-2 border-b border-slate-200 px-4 py-3 dark:border-dark-800">
          <span class="h-2.5 w-2.5 rounded-full bg-rose-300/90 dark:bg-rose-500/70" />
          <span class="h-2.5 w-2.5 rounded-full bg-amber-300/90 dark:bg-amber-500/70" />
          <span class="h-2.5 w-2.5 rounded-full bg-emerald-300/90 dark:bg-emerald-500/70" />
          <div
            class="ml-2 min-w-0 flex-1 truncate rounded-full border border-slate-200 bg-white font-medium text-slate-500 dark:border-dark-700 dark:bg-dark-900 dark:text-dark-300"
            :class="browserPathClass"
          >
            {{ pathLabel }}
          </div>
          <span
            class="hidden rounded-full border sm:inline-flex"
            :class="[variantToneClass.chip, tagClass]"
          >
            {{ sceneLabel }}
          </span>
        </div>

        <div class="p-4">
          <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div class="flex flex-wrap gap-2">
              <span
                v-for="(tab, index) in previewTabs"
                :key="tab"
                class="rounded-full border px-3 py-1.5 text-xs font-medium"
                :class="
                  index === 0
                    ? variantToneClass.chip
                    : 'border-slate-200 bg-white text-slate-500 dark:border-dark-700 dark:bg-dark-900 dark:text-dark-300'
                "
              >
                {{ tab }}
              </span>
            </div>

            <div class="flex flex-wrap gap-2 lg:justify-end">
              <button
                type="button"
                class="border border-slate-200 bg-white text-slate-600 dark:border-dark-700 dark:bg-dark-900 dark:text-dark-200"
                :class="actionButtonClass"
              >
                {{ secondaryAction }}
              </button>
              <button
                type="button"
                :class="[actionButtonClass, variantToneClass.primary]"
              >
                {{ primaryAction }}
              </button>
            </div>
          </div>

          <div
            v-if="toolbarFilters.length > 0"
            class="mt-3 flex flex-wrap gap-2"
          >
            <span
              v-for="filter in toolbarFilters"
              :key="filter"
              class="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs text-slate-500 dark:border-dark-700 dark:bg-dark-900 dark:text-dark-300"
            >
              {{ filter }}
            </span>
          </div>

          <div class="mt-4">
            <div
              v-if="variant === 'table'"
              class="overflow-hidden rounded-[18px] border border-slate-200 bg-white dark:border-dark-800 dark:bg-dark-900"
            >
              <div class="grid grid-cols-[1.4fr_0.9fr_0.8fr_0.9fr] gap-3 border-b border-slate-200 px-4 py-3 text-xs font-semibold text-slate-500 dark:border-dark-800 dark:text-dark-300">
                <div>名称</div>
                <div>状态</div>
                <div>负责人</div>
                <div>更新时间</div>
              </div>
              <div
                v-for="row in tableRows"
                :key="row[0]"
                class="grid grid-cols-[1.4fr_0.9fr_0.8fr_0.9fr] gap-3 border-b border-slate-100 px-4 py-3 text-sm text-slate-700 last:border-b-0 dark:border-dark-800 dark:text-dark-200"
              >
                <div class="truncate font-medium">
                  {{ row[0] }}
                </div>
                <div>
                  <span
                    class="rounded-full border px-2 py-0.5 text-xs"
                    :class="row[1] === '运行中' ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-amber-200 bg-amber-50 text-amber-700'"
                  >
                    {{ row[1] }}
                  </span>
                </div>
                <div>{{ row[2] }}</div>
                <div class="text-slate-500 dark:text-dark-300">
                  {{ row[3] }}
                </div>
              </div>
              <div class="flex items-center justify-between border-t border-slate-200 px-4 py-3 text-xs text-slate-500 dark:border-dark-800 dark:text-dark-300">
                <span>共 {{ isExpanded ? 32 : 18 }} 条记录</span>
                <div class="flex gap-1">
                  <span class="rounded-lg border border-slate-200 px-2 py-1 dark:border-dark-700">1</span>
                  <span class="rounded-lg border border-slate-200 px-2 py-1 dark:border-dark-700">2</span>
                  <span class="rounded-lg border border-slate-200 px-2 py-1 dark:border-dark-700">3</span>
                </div>
              </div>
            </div>

            <div
              v-else-if="variant === 'dashboard'"
              class="space-y-4"
            >
              <div class="grid gap-3 md:grid-cols-3">
                <div
                  v-for="card in dashboardStats"
                  :key="card.label"
                  class="rounded-[18px] border border-slate-200 bg-white p-4 dark:border-dark-800 dark:bg-dark-900"
                >
                  <div class="text-xs font-medium text-slate-500 dark:text-dark-300">
                    {{ card.label }}
                  </div>
                  <div class="mt-2 text-xl font-semibold text-slate-900 dark:text-white">
                    {{ card.value }}
                  </div>
                  <div class="mt-2 text-xs text-emerald-600 dark:text-emerald-300">
                    {{ card.delta }}
                  </div>
                </div>
              </div>
              <div class="grid gap-3 lg:grid-cols-[1.4fr_0.8fr]">
                <div class="rounded-[18px] border border-slate-200 bg-white p-4 dark:border-dark-800 dark:bg-dark-900">
                  <div class="mb-3 text-sm font-semibold text-slate-800 dark:text-white">
                    趋势概览
                  </div>
                  <div class="flex h-[220px] items-end gap-3">
                    <span
                      class="w-10 rounded-t-2xl bg-sky-200"
                      style="height: 34%;"
                    />
                    <span
                      class="w-10 rounded-t-2xl bg-sky-300"
                      style="height: 52%;"
                    />
                    <span
                      class="w-10 rounded-t-2xl bg-sky-400"
                      style="height: 71%;"
                    />
                    <span
                      class="w-10 rounded-t-2xl bg-cyan-300"
                      style="height: 46%;"
                    />
                    <span
                      class="w-10 rounded-t-2xl bg-cyan-400"
                      style="height: 84%;"
                    />
                    <span
                      class="w-10 rounded-t-2xl bg-cyan-500"
                      style="height: 63%;"
                    />
                  </div>
                </div>
                <div class="space-y-3">
                  <div
                    v-for="alert in alertItems"
                    :key="alert[0]"
                    class="rounded-[18px] border border-slate-200 bg-white p-4 dark:border-dark-800 dark:bg-dark-900"
                  >
                    <div class="text-sm font-semibold text-slate-800 dark:text-white">
                      {{ alert[0] }}
                    </div>
                    <div class="mt-2 text-xs text-slate-500 dark:text-dark-300">
                      {{ alert[1] }}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div
              v-else-if="variant === 'auth'"
              class="grid gap-4 lg:grid-cols-[1fr_0.95fr]"
            >
              <div class="rounded-2xl bg-gradient-to-br from-sky-500 via-cyan-500 to-teal-400 p-6 text-white shadow-[0_20px_40px_rgba(14,165,233,0.24)]">
                <div class="text-xs font-semibold uppercase tracking-[0.2em] text-white/75">
                  Platform Access
                </div>
                <div class="mt-4 text-3xl font-semibold">
                  Welcome Back
                </div>
                <p class="mt-3 max-w-md text-sm leading-7 text-white/85">
                  这是一个更接近真实登录页的预览容器，你能直接感受到品牌区、辅助说明和表单区的空间关系。
                </p>
                <div class="mt-6 flex gap-3">
                  <span class="rounded-full bg-white/16 px-4 py-2 text-xs">密码登录</span>
                  <span class="rounded-full bg-white/16 px-4 py-2 text-xs">组织接入</span>
                </div>
              </div>

              <div class="rounded-2xl border border-slate-200 bg-white p-6 dark:border-dark-800 dark:bg-dark-900">
                <div class="text-sm font-semibold text-slate-900 dark:text-white">
                  账号登录
                </div>
                <div class="mt-4 space-y-3">
                  <div class="rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-400 dark:border-dark-700 dark:text-dark-400">
                    邮箱地址
                  </div>
                  <div class="rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-400 dark:border-dark-700 dark:text-dark-400">
                    输入密码
                  </div>
                  <div class="flex items-center justify-between text-xs text-slate-500 dark:text-dark-300">
                    <span>保持登录</span>
                    <span>忘记密码？</span>
                  </div>
                </div>
                <div class="mt-5 rounded-xl bg-[#1677ff] px-4 py-3 text-center text-sm font-semibold text-white shadow-[0_10px_20px_rgba(22,119,255,0.2)]">
                  立即登录
                </div>
              </div>
            </div>

            <div
              v-else-if="variant === 'wizard'"
              class="space-y-4"
            >
              <div class="flex items-center gap-3">
                <div class="flex items-center gap-2">
                  <span class="flex h-8 w-8 items-center justify-center rounded-full bg-[#1677ff] text-xs font-semibold text-white">1</span>
                  <span class="text-sm font-medium text-slate-700 dark:text-dark-200">选择模板</span>
                </div>
                <div class="h-px flex-1 bg-slate-200 dark:bg-dark-700" />
                <div class="flex items-center gap-2">
                  <span class="flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold text-slate-500 dark:bg-dark-800 dark:text-dark-300">2</span>
                  <span class="text-sm text-slate-500 dark:text-dark-300">配置参数</span>
                </div>
                <div class="h-px flex-1 bg-slate-200 dark:bg-dark-700" />
                <div class="flex items-center gap-2">
                  <span class="flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold text-slate-500 dark:bg-dark-800 dark:text-dark-300">3</span>
                  <span class="text-sm text-slate-500 dark:text-dark-300">完成接入</span>
                </div>
              </div>

              <div class="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
                <div class="rounded-[18px] border border-slate-200 bg-white p-5 dark:border-dark-800 dark:bg-dark-900">
                  <div class="space-y-3">
                    <div class="rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-500 dark:border-dark-700 dark:text-dark-300">
                      项目名称
                    </div>
                    <div class="rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-500 dark:border-dark-700 dark:text-dark-300">
                      运行环境
                    </div>
                    <div class="rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-500 dark:border-dark-700 dark:text-dark-300">
                      目标账号
                    </div>
                  </div>
                </div>
                <div class="rounded-[18px] border border-slate-200 bg-white p-5 dark:border-dark-800 dark:bg-dark-900">
                  <div class="text-sm font-semibold text-slate-900 dark:text-white">
                    当前配置摘要
                  </div>
                  <div class="mt-4 space-y-2 text-sm text-slate-500 dark:text-dark-300">
                    <div>模板：{{ title }}</div>
                    <div>分类：{{ sceneLabel }}</div>
                    <div>借用点：{{ props.item.borrow.slice(0, 2).join(' / ') }}</div>
                  </div>
                </div>
              </div>
            </div>

            <div
              v-else-if="variant === 'dialog'"
              class="relative min-h-[260px] rounded-2xl border border-slate-200 bg-slate-100 p-4 dark:border-dark-800 dark:bg-dark-950"
            >
              <div class="space-y-3 opacity-70">
                <div class="flex items-center justify-between rounded-2xl bg-white px-4 py-3 dark:bg-dark-900">
                  <span class="text-sm font-semibold text-slate-800 dark:text-white">数据列表</span>
                  <span class="rounded-lg bg-[#1677ff] px-3 py-2 text-xs font-semibold text-white">新建</span>
                </div>
                <div class="rounded-2xl bg-white p-4 dark:bg-dark-900">
                  <div class="grid grid-cols-[1.3fr_0.8fr_0.9fr] gap-2 text-xs text-slate-400 dark:text-dark-500">
                    <div>名称</div>
                    <div>状态</div>
                    <div>操作</div>
                  </div>
                  <div class="mt-3 space-y-2">
                    <div class="h-10 rounded-xl bg-slate-50 dark:bg-dark-950" />
                    <div class="h-10 rounded-xl bg-slate-50 dark:bg-dark-950" />
                  </div>
                </div>
              </div>

              <div class="absolute inset-x-8 top-10 rounded-[22px] border border-white/90 bg-white p-5 shadow-[0_28px_60px_rgba(15,23,42,0.18)] dark:border-dark-700 dark:bg-dark-900">
                <div class="text-sm font-semibold text-slate-900 dark:text-white">
                  编辑配置
                </div>
                <div class="mt-4 space-y-3">
                  <div class="rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-500 dark:border-dark-700 dark:text-dark-300">
                    名称
                  </div>
                  <div class="rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-500 dark:border-dark-700 dark:text-dark-300">
                    描述
                  </div>
                </div>
                <div class="mt-5 flex justify-end gap-2">
                  <span class="rounded-xl border border-slate-200 px-4 py-2 text-xs dark:border-dark-700">取消</span>
                  <span class="rounded-xl bg-[#1677ff] px-4 py-2 text-xs font-semibold text-white">确认保存</span>
                </div>
              </div>
            </div>

            <div
              v-else-if="variant === 'form'"
              class="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]"
            >
              <div class="rounded-[18px] border border-slate-200 bg-white p-5 dark:border-dark-800 dark:bg-dark-900">
                <div class="grid gap-3 md:grid-cols-2">
                  <div class="rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-500 dark:border-dark-700 dark:text-dark-300">
                    名称
                  </div>
                  <div class="rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-500 dark:border-dark-700 dark:text-dark-300">
                    负责人
                  </div>
                  <div class="rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-500 dark:border-dark-700 dark:text-dark-300 md:col-span-2">
                    详细描述
                  </div>
                  <div class="rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-500 dark:border-dark-700 dark:text-dark-300">
                    生效时间
                  </div>
                  <div class="rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-500 dark:border-dark-700 dark:text-dark-300">
                    状态
                  </div>
                </div>
              </div>
              <div class="rounded-[18px] border border-slate-200 bg-white p-5 dark:border-dark-800 dark:bg-dark-900">
                <div class="text-sm font-semibold text-slate-900 dark:text-white">
                  提交摘要
                </div>
                <div class="mt-4 space-y-2 text-sm text-slate-500 dark:text-dark-300">
                  <div>最后编辑：2 分钟前</div>
                  <div>字段总数：12</div>
                  <div>校验状态：通过</div>
                </div>
              </div>
            </div>

            <div
              v-else-if="variant === 'media'"
              class="grid gap-4 lg:grid-cols-[1.35fr_0.85fr]"
            >
              <div class="rounded-[18px] border border-slate-200 bg-slate-950 p-4 dark:border-dark-800">
                <div class="flex h-[240px] items-center justify-center rounded-[16px] border border-white/10 bg-[radial-gradient(circle_at_center,rgba(56,189,248,0.24),transparent_56%)] text-white/70">
                  预览画布
                </div>
              </div>
              <div class="space-y-3">
                <div class="rounded-[18px] border border-slate-200 bg-white p-4 dark:border-dark-800 dark:bg-dark-900">
                  <div class="text-sm font-semibold text-slate-900 dark:text-white">
                    文件信息
                  </div>
                  <div class="mt-3 space-y-2 text-sm text-slate-500 dark:text-dark-300">
                    <div>格式：image/png</div>
                    <div>大小：2.1MB</div>
                    <div>分辨率：2048x1536</div>
                  </div>
                </div>
                <div class="rounded-[18px] border border-slate-200 bg-white p-4 dark:border-dark-800 dark:bg-dark-900">
                  <div class="space-y-2">
                    <div class="rounded-xl bg-slate-50 px-4 py-3 text-sm dark:bg-dark-950">
                      下载原件
                    </div>
                    <div class="rounded-xl bg-slate-50 px-4 py-3 text-sm dark:bg-dark-950">
                      复制链接
                    </div>
                    <div class="rounded-xl bg-slate-50 px-4 py-3 text-sm dark:bg-dark-950">
                      查看元数据
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div
              v-else-if="variant === 'api'"
              class="grid gap-4 lg:grid-cols-[0.8fr_1.2fr]"
            >
              <div class="rounded-[18px] border border-slate-200 bg-white p-4 dark:border-dark-800 dark:bg-dark-900">
                <div
                  v-for="file in fileTree"
                  :key="file"
                  class="rounded-xl px-3 py-2 text-sm text-slate-600 first:bg-slate-50 dark:text-dark-200 dark:first:bg-dark-950"
                >
                  {{ file }}
                </div>
              </div>
              <div class="rounded-[18px] border border-slate-800 bg-slate-950 p-4 text-slate-100">
                <div class="flex gap-2">
                  <span class="rounded-full bg-emerald-500/20 px-3 py-1 text-[11px] font-semibold text-emerald-300">GET</span>
                  <span class="rounded-full bg-sky-500/20 px-3 py-1 text-[11px] font-semibold text-sky-300">/accounts</span>
                </div>
                <pre class="mt-4 overflow-auto text-xs leading-7 text-slate-200"><code>{{ codeLines.join('\n') }}</code></pre>
              </div>
            </div>

            <div
              v-else-if="variant === 'state'"
              class="grid gap-4 lg:grid-cols-[0.95fr_1.05fr]"
            >
              <div class="rounded-[18px] border border-slate-200 bg-white p-5 dark:border-dark-800 dark:bg-dark-900">
                <div class="text-sm font-semibold text-slate-900 dark:text-white">
                  Store Snapshot
                </div>
                <div class="mt-4 space-y-3">
                  <div class="rounded-xl bg-slate-50 px-4 py-3 text-sm dark:bg-dark-950">
                    selectedProject: demo-workspace
                  </div>
                  <div class="rounded-xl bg-slate-50 px-4 py-3 text-sm dark:bg-dark-950">
                    filters.status: running
                  </div>
                  <div class="rounded-xl bg-slate-50 px-4 py-3 text-sm dark:bg-dark-950">
                    pageSize: 20
                  </div>
                </div>
              </div>
              <div class="rounded-[18px] border border-slate-200 bg-white p-5 dark:border-dark-800 dark:bg-dark-900">
                <div class="text-sm font-semibold text-slate-900 dark:text-white">
                  Action Flow
                </div>
                <div class="mt-4 space-y-3">
                  <div class="flex items-center gap-3">
                    <span class="h-10 w-10 rounded-2xl bg-[#1677ff]" />
                    <span class="text-sm text-slate-600 dark:text-dark-200">loadWorkspace()</span>
                  </div>
                  <div class="flex items-center gap-3">
                    <span class="h-10 w-10 rounded-2xl bg-emerald-500" />
                    <span class="text-sm text-slate-600 dark:text-dark-200">applyFilters()</span>
                  </div>
                  <div class="flex items-center gap-3">
                    <span class="h-10 w-10 rounded-2xl bg-amber-500" />
                    <span class="text-sm text-slate-600 dark:text-dark-200">syncSelection()</span>
                  </div>
                </div>
              </div>
            </div>

            <div
              v-else-if="variant === 'routing'"
              class="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]"
            >
              <div class="rounded-[18px] border border-slate-200 bg-white p-5 dark:border-dark-800 dark:bg-dark-900">
                <div class="space-y-3 text-sm text-slate-600 dark:text-dark-200">
                  <div>/workspace/resources</div>
                  <div>/workspace/resources/pages</div>
                  <div>/workspace/resources/components</div>
                  <div>/workspace/resources/engineering</div>
                </div>
              </div>
              <div class="rounded-[18px] border border-slate-800 bg-slate-950 p-5 text-slate-100">
                <div class="flex gap-2">
                  <span class="rounded-full bg-amber-500/20 px-3 py-1 text-[11px] font-semibold text-amber-300">guard</span>
                  <span class="rounded-full bg-sky-500/20 px-3 py-1 text-[11px] font-semibold text-sky-300">title</span>
                </div>
                <pre class="mt-4 text-xs leading-7 text-slate-200"><code>{{ codeLines.join('\n') }}</code></pre>
              </div>
            </div>

            <div
              v-else-if="variant === 'i18n'"
              class="grid gap-4 lg:grid-cols-2"
            >
              <div class="rounded-[18px] border border-slate-200 bg-white p-5 dark:border-dark-800 dark:bg-dark-900">
                <div class="text-sm font-semibold text-slate-900 dark:text-white">
                  zh-CN
                </div>
                <div class="mt-4 space-y-3 text-sm text-slate-500 dark:text-dark-300">
                  <div>examples.preview = 页面展示</div>
                  <div>examples.inspect = 源码拆解</div>
                  <div>nav.resources = 资源总览</div>
                </div>
              </div>
              <div class="rounded-[18px] border border-slate-200 bg-white p-5 dark:border-dark-800 dark:bg-dark-900">
                <div class="text-sm font-semibold text-slate-900 dark:text-white">
                  en-US
                </div>
                <div class="mt-4 space-y-3 text-sm text-slate-500 dark:text-dark-300">
                  <div>examples.preview = Preview</div>
                  <div>examples.inspect = Inspect</div>
                  <div>nav.resources = Resources</div>
                </div>
              </div>
            </div>

            <div
              v-else
              class="grid gap-4 lg:grid-cols-[0.78fr_1.22fr]"
            >
              <div class="rounded-[18px] border border-slate-200 bg-white p-4 dark:border-dark-800 dark:bg-dark-900">
                <div
                  v-for="file in fileTree"
                  :key="file"
                  class="rounded-xl px-3 py-2 text-sm text-slate-600 first:bg-slate-50 dark:text-dark-200 dark:first:bg-dark-950"
                >
                  {{ file }}
                </div>
              </div>
              <div class="rounded-[18px] border border-slate-800 bg-slate-950 p-4 text-slate-100">
                <pre class="overflow-auto text-xs leading-7 text-slate-200"><code>{{ codeLines.join('\n') }}</code></pre>
              </div>
            </div>
          </div>

          <div
            v-if="isExpanded"
            class="mt-4 flex flex-wrap gap-2"
          >
            <span
              v-for="tag in props.item.tags.slice(0, 6)"
              :key="tag"
              class="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-500 dark:border-dark-700 dark:bg-dark-900 dark:text-dark-300"
            >
              {{ tag }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

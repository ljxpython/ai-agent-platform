<script setup lang="ts">
import PageHeader from '@/components/layout/PageHeader.vue'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import MetricCard from '@/components/platform/MetricCard.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import BrandMark from '@/components/layout/BrandMark.vue'

const stats = [
  {
    label: '核心原则',
    value: 3,
    hint: '功能看 platform-web，风格看 platform-web-vue，参考看 sub2api-base。',
    icon: 'check',
    tone: 'primary'
  },
  {
    label: '页面母版',
    value: 5,
    hint: '列表页、详情页、创建页、工作区页、资源页五类母版已经收敛。',
    icon: 'folder',
    tone: 'success'
  },
  {
    label: '统一组件层',
    value: 4,
    hint: '基础输入、表格体系、顶栏下拉、状态反馈必须走公共组件。',
    icon: 'users',
    tone: 'warning'
  },
  {
    label: '推荐动作',
    value: 10,
    hint: '每做一个新功能，都按固定开发清单推进，不再凭感觉拼页面。',
    icon: 'runtime',
    tone: 'primary'
  }
] as const

const principles = [
  {
    title: '功能真相源固定',
    description: '页面和功能是否完整，一律以 apps/platform-web 为准。platform-web-vue 负责统一体验与视觉升级，不另起一套业务真相。',
    icon: 'project'
  },
  {
    title: '风格和交互以当前 VUE 版为基线',
    description: '后续新增页面必须像当前 platform-web-vue，而不是每次重新试风格。sub2api-base 只作为参考源，不作为开发宿主。',
    icon: 'sparkle'
  },
  {
    title: '先选母版再写页面',
    description: '新需求先判断属于列表页、详情页、创建页还是工作区页，然后复用现有母版和组件，不按灵感重新排版。',
    icon: 'overview'
  }
] as const

const pagePatterns = [
  {
    title: '列表页',
    structure: 'PageHeader → 提示区 → 筛选区 → DataTable → BulkActionsBar → PaginationBar',
    usage: 'projects / users / assistants / audit / graphs / testcase',
    note: '禁止每页自己发明搜索框、分页条和空态。'
  },
  {
    title: '详情页',
    structure: 'PageHeader → 摘要卡区 → 分组内容区 → 关联资源区 → 最近活动',
    usage: 'project detail / user detail / assistant detail',
    note: '先概览后细节，不堆成长表单。'
  },
  {
    title: '创建 / 编辑页',
    structure: 'PageHeader → 说明区 → 主表单卡 → 附加配置卡 → 操作区',
    usage: 'new project / new user / new assistant / edit dialogs',
    note: '同类字段同组，危险操作分区。'
  },
  {
    title: '工作区页',
    structure: '上下文说明 → 主工作区 → 抽屉/侧栏辅助区 → 执行态/中断/错误分层展示',
    usage: 'chat / sql-agent / runtime / threads / testcase generate',
    note: '主路径永远优先，调试信息不要常驻主界面。'
  },
  {
    title: '资源 / 说明页',
    structure: 'PageHeader → StateBanner → 摘要统计 → 模板/说明卡片 → 入口导航',
    usage: 'resources / top-picks / playbook',
    note: '这类页面负责传达规范和模板，不承担正式业务。'
  }
] as const

const componentRules = [
  {
    title: '基础输入层',
    items: 'BaseInput / BaseSelect / BaseButton / BaseDialog / ConfirmDialog',
    description: '字段录入、按钮和弹窗结构必须统一，不再页面内重做一套样式。'
  },
  {
    title: '表格体系',
    items: 'DataTable / SearchInput / FilterToolbar / ActionMenu / PaginationBar',
    description: '列表页优先走统一表格母版，继续向 sub2api-base 学长列表性能和更成熟分页。'
  },
  {
    title: '顶栏下拉体系',
    items: 'TopContextBar / WorkspaceProjectSwitcher / LocaleSwitcher / AnnouncementCenter / UserMenu',
    description: '顶部不是业务页自由发挥区，项目切换、语言、公告、用户菜单必须使用同一触发器尺寸、同一 dropdown 壳层和同一文案层级。'
  },
  {
    title: '状态反馈体系',
    items: 'StateBanner / EmptyState / StatusPill / ToastStack / NavigationProgress',
    description: '空态、加载态、错误态、成功反馈都要走统一组件，不准只扔裸文案。'
  }
] as const

const workflow = [
  '先确认 apps/platform-web 里有没有对应功能和页面。',
  '判断页面类型，选列表页、详情页、创建页、工作区页或资源页母版。',
  '优先在 Resources 里看开发范式、团队推荐 Top 10，再决定借哪组模板。',
  '尽量复用现有基础组件和平台组件，不在业务页重新发明控件。',
  '同步检查浅色 / 深色模式、i18n 文案、空态、加载态和错误态。',
  '顶栏新增入口时，先复用 TopContextBar 现有触发器和 dropdown 语法，不准单页手搓新样式。',
  '最后再做视觉微调，而不是一开始就在颜色和特效上乱试。'
] as const

const resourceLinks = [
  {
    title: '资源总览',
    to: '/workspace/resources',
    description: '先看入口和分类，再判断自己该去页面模板、组件模板还是工程模板。',
    icon: 'sparkle'
  },
  {
    title: '团队推荐 Top 10',
    to: '/workspace/resources/top-picks',
    description: '如果不确定先看谁，直接从这 10 个固定模板开始。',
    icon: 'check'
  },
  {
    title: '页面模板',
    to: '/workspace/resources/pages',
    description: '要借后台页面骨架和信息层级，就从这里挑。',
    icon: 'folder'
  },
  {
    title: '组件模板',
    to: '/workspace/resources/components',
    description: '要借表格、分页、弹窗、状态块和壳层交互，就看这页。',
    icon: 'users'
  },
  {
    title: '工程模板',
    to: '/workspace/resources/engineering',
    description: '要学 API、store、router、i18n、composable 的接线方式，就看这页。',
    icon: 'runtime'
  }
] as const

const brandCandidates = [
  {
    title: 'Workspace Frame',
    variant: 'workspace-frame',
    file: 'src/assets/brand/mark-workspace-frame.svg',
    description: '左侧导航 + 主内容区的结构直接体现在图形里，最像正式控制台产品。',
    recommendation: '备选'
  },
  {
    title: 'Panel Stack',
    variant: 'panel-stack',
    file: 'src/assets/brand/mark-panel-stack.svg',
    description: '更偏现代 SaaS 的多层面板感，适合后续做更轻一点的品牌语气。',
    recommendation: '当前默认采用'
  },
  {
    title: 'PW Monogram',
    variant: 'monogram',
    file: 'src/assets/brand/mark-monogram.svg',
    description: '保留字母品牌识别，但比直接写 PW 更规整，适合保守路线。',
    recommendation: '备选'
  },
  {
    title: 'Control Plane Grid',
    variant: 'control-plane-grid',
    file: 'src/assets/brand/mark-control-plane-grid.svg',
    description: '更像总控台和平台网格，适合强调“控制台 / 控制面”的产品语义。',
    recommendation: '新增候选'
  },
  {
    title: 'Split Dock',
    variant: 'split-dock',
    file: 'src/assets/brand/mark-split-dock.svg',
    description: '导航与内容区切分更明显，整体更偏平台壳层和工作区布局。',
    recommendation: '新增候选'
  },
  {
    title: 'Beacon Frame',
    variant: 'beacon-frame',
    file: 'src/assets/brand/mark-beacon-frame.svg',
    description: '更偏品牌化的控制中心符号，比字母方案更稳，也不会有 AI 味。',
    recommendation: '新增候选'
  }
] as const
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Resources"
      title="前端开发范式"
      description="这页不展示模板源码，而是把 platform-web-vue 的正式开发规则、页面母版和组件复用方式固定下来。后续开发者默认先看这里，再去挑模板。"
    />

    <StateBanner
      title="统一前端口径"
      description="从这一版开始，Resources 不只是模板仓。这里同时承担团队前端开发手册的角色，避免后续再回 sub2api-base 四处翻源码找感觉。"
      variant="info"
    />

    <div class="grid gap-4 xl:grid-cols-4">
      <MetricCard
        v-for="item in stats"
        :key="item.label"
        :label="item.label"
        :value="item.value"
        :hint="item.hint"
        :icon="item.icon"
        :tone="item.tone"
      />
    </div>

    <SurfaceCard>
      <div class="pw-page-eyebrow">
        Brand Marks
      </div>
      <h2 class="mt-1 text-xl font-semibold text-gray-900 dark:text-white">
        品牌图标候选
      </h2>
      <p class="mt-2 text-sm leading-7 text-gray-500 dark:text-dark-300">
        这组 SVG 都已经落到仓库里，后续如果要换 favicon、登录页和侧栏品牌区，只需要切换同一套资源，不要再使用临时字母标识。
      </p>
      <div class="mt-5 grid gap-4 xl:grid-cols-3">
        <article
          v-for="item in brandCandidates"
          :key="item.title"
          class="pw-panel-lg"
        >
          <div class="flex items-start justify-between gap-4">
            <div class="flex h-16 w-16 items-center justify-center overflow-hidden rounded-2xl">
              <BrandMark
                :variant="item.variant"
                :alt="item.title"
              />
            </div>
            <div class="pw-panel-info px-3 py-1 text-xs font-medium text-sky-700 dark:text-sky-200">
              {{ item.recommendation }}
            </div>
          </div>
          <h3 class="mt-4 text-lg font-semibold text-gray-900 dark:text-white">
            {{ item.title }}
          </h3>
          <p class="mt-2 text-sm leading-7 text-gray-500 dark:text-dark-300">
            {{ item.description }}
          </p>
          <div class="pw-panel-muted mt-4 px-4 py-3 font-mono text-xs text-gray-600 dark:text-dark-300">
            {{ item.file }}
          </div>
        </article>
      </div>
    </SurfaceCard>

    <SurfaceCard>
      <div class="pw-page-eyebrow">
        Core Principles
      </div>
      <h2 class="mt-1 text-xl font-semibold text-gray-900 dark:text-white">
        三条总原则
      </h2>
      <div class="mt-5 grid gap-4 xl:grid-cols-3">
        <article
          v-for="item in principles"
          :key="item.title"
          class="pw-panel-lg"
        >
          <div class="flex h-11 w-11 items-center justify-center rounded-2xl bg-sky-50 text-sky-500 dark:bg-sky-950/30 dark:text-sky-300">
            <BaseIcon
              :name="item.icon as never"
              size="md"
            />
          </div>
          <h3 class="mt-4 text-lg font-semibold text-gray-900 dark:text-white">
            {{ item.title }}
          </h3>
          <p class="mt-2 text-sm leading-7 text-gray-500 dark:text-dark-300">
            {{ item.description }}
          </p>
        </article>
      </div>
    </SurfaceCard>

    <div class="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_380px]">
      <SurfaceCard>
        <div class="pw-page-eyebrow">
          Page Patterns
        </div>
        <h2 class="mt-1 text-xl font-semibold text-gray-900 dark:text-white">
          标准页面母版
        </h2>
        <div class="mt-5 space-y-4">
          <article
            v-for="pattern in pagePatterns"
            :key="pattern.title"
            class="pw-panel-lg"
          >
            <div class="flex items-start justify-between gap-4">
              <div>
                <h3 class="text-lg font-semibold text-gray-900 dark:text-white">
                  {{ pattern.title }}
                </h3>
                <p class="mt-2 text-sm leading-7 text-gray-500 dark:text-dark-300">
                  {{ pattern.structure }}
                </p>
              </div>
              <div class="rounded-full border border-gray-200 bg-white px-3 py-1 text-xs font-medium text-gray-600 dark:border-dark-700 dark:bg-dark-900 dark:text-dark-200">
                母版
              </div>
            </div>

            <div class="mt-4 grid gap-3 lg:grid-cols-[180px_minmax(0,1fr)]">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-500">
                适用范围
              </div>
              <div class="text-sm text-gray-700 dark:text-dark-200">
                {{ pattern.usage }}
              </div>

              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-500">
                约束
              </div>
              <div class="text-sm text-gray-700 dark:text-dark-200">
                {{ pattern.note }}
              </div>
            </div>
          </article>
        </div>
      </SurfaceCard>

      <SurfaceCard>
        <div class="pw-page-eyebrow">
          Workflow
        </div>
        <h2 class="mt-1 text-xl font-semibold text-gray-900 dark:text-white">
          开发动作顺序
        </h2>
        <div class="mt-5 space-y-3">
          <div
            v-for="(item, index) in workflow"
            :key="item"
            class="pw-panel-muted"
          >
            <div class="flex items-start gap-3">
              <div class="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-white text-xs font-semibold text-gray-700 shadow-sm dark:bg-dark-900 dark:text-dark-100">
                {{ index + 1 }}
              </div>
              <p class="text-sm leading-7 text-gray-600 dark:text-dark-300">
                {{ item }}
              </p>
            </div>
          </div>
        </div>
      </SurfaceCard>
    </div>

    <SurfaceCard>
      <div class="pw-page-eyebrow">
        Shared Systems
      </div>
      <h2 class="mt-1 text-xl font-semibold text-gray-900 dark:text-white">
        必须统一的组件体系
      </h2>
      <div class="mt-5 grid gap-4 xl:grid-cols-2">
        <article
          v-for="rule in componentRules"
          :key="rule.title"
          class="pw-panel-lg"
        >
          <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-500">
            {{ rule.title }}
          </div>
          <div class="mt-2 text-base font-semibold text-gray-900 dark:text-white">
            {{ rule.items }}
          </div>
          <p class="mt-3 text-sm leading-7 text-gray-500 dark:text-dark-300">
            {{ rule.description }}
          </p>
        </article>
      </div>
    </SurfaceCard>

    <SurfaceCard>
      <div class="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div class="pw-page-eyebrow">
            Resource Entry
          </div>
          <h2 class="mt-1 text-xl font-semibold text-gray-900 dark:text-white">
            Resources 使用顺序
          </h2>
          <p class="mt-2 max-w-4xl text-sm leading-7 text-gray-500 dark:text-dark-300">
            以后不用再跳回 sub2api-base 找参考。先看范式页，再按需要进入推荐模板、页面模板、组件模板和工程模板。
          </p>
        </div>
      </div>

      <div class="mt-6 grid gap-4 xl:grid-cols-5">
        <router-link
          v-for="entry in resourceLinks"
          :key="entry.to"
          :to="entry.to"
          class="pw-panel-lg transition hover:border-gray-300 dark:hover:border-dark-600"
        >
          <div class="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary-50 text-primary-500 dark:bg-primary-950/30 dark:text-primary-300">
            <BaseIcon
              :name="entry.icon as never"
              size="md"
            />
          </div>
          <h3 class="mt-4 text-base font-semibold text-gray-900 dark:text-white">
            {{ entry.title }}
          </h3>
          <p class="mt-2 text-sm leading-7 text-gray-500 dark:text-dark-300">
            {{ entry.description }}
          </p>
        </router-link>
      </div>
    </SurfaceCard>
  </section>
</template>

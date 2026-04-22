import {
  allSub2apiTemplates,
  type Sub2apiTemplateItem,
  type TemplateMode
} from '@/modules/examples/ui-assets-catalog'

export type TemplateExplorerLayer = 'recommended' | 'scenes' | 'library'

export type TemplateExplorerLayerOption = {
  key: TemplateExplorerLayer
  label: string
  description: string
}

export type TemplateScene = {
  key: string
  mode: TemplateMode
  title: string
  description: string
  guidance: string
  items: Sub2apiTemplateItem[]
}

type SceneDefinition = Omit<TemplateScene, 'items' | 'mode'> & {
  sources: string[]
}

export type TeamRecommendedTemplate = {
  rank: number
  reason: string
  item: Sub2apiTemplateItem
}

type TeamRecommendedDefinition = {
  source: string
  reason: string
}

const templateIndex = new Map(
  allSub2apiTemplates.map((item) => [item.shortSource.replace(/^src\//, ''), item])
)

function pickTemplates(sources: readonly string[]) {
  return sources
    .map((source) => templateIndex.get(source))
    .filter((item): item is Sub2apiTemplateItem => Boolean(item))
}

function uniqueTemplateCount(scenes: TemplateScene[]) {
  return new Set(scenes.flatMap((scene) => scene.items.map((item) => item.id))).size
}

function uniqueTemplates(items: readonly Sub2apiTemplateItem[]) {
  return Array.from(new Map(items.map((item) => [item.id, item])).values())
}

export const templateExplorerLayers: TemplateExplorerLayerOption[] = [
  {
    key: 'recommended',
    label: '推荐模板',
    description: '默认只展示最值得优先借用的代表模板，先解决“该选谁”。'
  },
  {
    key: 'scenes',
    label: '场景模板',
    description: '按列表、看板、认证、弹窗、工程接线这些真实开发场景收口。'
  },
  {
    key: 'library',
    label: '模板库',
    description: '把推荐模板和场景模板去重后并成一个可搜索模板库，只保留值得直接看的可视化模板。'
  }
]

const recommendedSourceMap = {
  pages: [
    'views/auth/LoginView.vue',
    'views/admin/UsersView.vue',
    'views/admin/AccountsView.vue',
    'views/admin/UsageView.vue',
    'views/admin/AnnouncementsView.vue',
    'views/admin/DashboardView.vue',
    'views/admin/ops/OpsDashboard.vue',
    'views/setup/SetupWizardView.vue',
    'views/user/ProfileView.vue',
    'views/user/SoraView.vue'
  ],
  components: [
    'components/layout/AppLayout.vue',
    'components/layout/AppSidebar.vue',
    'components/layout/AppHeader.vue',
    'components/layout/TablePageLayout.vue',
    'components/common/DataTable.vue',
    'components/common/SearchInput.vue',
    'components/common/Pagination.vue',
    'components/common/BaseDialog.vue',
    'components/common/ConfirmDialog.vue',
    'components/common/LocaleSwitcher.vue',
    'components/common/AnnouncementBell.vue',
    'components/admin/account/AccountBulkActionsBar.vue',
    'components/admin/account/AccountTableFilters.vue',
    'components/common/StatCard.vue',
    'components/charts/TokenUsageTrend.vue'
  ],
  engineering: [
    'App.vue',
    'main.ts',
    'api/client.ts',
    'api/admin/accounts.ts',
    'api/admin/users.ts',
    'api/admin/usage.ts',
    'composables/useKeyedDebouncedSearch.ts',
    'composables/usePersistedPageSize.ts',
    'composables/useTableLoader.ts',
    'composables/useTableSelection.ts',
    'stores/auth.ts',
    'router/index.ts',
    'i18n/index.ts'
  ]
} as const satisfies Record<TemplateMode, readonly string[]>

const sceneDefinitionMap: Record<TemplateMode, SceneDefinition[]> = {
  pages: [
    {
      key: 'page-admin-list',
      title: '后台列表页',
      description: '做后台管理页时，先从这组页面骨架里挑，不要重新拼列表节奏。',
      guidance: '优先借页面骨架、工具栏区和状态密度，表格细节再去组件模板里补。',
      sources: [
        'views/admin/UsersView.vue',
        'views/admin/AccountsView.vue',
        'views/admin/GroupsView.vue',
        'views/admin/UsageView.vue'
      ]
    },
    {
      key: 'page-dashboard-monitoring',
      title: '总览与监控页',
      description: '总览、趋势、异常、监控这些页面都在这里收口。',
      guidance: '先定信息层级，再挑指标卡和图表骨架，不要一上来就堆图。',
      sources: [
        'views/admin/DashboardView.vue',
        'views/admin/ops/OpsDashboard.vue',
        'views/user/DashboardView.vue',
        'views/HomeView.vue'
      ]
    },
    {
      key: 'page-auth-onboarding',
      title: '认证与引导页',
      description: '登录、注册、回调、校验和初始化向导属于同一套首屏与流程范式。',
      guidance: '借品牌区、表单分区和流程状态条，不要把认证页做成默认脚手架皮肤。',
      sources: [
        'views/auth/LoginView.vue',
        'views/auth/RegisterView.vue',
        'views/auth/EmailVerifyView.vue',
        'views/setup/SetupWizardView.vue'
      ]
    },
    {
      key: 'page-user-workspace',
      title: '用户工作台',
      description: '面向普通用户的个人中心、订阅、密钥和媒体页可以从这组开始。',
      guidance: '这组更适合低压信息密度页面，和后台管理页不要混用。',
      sources: [
        'views/user/ProfileView.vue',
        'views/user/KeysView.vue',
        'views/user/SubscriptionsView.vue',
        'views/user/SoraView.vue'
      ]
    }
  ],
  components: [
    {
      key: 'component-shell-system',
      title: '壳层与系统区',
      description: '做成熟后台观感时，壳层和系统区是第一优先级。',
      guidance: '先统一侧栏、顶栏、语言切换和公告入口，再谈业务页细节。',
      sources: [
        'components/layout/AppLayout.vue',
        'components/layout/AppSidebar.vue',
        'components/layout/AppHeader.vue',
        'components/common/LocaleSwitcher.vue',
        'components/common/AnnouncementBell.vue'
      ]
    },
    {
      key: 'component-list-tooling',
      title: '列表工具栏体系',
      description: '列表页真正值钱的是工具栏、筛选、分页、批量操作，而不是单独一张表。',
      guidance: '新列表页默认从这组开始选，除非需求特殊，否则不要重新造一套表格交互。',
      sources: [
        'components/layout/TablePageLayout.vue',
        'components/common/DataTable.vue',
        'components/common/SearchInput.vue',
        'components/common/Pagination.vue',
        'components/admin/account/AccountTableFilters.vue',
        'components/admin/account/AccountBulkActionsBar.vue'
      ]
    },
    {
      key: 'component-dialog-editing',
      title: '弹窗与编辑流',
      description: '确认、编辑、新建、清理这类动作都应该在统一弹层范式里完成。',
      guidance: '先借基础弹层和确认弹层，再看领域编辑弹窗怎么组织表单与动作按钮。',
      sources: [
        'components/common/BaseDialog.vue',
        'components/common/ConfirmDialog.vue',
        'components/account/CreateAccountModal.vue',
        'components/admin/user/UserEditModal.vue',
        'components/admin/usage/UsageCleanupDialog.vue'
      ]
    },
    {
      key: 'component-metrics-charts',
      title: '指标卡与图表区',
      description: '做总览、监控和运营页时，先从指标卡和趋势图这组出发。',
      guidance: '先定卡片节奏和图表组合，不要让每个指标区都长得像一套新东西。',
      sources: [
        'components/common/StatCard.vue',
        'components/charts/TokenUsageTrend.vue',
        'components/charts/GroupDistributionChart.vue',
        'components/admin/usage/UsageStatsCards.vue',
        'components/user/dashboard/UserDashboardStats.vue'
      ]
    },
    {
      key: 'component-auth-security',
      title: '认证与安全组件',
      description: '认证辅助、密码修改和 TOTP 这些交互适合放在一个篮子里看。',
      guidance: '统一错误提示、辅助说明和主按钮节奏，避免认证组件各写各的。',
      sources: [
        'components/auth/LinuxDoOAuthSection.vue',
        'components/auth/TotpLoginModal.vue',
        'components/user/profile/ProfilePasswordForm.vue',
        'components/user/profile/ProfileTotpCard.vue',
        'components/user/profile/TotpSetupModal.vue'
      ]
    }
  ],
  engineering: [
    {
      key: 'engineering-api-boundary',
      title: 'API 边界模板',
      description: '接口分层、client 封装和领域拆分应该先看这一组。',
      guidance: '公共 client 在前，领域 API 在后，别把业务语义和请求细节搅在一起。',
      sources: [
        'api/client.ts',
        'api/admin/accounts.ts',
        'api/admin/users.ts',
        'api/admin/usage.ts'
      ]
    },
    {
      key: 'engineering-table-state',
      title: '列表状态模板',
      description: '搜索、防抖、分页、装载和勾选态这些表格状态逻辑都集中在这里。',
      guidance: '列表页先复用这组工程模板，再去拼 UI，别把状态逻辑写回页面里。',
      sources: [
        'composables/useKeyedDebouncedSearch.ts',
        'composables/usePersistedPageSize.ts',
        'composables/useTableLoader.ts',
        'composables/useTableSelection.ts',
        'stores/app.ts'
      ]
    },
    {
      key: 'engineering-navigation',
      title: '路由与导航反馈',
      description: '路由表、标题管理和导航加载反馈是一整套系统能力。',
      guidance: '导航体验要统一，别让每个页面自己决定标题和切换反馈。',
      sources: [
        'router/index.ts',
        'router/title.ts',
        'composables/useNavigationLoading.ts',
        'composables/useRoutePrefetch.ts'
      ]
    },
    {
      key: 'engineering-i18n-bootstrap',
      title: '启动、国际化与主题',
      description: '应用启动接线、多语言和全局主题属于同一层面的工程骨架。',
      guidance: '这组决定全局一致性，后面页面再漂亮，底层接线烂了也会散架。',
      sources: [
        'App.vue',
        'main.ts',
        'i18n/index.ts',
        'i18n/locales/zh.ts',
        'i18n/locales/en.ts'
      ]
    }
  ]
}

export const recommendedTemplatesByMode = {
  pages: pickTemplates(recommendedSourceMap.pages),
  components: pickTemplates(recommendedSourceMap.components),
  engineering: pickTemplates(recommendedSourceMap.engineering)
} as const

const recommendedTemplateIdSet = new Set(
  Object.values(recommendedTemplatesByMode).flatMap((items) => items.map((item) => item.id))
)

export const recommendedTemplateStats = {
  pages: recommendedTemplatesByMode.pages.length,
  components: recommendedTemplatesByMode.components.length,
  engineering: recommendedTemplatesByMode.engineering.length,
  total:
    recommendedTemplatesByMode.pages.length +
    recommendedTemplatesByMode.components.length +
    recommendedTemplatesByMode.engineering.length
}

const teamRecommendedDefinitions: TeamRecommendedDefinition[] = [
  {
    source: 'components/layout/AppLayout.vue',
    reason: '后台主壳层的总骨架，决定侧栏、顶栏和主内容区的整体节奏。'
  },
  {
    source: 'components/layout/AppSidebar.vue',
    reason: '左侧主导航的层级、激活态和折叠逻辑都该先从这份模板借。'
  },
  {
    source: 'components/layout/AppHeader.vue',
    reason: '顶部上下文条、公告、语言切换和个人菜单的组织方式以它为准。'
  },
  {
    source: 'components/layout/TablePageLayout.vue',
    reason: '后台列表页最常见的工具栏加内容区节奏，别再每页重拼。'
  },
  {
    source: 'views/admin/UsersView.vue',
    reason: '最典型的后台管理页成品参考，筛选、表格和弹窗动作都比较完整。'
  },
  {
    source: 'views/admin/UsageView.vue',
    reason: '统计型列表页的卡片、筛选和表格组合已经跑通，适合做运营页母版。'
  },
  {
    source: 'components/common/DataTable.vue',
    reason: '表格头、单元格、空态和交互壳统一收口，新列表页优先复用它。'
  },
  {
    source: 'components/common/Pagination.vue',
    reason: '分页、页大小切换和翻页节奏不要重新造，这个模板已经够成熟。'
  },
  {
    source: 'components/common/BaseDialog.vue',
    reason: '编辑、新建、确认类弹层都应该从这个底座出发，别到处散。'
  },
  {
    source: 'composables/useTableLoader.ts',
    reason: '列表装载、翻页和刷新状态的工程逻辑靠它兜底，值钱得很。'
  }
]

export const teamRecommendedTemplates = teamRecommendedDefinitions
  .map((entry, index) => {
    const item = templateIndex.get(entry.source)

    if (!item) {
      return null
    }

    return {
      rank: index + 1,
      reason: entry.reason,
      item
    }
  })
  .filter((item): item is TeamRecommendedTemplate => Boolean(item))

const teamRecommendedMetaById = new Map(
  teamRecommendedTemplates.map((item) => [
    item.item.id,
    {
      rank: item.rank,
      reason: item.reason
    }
  ])
)

export const teamRecommendedTemplatesByMode = {
  pages: teamRecommendedTemplates.filter((item) => item.item.mode === 'pages'),
  components: teamRecommendedTemplates.filter((item) => item.item.mode === 'components'),
  engineering: teamRecommendedTemplates.filter((item) => item.item.mode === 'engineering')
} as const

export const teamRecommendedStats = {
  pages: teamRecommendedTemplatesByMode.pages.length,
  components: teamRecommendedTemplatesByMode.components.length,
  engineering: teamRecommendedTemplatesByMode.engineering.length,
  total: teamRecommendedTemplates.length
}

export function getTemplateCurationMeta(item: Sub2apiTemplateItem) {
  const teamRecommended = teamRecommendedMetaById.get(item.id)

  return {
    isRecommended: recommendedTemplateIdSet.has(item.id),
    isTeamRecommended: Boolean(teamRecommended),
    teamRank: teamRecommended?.rank ?? null,
    teamReason: teamRecommended?.reason ?? ''
  }
}

export function sortTemplatesByRecommendation(items: readonly Sub2apiTemplateItem[]) {
  return [...items]
    .map((item, index) => ({
      item,
      index,
      meta: getTemplateCurationMeta(item)
    }))
    .sort((left, right) => {
      if (left.meta.teamRank && right.meta.teamRank) {
        return left.meta.teamRank - right.meta.teamRank
      }

      if (left.meta.teamRank) {
        return -1
      }

      if (right.meta.teamRank) {
        return 1
      }

      return left.index - right.index
    })
    .map((entry) => entry.item)
}

export const templateScenesByMode = {
  pages: sceneDefinitionMap.pages.map((scene) => ({
    ...scene,
    mode: 'pages' as const,
    items: pickTemplates(scene.sources)
  })),
  components: sceneDefinitionMap.components.map((scene) => ({
    ...scene,
    mode: 'components' as const,
    items: pickTemplates(scene.sources)
  })),
  engineering: sceneDefinitionMap.engineering.map((scene) => ({
    ...scene,
    mode: 'engineering' as const,
    items: pickTemplates(scene.sources)
  }))
} as const

export const templateSceneStats = {
  pages: {
    sceneCount: templateScenesByMode.pages.length,
    templateCount: uniqueTemplateCount(templateScenesByMode.pages)
  },
  components: {
    sceneCount: templateScenesByMode.components.length,
    templateCount: uniqueTemplateCount(templateScenesByMode.components)
  },
  engineering: {
    sceneCount: templateScenesByMode.engineering.length,
    templateCount: uniqueTemplateCount(templateScenesByMode.engineering)
  }
}

export const curatedTemplatesByMode = {
  pages: uniqueTemplates([
    ...recommendedTemplatesByMode.pages,
    ...templateScenesByMode.pages.flatMap((scene) => scene.items)
  ]),
  components: uniqueTemplates([
    ...recommendedTemplatesByMode.components,
    ...templateScenesByMode.components.flatMap((scene) => scene.items)
  ]),
  engineering: uniqueTemplates([
    ...recommendedTemplatesByMode.engineering,
    ...templateScenesByMode.engineering.flatMap((scene) => scene.items)
  ])
} as const

export const curatedTemplateStats = {
  pages: curatedTemplatesByMode.pages.length,
  components: curatedTemplatesByMode.components.length,
  engineering: curatedTemplatesByMode.engineering.length,
  total:
    curatedTemplatesByMode.pages.length +
    curatedTemplatesByMode.components.length +
    curatedTemplatesByMode.engineering.length
}

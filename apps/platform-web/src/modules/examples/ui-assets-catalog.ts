import {
  componentTemplateSources,
  engineeringTemplateSources,
  pageTemplateSources
} from '@/modules/examples/template-source-manifest'

export type TemplateMode = 'pages' | 'components' | 'engineering'
export type TemplateKind = 'page' | 'component' | 'engineering'

export type Sub2apiTemplateItem = {
  id: string
  kind: TemplateKind
  mode: TemplateMode
  name: string
  source: string
  shortSource: string
  groupKey: string
  groupTitle: string
  groupDescription: string
  sceneLabel: string
  previewPath?: string
  note?: string
  summary: string
  tags: string[]
  borrow: string[]
}

export type Sub2apiTemplateGroup = {
  key: string
  title: string
  description: string
  mode: TemplateMode
  items: Sub2apiTemplateItem[]
}

export type Sub2apiTemplateDetail = {
  code: string
  lineCount: number
  imports: string[]
  blocks: {
    template?: string
    script?: string
    style?: string
  }
  tags: string[]
  borrow: string[]
}

export type TemplateModeOption = {
  key: TemplateMode
  label: string
  description: string
}

const repoSourceRoot = 'apps/platform-web/examples/sub2api-reference/src/'

const pageRouteMap: Record<string, string> = {
  'views/HomeView.vue': '/home',
  'views/KeyUsageView.vue': '/key-usage',
  'views/NotFoundView.vue': '/:pathMatch(.*)*',
  'views/setup/SetupWizardView.vue': '/setup',
  'views/auth/LoginView.vue': '/login',
  'views/auth/RegisterView.vue': '/register',
  'views/auth/EmailVerifyView.vue': '/email-verify',
  'views/auth/OAuthCallbackView.vue': '/auth/callback',
  'views/auth/LinuxDoCallbackView.vue': '/auth/linuxdo/callback',
  'views/auth/ForgotPasswordView.vue': '/forgot-password',
  'views/auth/ResetPasswordView.vue': '/reset-password',
  'views/user/DashboardView.vue': '/dashboard',
  'views/user/KeysView.vue': '/keys',
  'views/user/UsageView.vue': '/usage',
  'views/user/RedeemView.vue': '/redeem',
  'views/user/ProfileView.vue': '/profile',
  'views/user/SubscriptionsView.vue': '/subscriptions',
  'views/user/PurchaseSubscriptionView.vue': '/purchase',
  'views/user/SoraView.vue': '/sora',
  'views/user/CustomPageView.vue': '/custom/:id',
  'views/admin/DashboardView.vue': '/admin/dashboard',
  'views/admin/UsersView.vue': '/admin/users',
  'views/admin/GroupsView.vue': '/admin/groups',
  'views/admin/SubscriptionsView.vue': '/admin/subscriptions',
  'views/admin/AccountsView.vue': '/admin/accounts',
  'views/admin/AnnouncementsView.vue': '/admin/announcements',
  'views/admin/ProxiesView.vue': '/admin/proxies',
  'views/admin/RedeemView.vue': '/admin/redeem',
  'views/admin/PromoCodesView.vue': '/admin/promo-codes',
  'views/admin/SettingsView.vue': '/admin/settings',
  'views/admin/UsageView.vue': '/admin/usage',
  'views/admin/ops/OpsDashboard.vue': '/admin/ops'
}

const tagBorrowMap: Record<string, string[]> = {
  shell: ['整体布局节奏', '顶部上下文条', '侧边主导航'],
  table: ['表格骨架', '行级操作区', '字段密度控制'],
  filters: ['搜索与筛选区', '筛选状态表达', '工具栏布局'],
  pagination: ['分页节奏', '页大小切换'],
  dialog: ['弹窗开关状态', '编辑/确认弹窗结构'],
  form: ['字段编排', '录入反馈区', '校验交互'],
  chart: ['图表容器', '统计卡片排布'],
  stats: ['指标卡节奏', '摘要信息层级'],
  auth: ['认证分支编排', '错误提示块', '登录注册流转'],
  wizard: ['分步流程', '步骤状态条'],
  media: ['预览区', '下载/上传入口'],
  api: ['接口按领域拆分', '请求层边界'],
  state: ['状态收口', '页面状态共享'],
  composable: ['可复用逻辑封装', '交互能力抽离'],
  i18n: ['中英文文案归档', '语言切换接线'],
  routing: ['路由分层', '页面守卫与标题管理'],
  utils: ['纯函数工具集', '格式化与策略函数'],
  selection: ['批量选择', '勾选态同步'],
  importExport: ['导入导出入口', '异步进度反馈'],
  ops: ['监控看板结构', '告警与日志视图'],
  status: ['状态徽标', '风险状态表达'],
  upload: ['上传入口', '文件选择与回显']
}

export const templateModeOptions: TemplateModeOption[] = [
  {
    key: 'pages',
    label: '页面模板',
    description: '把上游页面一张张摊开，直接看每个页面适合承接什么业务。'
  },
  {
    key: 'components',
    label: '组件模板',
    description: '把列表、弹窗、图表、布局壳和领域组件按模板方式集中展示。'
  },
  {
    key: 'engineering',
    label: '工程模板',
    description: '把 API、store、composable、router、i18n 等工程支撑也收进来，方便整套学习。'
  }
]

function toRepoRelativePath(key: string) {
  const normalized = key.replace(/^(\.\.\/)+/, '')

  if (normalized.startsWith('examples/') || normalized.startsWith('src/')) {
    return `apps/platform-web/${normalized}`
  }

  return key
}

function toSourceRelativePath(source: string) {
  return source.replace(repoSourceRoot, '')
}

function fileNameFromSource(source: string) {
  const raw = source.split('/').pop() || source
  return raw.replace(/\.(vue|ts|css)$/, '')
}

function titleCaseSegment(value: string) {
  return value
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/[-_]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/^\w/, (char) => char.toUpperCase())
}

function unique(items: string[]) {
  return Array.from(new Set(items))
}

function inferPatternTags(lower: string) {
  const tags = new Set<string>()

  if (
    /(users|accounts|groups|subscriptions|usage|proxies|announcements|redeem|promo|keys|datatable|table)/.test(
      lower
    )
  ) {
    tags.add('table')
    tags.add('filters')
    tags.add('pagination')
  }

  if (/(bulk|selection|swipeselect)/.test(lower)) {
    tags.add('selection')
  }

  if (/(import|export)/.test(lower)) {
    tags.add('importExport')
  }

  if (/(dialog|modal|popup)/.test(lower)) {
    tags.add('dialog')
  }

  if (
    /(form|input|select|textarea|picker|editor|selector|profile|settings|setup|wizard|register|login|forgot|reset|verify|oauth|totp)/.test(
      lower
    )
  ) {
    tags.add('form')
  }

  if (/(login|register|forgot|reset|verify|oauth|totp|auth)/.test(lower)) {
    tags.add('auth')
  }

  if (/(setup|wizard|guide|onboarding|step)/.test(lower)) {
    tags.add('wizard')
  }

  if (/(dashboard|chart|trend|distribution|stats|metric|usage|quota|progress)/.test(lower)) {
    tags.add('chart')
    tags.add('stats')
  }

  if (/(layout|sidebar|header|navigation|bell|announcement|locale|menu|app\.vue|theme)/.test(lower)) {
    tags.add('shell')
  }

  if (/(status|badge|indicator|warning|alert)/.test(lower)) {
    tags.add('status')
  }

  if (/(image|media|preview|upload|download|sora)/.test(lower)) {
    tags.add('media')
  }

  if (/(upload)/.test(lower)) {
    tags.add('upload')
  }

  if (/(api\/|client\.ts|accounts\.ts|users\.ts|usage\.ts|subscriptions\.ts|auth\.ts|setup\.ts|sora\.ts)/.test(lower)) {
    tags.add('api')
  }

  if (/(stores\/|definestore|auth\.ts|app\.ts|subscriptions\.ts|adminsettings\.ts|announcements\.ts)/.test(lower)) {
    tags.add('state')
  }

  if (/(composables\/|^use[a-z]|\/use[a-z])/.test(lower)) {
    tags.add('composable')
  }

  if (/(i18n|locale)/.test(lower)) {
    tags.add('i18n')
  }

  if (/(router\/|route|navigationloading|prefetch)/.test(lower)) {
    tags.add('routing')
  }

  if (/(utils\/|format|sanitize|parser|policy|url|stableobjectkey)/.test(lower)) {
    tags.add('utils')
  }

  if (/(ops)/.test(lower)) {
    tags.add('ops')
  }

  return Array.from(tags)
}

function inferTags(kind: TemplateKind, source: string) {
  const lower = source.toLowerCase()
  const tags = new Set<string>(inferPatternTags(lower))

  if (kind === 'page') {
    tags.add('page')
  } else if (kind === 'component') {
    tags.add('component')
  } else {
    tags.add('engineering')
  }

  return Array.from(tags)
}

function inferBorrow(tags: string[]) {
  return unique(
    tags.flatMap((tag) => tagBorrowMap[tag] || []).filter(Boolean)
  ).slice(0, 6)
}

function inferSummary(kind: TemplateKind, tags: string[], source: string) {
  const shortSource = toSourceRelativePath(source)

  if (tags.includes('shell')) {
    return '适合直接借壳做后台整体框架、导航和顶部系统交互。'
  }

  if (tags.includes('table') && tags.includes('filters')) {
    return '适合后台管理列表页，筛选、排序、分页和动作区都能直接照着学。'
  }

  if (tags.includes('auth')) {
    return '适合登录、注册、回调、校验等认证链路页面或组件。'
  }

  if (tags.includes('wizard')) {
    return '适合初始化向导、多步骤配置或引导式流程页面。'
  }

  if (tags.includes('chart')) {
    return '适合总览、监控、运营分析类页面，强调指标卡和图表节奏。'
  }

  if (tags.includes('dialog') && tags.includes('form')) {
    return '适合新建/编辑/配置弹窗，直接复用字段布局和提交反馈结构。'
  }

  if (tags.includes('api')) {
    return '适合作为接口分层模板，按领域拆函数，方便迁移时保持边界清晰。'
  }

  if (tags.includes('state')) {
    return '适合作为 Pinia 状态模板，页面共享状态和全局状态都能按这个范式收口。'
  }

  if (tags.includes('composable')) {
    return '适合作为组合式能力模板，把交互逻辑从页面里抽出去，别把页面写成一锅粥。'
  }

  if (tags.includes('i18n')) {
    return '适合作为多语言模板，文案归档和语言切换接线都能直接照抄。'
  }

  if (tags.includes('routing')) {
    return '适合作为路由模板，守卫、标题和预加载这套组织方式很成熟。'
  }

  if (tags.includes('utils')) {
    return '适合作为前端工具函数模板，把格式化、策略判断和纯函数逻辑收敛出去。'
  }

  if (kind === 'page') {
    return `这是 ${shortSource} 的页面模板，适合先看整体布局和状态编排。`
  }

  if (kind === 'component') {
    return `这是 ${shortSource} 的组件模板，适合直接借局部交互和领域表达。`
  }

  return `这是 ${shortSource} 的工程模板，适合学习前端结构和支撑层拆分。`
}

function pageGroupMeta(sourceRelative: string) {
  if (sourceRelative.startsWith('views/admin/ops/components/')) {
    return {
      key: 'page-admin-ops-components',
      title: '运维监控子模板',
      description: '监控页内部拆出的卡片、图表、表格和明细弹窗模板。'
    }
  }

  if (sourceRelative.startsWith('views/admin/ops/')) {
    return {
      key: 'page-admin-ops',
      title: '运维监控页模板',
      description: '偏监控看板和可观测性视图，适合告警、日志、吞吐、错误追踪类页面。'
    }
  }

  if (sourceRelative.startsWith('views/admin/')) {
    return {
      key: 'page-admin',
      title: '后台管理页模板',
      description: '后台列表、配置、公告、账号、分组、用量这类重型管理页模板。'
    }
  }

  if (sourceRelative.startsWith('views/user/')) {
    return {
      key: 'page-user',
      title: '用户工作台模板',
      description: '普通用户侧 dashboard、个人中心、Keys、订阅和业务页模板。'
    }
  }

  if (sourceRelative.startsWith('views/auth/')) {
    return {
      key: 'page-auth',
      title: '认证页模板',
      description: '登录、注册、找回密码、回调和校验链路页模板。'
    }
  }

  if (sourceRelative.startsWith('views/setup/')) {
    return {
      key: 'page-setup',
      title: '初始化向导模板',
      description: '首次配置、多步骤流程和引导式页面模板。'
    }
  }

  return {
    key: 'page-public',
    title: '公开页模板',
    description: '公开落地页、无需登录页和系统兜底页模板。'
  }
}

function componentGroupMeta(sourceRelative: string) {
  const pairs: Array<[RegExp, { key: string; title: string; description: string }]> = [
    [
      /^components\/admin\/account\//,
      {
        key: 'component-admin-account',
        title: '后台账号模板',
        description: '后台账号管理用到的筛选、批量动作、测试、导入和行操作模板。'
      }
    ],
    [
      /^components\/admin\/user\//,
      {
        key: 'component-admin-user',
        title: '后台用户模板',
        description: '用户编辑、余额、分组替换和用户辅助弹窗模板。'
      }
    ],
    [
      /^components\/admin\/usage\//,
      {
        key: 'component-admin-usage',
        title: '后台用量模板',
        description: '用量筛选、统计卡、导出进度和表格模板。'
      }
    ],
    [
      /^components\/admin\/announcements\//,
      {
        key: 'component-admin-announcements',
        title: '公告模板',
        description: '公告投放和公告已读状态这类后台交互模板。'
      }
    ],
    [
      /^components\/admin\/group\//,
      {
        key: 'component-admin-group',
        title: '分组模板',
        description: '分组配置和倍率设置类模板。'
      }
    ],
    [
      /^components\/admin\/proxy\//,
      {
        key: 'component-admin-proxy',
        title: '代理模板',
        description: '代理配置与数据导入相关模板。'
      }
    ],
    [
      /^components\/admin\//,
      {
        key: 'component-admin',
        title: '后台管理组件模板',
        description: '后台管理类通用组件与弹窗模板。'
      }
    ],
    [
      /^components\/user\/dashboard\//,
      {
        key: 'component-user-dashboard',
        title: '用户看板模板',
        description: '用户 dashboard 的卡片、图表和快速动作模板。'
      }
    ],
    [
      /^components\/user\/profile\//,
      {
        key: 'component-user-profile',
        title: '用户资料模板',
        description: '用户资料与安全设置相关表单、信息卡和 TOTP 模板。'
      }
    ],
    [
      /^components\/user\//,
      {
        key: 'component-user',
        title: '用户侧组件模板',
        description: '普通用户侧字段、并发度、属性等局部交互模板。'
      }
    ],
    [
      /^components\/account\//,
      {
        key: 'component-account',
        title: '账号领域模板',
        description: '账号状态、用量、配额、编辑弹窗和授权流模板。'
      }
    ],
    [
      /^components\/common\//,
      {
        key: 'component-common',
        title: '通用基础组件模板',
        description: 'DataTable、Pagination、Input、Select、Toast、Dialog 这批基础模板。'
      }
    ],
    [
      /^components\/layout\//,
      {
        key: 'component-layout',
        title: '布局壳模板',
        description: '顶部、侧边栏、页面框架和表格页壳层模板。'
      }
    ],
    [
      /^components\/charts\//,
      {
        key: 'component-charts',
        title: '图表模板',
        description: '各类趋势、分布和拆分图表模板。'
      }
    ],
    [
      /^components\/auth\//,
      {
        key: 'component-auth',
        title: '认证组件模板',
        description: 'OAuth、TOTP 等认证辅助模板。'
      }
    ],
    [
      /^components\/keys\//,
      {
        key: 'component-keys',
        title: 'Key 交互模板',
        description: 'Key 使用说明和 Endpoint 交互模板。'
      }
    ],
    [
      /^components\/sora\//,
      {
        key: 'component-sora',
        title: 'Sora 业务模板',
        description: '媒体生成、预览、下载和配额表达模板。'
      }
    ],
    [
      /^components\/Guide\//,
      {
        key: 'component-guide',
        title: '引导模板',
        description: '新手引导步骤和 onboarding 支撑模板。'
      }
    ],
    [
      /^components\/icons\//,
      {
        key: 'component-icons',
        title: '图标模板',
        description: '图标封装和图标索引模板。'
      }
    ]
  ]

  const matched = pairs.find(([pattern]) => pattern.test(sourceRelative))
  if (matched) {
    return matched[1]
  }

  return {
    key: 'component-system',
    title: '系统接入模板',
    description: '零散但必要的系统接入组件模板。'
  }
}

function engineeringGroupMeta(sourceRelative: string) {
  const pairs: Array<[RegExp, { key: string; title: string; description: string }]> = [
    [
      /^api\/admin\//,
      {
        key: 'engineering-api-admin',
        title: '后台接口模板',
        description: '后台管理相关 API 封装，按领域拆分得比较清楚。'
      }
    ],
    [
      /^api\//,
      {
        key: 'engineering-api',
        title: '通用接口模板',
        description: '普通用户侧 API、公共 client 和接口入口模板。'
      }
    ],
    [
      /^composables\//,
      {
        key: 'engineering-composables',
        title: '组合式能力模板',
        description: '搜索、防抖、剪贴板、表格装载、导航加载等逻辑封装模板。'
      }
    ],
    [
      /^stores\//,
      {
        key: 'engineering-stores',
        title: '状态管理模板',
        description: 'Pinia store 组织方式和跨页状态模板。'
      }
    ],
    [
      /^router\//,
      {
        key: 'engineering-router',
        title: '路由模板',
        description: '路由表、守卫、页面标题和预加载相关模板。'
      }
    ],
    [
      /^i18n\/locales\//,
      {
        key: 'engineering-i18n-locales',
        title: '国际化文案模板',
        description: '中英文文案归档模板。'
      }
    ],
    [
      /^i18n\//,
      {
        key: 'engineering-i18n',
        title: '国际化接线模板',
        description: 'i18n 初始化与接线模板。'
      }
    ],
    [
      /^styles\//,
      {
        key: 'engineering-styles',
        title: '样式主题模板',
        description: '全局样式和主题变量组织模板。'
      }
    ],
    [
      /^types\//,
      {
        key: 'engineering-types',
        title: '类型模板',
        description: '类型声明和全局类型模板。'
      }
    ],
    [
      /^utils\//,
      {
        key: 'engineering-utils',
        title: '工具函数模板',
        description: '格式化、策略判断和纯函数工具模板。'
      }
    ],
    [
      /^views\/admin\/ops\//,
      {
        key: 'engineering-ops-support',
        title: '运维页支撑模板',
        description: '运维监控页的类型和格式化支撑模板。'
      }
    ]
  ]

  const matched = pairs.find(([pattern]) => pattern.test(sourceRelative))
  if (matched) {
    return matched[1]
  }

  return {
    key: 'engineering-bootstrap',
    title: '启动入口模板',
    description: '应用启动、根组件和入口文件模板。'
  }
}

function groupMetaByMode(mode: TemplateMode, sourceRelative: string) {
  if (mode === 'pages') {
    return pageGroupMeta(sourceRelative)
  }

  if (mode === 'components') {
    return componentGroupMeta(sourceRelative)
  }

  return engineeringGroupMeta(sourceRelative)
}

function sceneLabelByMode(mode: TemplateMode) {
  if (mode === 'pages') {
    return '页面模板'
  }

  if (mode === 'components') {
    return '组件模板'
  }

  return '工程模板'
}

function createTemplateItem(mode: TemplateMode, sourceKey: string): Sub2apiTemplateItem {
  const source = toRepoRelativePath(sourceKey)
  const sourceRelative = toSourceRelativePath(source)
  const kind: TemplateKind =
    mode === 'pages' ? 'page' : mode === 'components' ? 'component' : 'engineering'
  const tags = inferTags(kind, sourceRelative)
  const group = groupMetaByMode(mode, sourceRelative)
  const borrow = inferBorrow(tags)

  return {
    id: sourceRelative.replace(/[^a-zA-Z0-9]+/g, '-').toLowerCase(),
    kind,
    mode,
    name: fileNameFromSource(sourceRelative),
    source,
    shortSource: `src/${sourceRelative}`,
    groupKey: group.key,
    groupTitle: group.title,
    groupDescription: group.description,
    sceneLabel: sceneLabelByMode(mode),
    previewPath: mode === 'pages' ? pageRouteMap[sourceRelative] : undefined,
    note:
      mode === 'pages' && !pageRouteMap[sourceRelative]
        ? '这是页面或页面子模板源码，路由不一定直接暴露。'
        : undefined,
    summary: inferSummary(kind, tags, source),
    tags,
    borrow
  }
}

function buildGroups(mode: TemplateMode, sourceKeys: readonly string[]) {
  const items = [...sourceKeys]
    .sort((left, right) => left.localeCompare(right))
    .map((sourceKey) => createTemplateItem(mode, sourceKey))

  const groups = new Map<string, Sub2apiTemplateGroup>()

  for (const item of items) {
    const existing = groups.get(item.groupKey)

    if (existing) {
      existing.items.push(item)
      continue
    }

    groups.set(item.groupKey, {
      key: item.groupKey,
      title: item.groupTitle,
      description: item.groupDescription,
      mode,
      items: [item]
    })
  }

  return Array.from(groups.values())
}

export const sub2apiTemplateGroups = {
  pages: buildGroups('pages', pageTemplateSources),
  components: buildGroups('components', componentTemplateSources),
  engineering: buildGroups('engineering', engineeringTemplateSources)
} as const

export const sub2apiTemplateStats = {
  pages: sub2apiTemplateGroups.pages.reduce((total, group) => total + group.items.length, 0),
  components: sub2apiTemplateGroups.components.reduce((total, group) => total + group.items.length, 0),
  engineering: sub2apiTemplateGroups.engineering.reduce((total, group) => total + group.items.length, 0)
}

export const allSub2apiTemplates = [
  ...sub2apiTemplateGroups.pages.flatMap((group) => group.items),
  ...sub2apiTemplateGroups.components.flatMap((group) => group.items),
  ...sub2apiTemplateGroups.engineering.flatMap((group) => group.items)
]

export function relatedTemplatesOf(item: Sub2apiTemplateItem, size = 6) {
  return allSub2apiTemplates
    .filter((candidate) => candidate.id !== item.id && candidate.groupKey === item.groupKey)
    .slice(0, size)
}

export function humanizeTemplateName(name: string) {
  return titleCaseSegment(name)
}

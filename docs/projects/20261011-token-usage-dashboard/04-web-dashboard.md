# Web 看板与交互规范

## 目标

在正式平台壳层增加“Token 看板”，提供从全局/项目汇总到运行证据的端到端阅读路径。页面纯消费 Platform API，不连接 Runtime、不扫描聊天消息、不参与服务端聚合或财务重算。

## 方案设计

### 1. 路由与页面归属

- **平台入口**：`/workspace/usage`，导航组“平台管理”，`requiredPermissions=['platform.usage.read']`。
- **项目入口**：`/workspace/projects/:projectId/usage`，导航组“项目管理”，`requiredPermissions=['project.usage.read']`、`permissionProjectSource='route'`。
- **页面复用与作用域隔离**：
  - 两路由共用 `src/modules/usage/pages/UsageDashboardPage.vue`；
  - 页面通过路由路径派生当前作用域 `scope`（`platform` 或 `project`），**绝对禁止依赖顶栏项目切换改变平台视图**；
  - 平台页面标示“平台用量”，支持跨项目汇总与筛选；项目页面锁定路径项目，标示具体项目名称。
- **页面布局范式**：
  - 遵循 playbook 规范：`PageHeader → FilterToolbar → MetricCard(4卡) → 趋势/排行(双栏) → DataTable(运行明细)`；
  - 沿用现有 `WorkspaceLayout`、设计 tokens 与深浅双主题，不另建外部分析壳层。

### 2. 首屏交互草图

```text
Token 看板 · 平台用量                                     数据时间 10:42 · [手动刷新]
ℹ️ 已采集当前范围内 Agent 运行用量；辅助开销（标题生成、推荐问题等）未计入。汇总数据与供应商账单可能存在偏差。

[近7天 ▾] [时区: 上海 ▾] [粒度: 按日 ▾] [项目: 全部 ▾] [Agent: 禁用(多项目中) ▾] [模型: 全部 ▾] [更多筛选 ▾]
当前过滤：[模型: deepseek-v4.1-flash ×] [用途: agent ×]                            [重置所有条件]

┌ 已记录 Token ┐┌ 输入 / 输出 ┐┌ 估算成本 (USD) ┐┌ 已采集调用 / Run ┐
│ 1,100        ││ 1,000 / 100 ││ $0.00258       ││ 1 / 1           │
│ 较前窗 +10%  ││ 缓存200/推理30││ 计价缺失: 0   ││ 已报告率: 100%  │
└──────────────┘└─────────────┘└────────────────┘└──────────────────┘

┌ Token / 成本趋势 ─────────────────────────┐┌ 模型 / Agent / 项目排行分解 ─────────┐
│ [Token 堆叠] [成本折线] | [日] [小时] [表格]││ [维度: 模型 ▾] [指标: Token ▾]     │
│ 堆叠柱: 输入(蓝)+输出(绿); partial纹理    ││ 1. deepseek-v4.1-flash  1,100 (100%) │
│ null值展示为断口缺口，严禁画为0           ││ [展开“其他”维度]                     │
└───────────────────────────────────────────┘└───────────────────────────────────────┘

数据质量诊断：已观察 1；已报告 1；未结束 0；缺用量 0；未计价 0 | 采集状态：正常采集 | 记录起点：2026-10-01

运行明细（仅显示当前可查看的运行）
[平台全量模式引导]：平台视图下请在上方筛选具体项目以查看该项目的可访问运行明细。
(若已锁定项目，则展示明细表：时间 | Agent | 运行ID | 期间Token | 期间估算成本 | 覆盖率 | [查看用量])
[第一页/重新开始]                                                  [继续扫描下一批]
```

### 3. 指标、图形与筛选交互规约

1. **指标卡（MetricCard）**：
   - **Token 展现**：优先展示完整值；若是部分记录则打上 `partial` 标签展示“已知小计”；`null` 统一显示为 `—`，严禁补 0。
   - **集合关系与防重**：输入与输出为并列关系（总和即两者相加）；缓存读/写作为输入子行展示，推理作为输出子行展示，**严禁把子集与输入输出重复相加**。
   - **成本展示**：严格保留 12 位 USD 小数字符串，禁止转浮点数运算。复用 `formatCostUsd()`，极小正值渲染 `< $0.0001`，不显示免费。
2. **筛选工具栏（FilterToolbar）联动与防呆**：
   - **粒度与跨度联动防呆**：
     - 若 `granularity=hour`，时间跨度强约束 `to - from <= 7 天`；
     - 当用户切换到“小时”粒度，日期选择器自动将跨度收缩至 7 天内；若当前时间跨度 > 7 天，自动回退为“天”并禁用“小时”选项。
   - **项目与 Agent 联动防呆**：
     - 平台全量模式或选择了 ≥2 个项目时，**禁用 Agent 下拉框**，悬浮提示“请先限定单个项目”；
     - 仅当锁定了单个项目时，解禁 Agent 下拉并加载该项目的 Agent 列表。
   - **维度排行防呆**：
     - 单项目模式下，隐藏 `group_by=project` 选项（单项目无需对比）。
   - **互斥与序列化**：
     - `model_id` 与 `model_mapping=unmapped` 互斥绑定；
     - Axios 传参时 `project_ids` 强制使用原生重复键（`paramsSerializer: { indexes: null }`），绝不带中括号 `[]`；单项目模式严禁传 `project_ids`。
3. **原生 SVG 趋势图（UsageTrend.vue）**：
   - **免图表库设计**：采用模块内自研轻量 SVG，最多渲染 200 点，不引入第三方重型图表库。
   - **日/小时堆叠柱状图**：
     - 输入 Token（深蓝/主色）与输出 Token（翡翠绿）垂直堆叠；
     - `partial` 桶使用 SVG `<defs><pattern>` 斜条纹填充，悬浮展示“部分调用尚未完成”；
     - `tokens=null` 表现为柱状断口/留空，绝对不画成高度为 0 的柱子。
   - **成本折线图**：独立切换视图，避免双 Y 轴误导用户。
   - **深浅色自适应**：坐标轴使用 `stroke-gray-200 dark:stroke-dark-700`，刻度字使用 `fill-gray-500 dark:fill-dark-400`。
   - **可访问性（A11y）**：提供“图形 / 数据表格”一键切换按钮，保证键盘与屏幕阅读器友好访问。
4. **排行分解图（UsageBreakdown.vue）**：
   - 横向条形图展示 Top10 排名；
   - 末尾若有“其他”（`other`），以浅色条展示，支持展开查看汇总，但不可点击生成非法 filter ID；
   - 点击具体排行项（如某个模型、Agent、目的），自动在筛选栏追加对应 Chip 触发下钻。

### 4. 运行明细表与组件复用改造

1. **平台与项目分流展示**：
   - 平台全量模式下（未选单个项目），明细区展示友好引导卡片：“平台视图下请在上方筛选具体项目，以查看该项目的可访问运行明细”；
   - 选定单一项目后，立即发起 `GET /api/projects/{projectId}/usage/runs`。
2. **分页与空页 Cursor 状态机**：
   - 列表按 `(project_id, run_id)` 去重拼接；
   - **空页带 Cursor 处理**：当接口由于 ACL 过滤返回 `items: []` 但 `next_cursor` 存在时，按钮文案变为“继续扫描下一批”，并展示提示条“当前批次无可见运行，可继续向下穿透扫描”，彻底消除用户“点击无反应/卡死”的假象；
   - 筛选或时区变化时，**无条件重置分页**：清空列表、cursor 归 null、abort 正在进行的翻页请求。
3. **`RunUsage.vue` 与 `BaseDrawer.vue` 改造方案（消灭双 Header 冲突）**：
   - **根因消除**：`RunUsage.vue` 原本自带有 `<header>`（带标题、Badge、关闭按钮 X），`BaseDrawer.vue` 也自带有 `<header>`。
   - **改造方案**：
     - 在 `RunUsage.vue` 增加 `headless?: boolean` prop（默认 `false`）；
     - 当 `headless: true` 时，隐藏自身的 `<header>` 和外层 `border-l`，只保留主体内容和滚动区；
     - 在看板中使用 `<BaseDrawer show="..." title="完整运行用量" flush="true" width="wide">` 承载 `RunUsage`；
     - 彻底消除两层 Header、双关闭按钮和外层 padding 冲突，滚动由单层接管。
   - 抽屉挂载时精确传入 `projectId`、`threadId`、`runId`，关闭抽屉立即销毁组件并 abort 进行中的请求。

### 5. 前端模块与职责落点

| 路径（相对 `apps/platform-web/`） | 职责与变更类型 | 核心规约 |
|---|---|---|
| `src/types/management.ts` | 修改现有文件 | 补充 `platform.usage.read` 与 `project.usage.read` 权限码 |
| `src/modules/usage/types.ts` | 拟新增 | 严格对应 `fixtures` 的 Zod schemas 与 TS 类型 |
| `src/services/usage/usage.service.ts` | 拟新增 | 封装 3 个 GET 接口，处理原生重复键序列化、参数白名单与 AbortSignal |
| `src/modules/usage/composables/useUsageDashboard.ts` | 拟新增 | 报表数据拉取、双 scope 管理、刷新/重置、请求 epoch 防竞态 |
| `src/modules/usage/composables/useUsageRuns.ts` | 拟新增 | 运行明细分页管理、空页 cursor 穿透状态机、去重与重置 |
| `src/modules/usage/pages/UsageDashboardPage.vue` | 拟新增 | 看板主页面，编排筛选、指标卡、图表与明细表格 |
| `src/modules/usage/components/UsageFilterToolbar.vue` | 拟新增 | 筛选工具栏，处理小时/跨度联动防呆、平台禁用 Agent 守卫 |
| `src/modules/usage/components/UsageTrend.vue` | 拟新增 | 原生 SVG 堆叠柱/折线图，支持 partial 条纹、断点与数据表格切换 |
| `src/modules/usage/components/UsageBreakdown.vue` | 拟新增 | Top10 横向进度排行与钻取下钻 |
| `src/modules/chat/components/trajectory/RunUsage.vue` | 修改现有组件 | 增加 `headless` prop 支持无头模式，消除 Drawer 嵌套冲突 |
| `src/router/routes.ts` | 修改现有文件 | 注册平台 `/workspace/usage` 与项目 `/workspace/projects/:projectId/usage` 路由及导航项 |

### 6. 状态与竞态防御机制

| 触发场景 | 防御动作 |
|---|---|
| 初次加载 | 渲染骨架屏（Skeleton），避免首屏跳动，数字不展示为 0 |
| 手动刷新 | 保留当前已有数据，按钮显示 Loading 动效，标明“正在刷新” |
| 筛选条件变更 | 自增 `epoch`，调用 `abortController.abort()` 中止旧请求，重置分页游标与明细列表 |
| 顶栏切换项目 | 平台路由（`/workspace/usage`）严格保持平台 scope，禁止受顶栏污染自动切为单项目 |
| 账号注销/撤权 | 立即清空所有看板数据、关闭打开的抽屉，显示权限不足占位态，不触发全局登出 |
| 上游服务 502/503/504 | 保持筛选，局部呈现“服务暂不可用”重试卡；503 `usage_query_capacity_exhausted`沿临时故障处理，保留条件手动重试 |

---

## 任务拆分 (W01–W04)

| 阶段 | 任务目标 | 核心产出与验证条件 | 预计工时 | 状态 |
|---|---|---|---|---|
| **W01** | 权限、契约、Service 与路由导航 | 扩展 `management.ts` 权限类型；实现 `usage.service.ts`（参数白名单、Axios 重复键、AbortSignal）；配置双路由与导航图标；通过 Zod 校验所有 frozen fixtures。 | 1 人天 | [x] |
| **W02** | 页面编排、筛选联动、指标卡与防竞态 | 实现 `UsageDashboardPage.vue`、`useUsageDashboard`；实现筛选防呆（小时≤7天联动、多项目禁用 Agent、单项目隐藏 project 分组）；实现 4 组金融级精度指标卡；防竞态 epoch 验证。 | 1 人天 | [x] |
| **W03** | 原生 SVG 趋势图、排行分解与无障碍 | 实现 `UsageTrend.vue`（堆叠柱、折线、partial 条纹 pattern、null 缺口断口、深浅主题绑定、表格模式切换）；实现 `UsageBreakdown.vue`（Top10 排行与 Chip 钻取）。 | 1–1.5 人天 | [x] |
| **W04** | 运行分页、抽屉集成与多视口联合验收 | 实现 `useUsageRuns`（空页 cursor 提示、去重）；改造 `RunUsage.vue`（`headless` prop 解决双 Header 冲突）并嵌入 `BaseDrawer`；覆盖 1440/1024/390 响应式；执行 Vitest、typecheck、lint 与 build；Playwright 真实模型 E2E 闭环验收通过。 | 1 人天 | [x] |

---

## 验证要求

- [x] **静态代码质量门禁**：
   - `pnpm lint` 0 报错；
   - `pnpm typecheck`（`vue-tsc --noEmit`）0 错误；
   - `pnpm test:run` Vitest 单元测试 846 项全部通过；
   - `pnpm build` 生产构建成功。
- [x] **契约与数据格式验证**：
   - 验证 `fixtures/` 目录下全部场景（complete, partial, empty, not_recorded, disabled, unavailable, unpriced, no-projects）正常通过 Zod 校验；
   - 验证金额严格按 12 位 USD 字符串展示，极小值显示 `< $0.0001`；
   - 验证 Token 总和不重复叠加缓存读/写与推理。
- [x] **边界与异常交互验证**：
   - 验证切换粒度为“小时”时，时间跨度被强约束在 7 天内；
   - 验证平台多项目状态下 Agent 下拉被禁用并提示；
   - 验证 Runs 分页在遇到空页但有 cursor 时展示清晰提示，点击可继续扫描；
   - 验证抽屉打开时无双层 Header、无双关闭按钮、无双滚动条。
- [x] **多视口与端到端自动化验收**：
   - 验证 1440×900（双栏大屏）、1024×768（自适应平板）、390×844（单列移动端）留痕通过；
   - Playwright + Chromium 真实大模型（DeepSeek-V4-Flash）自动化端到端测试 1 passed (20.5s)，全套 4 张截图已落库。

---

## 状态记录

- 2026-10-11：W01–W04 前端开发全链路闭环完成。代码质量门禁全绿（vue-tsc 0 错、ESLint 0 错、Vitest 846 项通过、打包成功）；Playwright 真实大模型端到端自动化测试通过，4 张实景截图留痕落库；本地服务（Web 28226, API 29493, Runtime 24138）已保持稳定运行。
- 2026-10-11：【专项优化】彻底根除顶栏切换项目时的视觉缩放与布局抖动（CLS）：1) `WorkspaceLayout.vue` 启用 `[scrollbar-gutter:stable]` 锁定垂直滚动条槽位，并将 `transition-all` 规范收敛为精确的 `transition-[margin-left]`；2) `WorkspaceProjectSwitcher.vue` 补齐 `/usage` 路由正则匹配；3) `useUsageDashboard` 采用 SWR 平滑保留数据快照策略，避免切换项目瞬间 DOM 塌陷。类型检查、构建及 Playwright 自动化全链路回归测试（36.7s）100% 通过。
- 当前状态：前端实施已完成 (`done`)；等待用户人工验收。2026-10-12后端容量B01已解除，见05的两轮公开容量证据；前端以上阶段记录保留，本轮B01工作未复验这些测试，全栈Final/人工验收及生产发布另行接续。

# Platform Web V2 架构与 UI 基座方案

更新时间：2026-04-01

## 1. 为什么新建 `platform-web-v2`

当前仓库已有 `apps/platform-web`，但本轮不继续在原目录上叠加 UI 重构，原因很实际：

- 原应用已经承担真实联调职责
- 页面结构和交互逻辑已较多，继续原地重构风险高
- UI 改造和业务维护混在一起，容易互相污染
- 需要一个独立前端目录先把新版工作台壳子和母版打稳

所以本轮采用：

**新建 `apps/platform-web-v2`，然后逐步迁移旧 `platform-web` 的能力。**

## 2. 设计目标

`platform-web-v2` 的目标不是“把旧页面原样复制一遍”，而是：

- 重建更成熟的平台工作台 UI 基座
- 提供统一的中后台页面母版
- 保持与 `platform-api` 的契约兼容
- 为后续所有页面迁移提供一致的视觉和结构

## 3. 技术路线

零成本前提下，当前建议路线固定为：

- `Next.js App Router`
- `React`
- `Tailwind CSS`
- `Radix UI`
- `shadcn/ui`

参考来源：

- 主基座参考：`shadcn/ui + Blocks`
- 中后台页面模式参考：`Refine + shadcn/ui`

明确不做：

- 不迁入 `Ant Design Pro`
- 不切换到 `HeroUI`
- 不使用另一整套 UI 体系替代 `Tailwind + Radix`

## 4. UI 结构方向

新版工作台统一采用：

- 左侧主导航
- 顶部上下文条
- 主内容区

不再沿用旧版 `platform-web` 那种顶部横向堆导航的主结构。

原因：

- 左侧导航更适合中后台长期扩展
- 顶部上下文条更适合承载当前项目、用户、全局动作
- 主内容区更适合统一列表页、详情页、工作区页面结构

## 5. 新版层级结构

建议把 `platform-web-v2` 拆成四层：

### 5.1 App Shell 层

负责：

- 左侧导航
- 顶部上下文条
- 页面容器宽度和滚动行为
- 全局快捷入口

核心组件建议：

- `WorkspaceShellV2`
- `SidebarNav`
- `TopContextBar`

### 5.2 Page Template 层

负责：

- 页面标题
- 操作区
- 筛选区
- 内容区
- 状态反馈区

核心组件建议：

- `PlatformPage`
- `PageHeader`
- `FilterToolbar`
- `DataPanel`
- `FormSection`
- `DetailPanel`
- `StateBanner`

### 5.3 Domain Page 层

负责：

- `Projects`
- `Users`
- `Assistants`
- `Graphs`
- `Audit`
- `Chat`
- `Threads`
- `SQL Agent`
- `Testcase`

### 5.4 Integration 层

负责：

- 与 `platform-api` 的接口调用
- query-state
- thread / stream / auth 等 provider

这个层在第一阶段尽量复用旧逻辑，不先发明新协议。

## 6. 视觉方向

视觉方向定为：

**企业工作台 / Enterprise Workspace**

要求：

- 比当前 `platform-web` 更成熟、更稳定
- 信息密度中高
- 清晰、克制、专业
- 浅色优先，深色可后补
- 不走 AI 演示风
- 更像成熟企业内部系统

建议基调：

- 稍冷的浅灰蓝背景
- 浅天蓝强调色
- 中性色为主，强调色点到为止
- 更清晰的卡片边界、分组层级、状态色
- 标题、操作、表格、详情块遵循统一节奏

## 6.1 主题方案

`platform-web-v2` 已确定采用主题化视觉方案。

当前主题决策如下：

- 默认主题：`Refine HR 系`
- 备选主题：`Workspace Neutral`
- 备选主题：`Soft Admin`

### 默认主题：Refine HR 系

该主题已作为当前首选方向确定，特点：

- 企业内部系统气质
- 稍冷背景
- 浅天蓝图标与强调色
- 克制，不带强 AI 味
- 适合长期使用的管理后台

### 主题切换能力

后续 `platform-web-v2` 需要支持：

- 一键切换主题
- 主题写入浏览器本地存储
- 页面刷新后保留用户选择
- 不改变布局与业务结构，只切换视觉 token

这不是附属玩具功能，而是新版工作台的正式能力之一。

## 6.2 UI 组件库策略

`platform-web-v2` 不是没有 UI 组件库，而是采用：

- `shadcn/ui` 作为基础组件库
- `Radix UI` 作为交互 primitives
- `shadcn/ui Blocks` 作为布局与页面块参考
- 内部 `platform` 组件层作为平台级复用组件库

也就是说，真正的组件体系是：

### 基础组件层

负责：

- Button
- Input
- Dialog
- Sheet
- Tooltip
- Avatar
- Skeleton
- Table 基础能力

### 平台组件层

负责：

- `WorkspaceShellV2`
- `SidebarNav`
- `TopContextBar`
- `PlatformPage`
- `PageHeader`
- `FilterToolbar`
- `DataPanel`
- `FormSection`
- `DetailPanel`
- `StateBanner`

后续开发统一原则：

- 禁止再引入第二套重型 UI 组件系统
- 优先补全 `shadcn/ui`
- 再在此之上沉淀自己的平台组件库

## 7. 页面迁移策略

迁移遵循“先基础、后业务；先标准 CRUD、后复杂工作区”的顺序。

### 第一批

- 登录页
- 项目页
- 用户页
- 助手页

### 第二批

- Graphs
- Audit
- Me
- Security
- Project detail
- Members

### 第三批

- Chat
- Threads
- SQL Agent
- Testcase

## 8. 当前结论

`platform-web-v2` 的建设原则已经确定：

- 不动旧 `platform-web`
- 新建独立前端目录承接迁移
- 采用 `shadcn/ui + Blocks` 做 UI 基座
- 采用左侧导航 + 顶部上下文条 + 主内容区布局
- 采用母版组件优先策略，不直接逐页乱改
- 默认主题使用 `Refine HR 系`
- 保留 `Workspace Neutral` / `Soft Admin` 作为可切换主题
- 主题切换是正式能力，不是演示功能

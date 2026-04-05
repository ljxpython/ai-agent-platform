# Platform Web 视觉升级规划

更新时间：2026-04-01

## 1. 目标

在不改变现有业务功能和接口边界的前提下，完成 `apps/platform-web` 的视觉升级和页面母版升级。

本轮重点不是“发明新功能”，而是：

- 让平台工作台从“能用的原型”升级为“成熟中后台”
- 建立统一的页面骨架和视觉语言
- 降低后续新页面继续长歪的概率

## 2. 范围

### 2.1 本轮包含

- 登录页视觉重做
- 工作区整体布局升级
- 页面头部、工具栏、筛选区、详情区、表格区统一
- 管理类页面的列表 / 表单 / 详情样式升级
- 空态、错误态、成功反馈、危险操作弹窗统一

### 2.2 本轮不包含

- `platform-api` 接口协议变更
- query-state 模型重构
- 权限模型重构
- chat / runtime 的业务逻辑重写
- 数据结构和路由结构大改

## 3. 视觉方向

建议方向：**AI 平台工作台 / Control Tower**

风格关键词：

- 清晰
- 稳定
- 专业
- 信息密度适中
- 有现代感，但不过度花哨

建议不要走这几种坑：

- 纯 demo 风 dashboard
- 花里胡哨的大渐变 SaaS 官网风
- 传统 ERP 式老旧蓝灰后台

建议的视觉基调：

- 浅色为主，深色为辅助
- 中性灰底 + 克制蓝青色强调
- 更强的层级边界、卡片阴影和状态色体系
- 统一圆角、间距、表格密度和标题层级

## 4. 组件与页面母版建设

先不要一页一页瞎改，先把基座搭起来。

建议新增或重构的平台组件：

- `WorkspaceShell` 新版
  - 左侧主导航
  - 顶部上下文条
  - 页面内容容器
- `PlatformPage`
  - 页面统一外边距、宽度和响应式规则
- `PageHeader`
  - 标题、副标题、主操作、次操作、breadcrumb
- `FilterToolbar`
  - 搜索、筛选、快速操作、批量动作
- `StatCard`
  - 数量、状态、提示信息
- `DataPanel`
  - 表格 / 列表区域壳子
- `FormSection`
  - 表单分组、说明文案、危险操作区
- `DetailPanel`
  - 基础信息 / metadata / config 的分栏展示
- `EmptyState` / `ErrorState` / `SuccessNotice`
  - 统一反馈组件

## 5. 页面优先级

### P0：先打样，最能体现观感变化

- `/auth/login`
- `/workspace/projects`
- `/workspace/assistants`
- `/workspace/users`

原因：

- 这几页最像标准中后台页面
- 改完最容易给 CEO 看出变化
- 也最适合沉淀列表页、表单页、详情页母版

### P1：批量套用管理页母版

- `/workspace/graphs`
- `/workspace/audit`
- `/workspace/me`
- `/workspace/security`
- `/workspace/projects/[projectId]`
- `/workspace/projects/[projectId]/members`

### P2：复杂工作区二次深化

- `/workspace/chat`
- `/workspace/threads`
- `/workspace/sql-agent`
- `/workspace/testcase/*`

这些页不能只靠 CRUD 模板改，需要保留业务特性后单独优化。

## 6. 分阶段执行

### Phase 1：设计令牌和工作台骨架

产出：

- 全局色板、阴影、圆角、间距、字体、状态色
- 新版 `WorkspaceShell`
- 新版登录页
- 统一 page header / card / table / form section / notice 组件

验收标准：

- 不改业务逻辑就能明显提升整体观感
- 至少 3 个页面能复用同一套基座组件

### Phase 2：列表页与表单页模板化

产出：

- `Projects`
- `Assistants`
- `Users`
- `Graphs`

这些页面完成：

- 标题区统一
- 搜索筛选统一
- 表格壳子统一
- 行操作按钮统一
- 分页和状态反馈统一

验收标准：

- 管理页风格统一，不再一页一个脾气

### Phase 3：详情页与复合页升级

产出：

- project detail
- assistant detail
- me / security
- members

验收标准：

- 详情信息、配置块、危险操作区有明确层级

### Phase 4：复杂工作区升级

产出：

- chat / threads / sql-agent / testcase

重点：

- 保持原有功能不变
- 引入更成熟的工作台信息结构
- 强化上下文区、操作区、主内容区、侧栏的关系

## 7. 工程策略

本轮工程策略很明确：

- 保留 `Next.js App Router`
- 保留 `management-api` 封装
- 保留 `WorkspaceContext` / `Thread` / `Stream` provider
- 不在第一阶段引入整套新框架控制路由和数据流

具体做法：

- 参考 `Refine + shadcn/ui` 的页面模式
- 参考 `shadcn blocks` 的布局与视觉素材
- 在现有项目内建设内部平台 UI 层

## 8. 风险与控制

### 风险 1：只改皮肤，不改页面骨架

结果：

- 看着比现在好一点
- 但整体仍然像 patchwork

控制方式：

- 先做母版组件，再改页面

### 风险 2：一次性重构太多页面

结果：

- 改到一半风格混乱
- 回归成本暴涨

控制方式：

- 按 P0 -> P1 -> P2 推进
- 每个阶段都能独立交付

### 风险 3：引入第二套 UI 体系

结果：

- antd 一套，Tailwind/Radix 一套
- 代码库很快变成大杂烩

控制方式：

- 本轮不引入 Ant Design Pro 作为主实现

## 9. 初步任务拆分

1. 抽象 `WorkspaceShell` 2.0
2. 抽象 `PageHeader` / `FilterToolbar` / `DataPanel` / `FormSection`
3. 重做登录页
4. 重做 `Projects`
5. 重做 `Assistants`
6. 重做 `Users`
7. 批量替换其余 CRUD 管理页
8. 再处理 `Chat / Threads / Testcase / SQL Agent`

## 10. 推荐决策

当前建议直接定下来：

- 主参考框架：`Refine + shadcn/ui`
- 直接落地素材：`shadcn/ui Blocks`
- 当前工程实现：继续保留 `platform-web` 现有架构，渐进改造

这个方案的好处很现实：

- 看起来会比现在高级不少
- 不会把当前工程狠狠干碎
- 后续新增页面也有统一模板可套

# Platform Web 前端中台框架调研

更新时间：2026-04-01

## 1. 背景

`apps/platform-web` 当前已经不是通用 chat demo，而是平台工作台前端，承担：

- 登录与工作区导航
- 项目、用户、成员、审计等管理页面
- assistant / graph / runtime 管理页
- chat / thread / testcase / sql-agent 等业务工作区

这轮目标不是改业务功能，而是：

- 保持现有接口、路由、状态模型基本不变
- 参考成熟中后台前端方案，提升页面观感、信息层级和一致性
- 在当前技术栈上渐进改造，不做高风险重构

## 2. 当前项目现状

### 2.1 技术栈

结合当前代码，`platform-web` 真实基线是：

- `Next.js 15` App Router
- `React 19`
- `Tailwind CSS 4`
- `Radix UI`
- `class-variance-authority`
- `nuqs` query state

与 `runtime-web` 的依赖基线几乎一致，说明 `platform-web` 本质上是在现有 React / Tailwind / Radix 体系上继续长出来的平台前端，而不是独立的另一套管理后台。

### 2.2 当前页面问题

从真实页面和代码模式看，当前“丑”的核心不在于框架太弱，而在于平台层缺少成熟中后台设计基座：

- 登录页和管理页整体像“能用的原型”，视觉重心弱
- 页面标题、筛选区、操作区、表格区、详情区没有统一版式
- 大量页面重复使用 `rounded-lg border bg-card/70 p-4` 这类朴素容器
- 按钮、表单、列表、分页虽可用，但缺少成熟中后台的层级感和节奏
- 顶部导航信息密度高，但没有形成稳定的工作台信息架构
- CRUD 页面很多，但缺少统一的列表页 / 详情页 / 表单页脚手架

换句话说，问题主要是“平台设计系统和页面母版缺失”，不是“React 不够成熟”。

## 3. 选型评估原则

这轮选型优先看四件事：

1. 能否兼容 `Next.js App Router + React 19`
2. 能否兼容当前 `Tailwind + Radix` 体系，避免重做全部 UI
3. 能否服务大量管理页、列表页、表单页
4. 能否渐进接入，而不是强迫整站推翻重写

## 4. 候选方案

### 4.1 Ant Design Pro / ProComponents

官方定位和能力：

- Ant Design Pro 官方把自己定义为企业应用的开箱即用 UI 方案
- ProComponents 官方主打企业级应用组件，包含 table、form、layout 等一整套中后台能力

适合点：

- 视觉成熟度高，中后台味道很足
- `ProLayout`、`ProTable`、`ProForm` 这些东西确实省时间
- 对传统管理后台 CRUD 场景很强

不适合当前项目的地方：

- 它本质是 `antd` 生态，不是 `Tailwind + Radix` 生态
- 会把当前项目从 CSS variables + Tailwind tokens 拉到另一套组件体系
- 大量页面需要重写成 Ant Design 组件写法
- chat / thread / testcase / sql-agent 这类“平台业务页”并不天然适合 Pro 的套路
- 长期结果很容易变成一个项目里并存两套设计语言

结论：

- 适合作为“成熟中后台交互样式参考”
- 不适合作为 `platform-web` 当前阶段的直接迁移目标

### 4.2 Refine + shadcn/ui

官方定位和能力：

- Refine 官方提供 `Next.js` 路由集成
- Refine 官方已提供 `shadcn/ui` 集成，强调通过源码复制保留完整定制权
- Refine 的 `shadcn/ui` 集成包含 layout、list/create/edit/show、data table、auth 相关组件

适合点：

- 与当前 `Next.js + Tailwind + Radix/shadcn 风格` 的技术路线最接近
- 更像“中后台开发框架 + 业务脚手架”，不是单纯 UI 库
- 对 CRUD 管理页、列表页、表单页、详情页非常友好
- 可以在现有工程里逐步吸收其 page pattern、resource pattern 和 layout pattern

代价与风险：

- Refine 偏 `resource + dataProvider + authProvider` 模型
- 你们现在很多页面是自定义 API wrapper + 自定义 query-state，不是标准资源后台
- chat / runtime / testcase 这类复合工作区并不是典型 Refine CRUD 页面
- 如果整站硬上 Refine，会引入一层新的抽象成本

结论：

- 这是当前项目最值得参考、也最容易兼容的成熟中后台方案
- 但更合理的落地方式是“参考并局部吸收”，不是一次性整站重构成 Refine

### 4.3 shadcn/ui Blocks + 内部平台设计系统

官方定位和能力：

- shadcn 官方已经提供 blocks 体系，包含 login、sidebar、dashboard 等块级页面资产
- blocks 是源码级引入，适合做页面骨架和视觉升级

适合点：

- 与当前 Tailwind / Radix 路线完全同源
- 迁移成本最低
- 最适合“功能不变，只把页面做漂亮一点”的目标
- 可以直接沉淀成你们自己的 `platform` 组件层

不足：

- 它不是完整中后台框架，更像高质量页面骨架和组件资产
- 数据层、权限层、资源管理模式仍然要自己维护

结论：

- 非常适合作为本轮视觉升级的直接落地素材库
- 单独拿来做框架还不够，需要结合你们自己的平台组件抽象

### 4.4 React-admin / Shadcn Admin Kit

优点：

- React-admin 在 B2B admin 领域非常成熟，`dataProvider` / `authProvider` / `Resource` 模型也很完整
- Marmelab 的 `shadcn-admin-kit` 让它可以走 `shadcn` 视觉路线

问题：

- React-admin 官方在 Next.js 场景里仍然强调它本质是客户端 SPA
- 路由、资源模型、页面组织方式会明显改变当前 App Router 项目结构
- 对你们这种“管理页 + chat 工作区 + 自定义平台壳子”混合型应用，不如 Refine 顺手

结论：

- 是成熟备选，但不是当前最优解

## 5. 最终建议

如果必须只选一个“主参考框架”，我建议选：

**`Refine + shadcn/ui`**

原因：

1. 它和当前 `Next.js + Tailwind + Radix` 技术栈最兼容
2. 它对中后台最常见的列表、表单、详情、布局问题都有成熟答案
3. 它比 Ant Design Pro 更容易渐进接入
4. 它不会强迫 `platform-web` 变成另一种技术体系

但真正的落地方式不要搞成“全量迁移 Refine”，那样反而容易把项目搞成半新半旧的四不像。

更合理的执行建议是：

- 视觉和布局层：直接参考 `shadcn/ui Blocks`
- 中后台页面模式：参考 `Refine + shadcn/ui`
- 工程实现层：继续保留当前 `Next.js App Router + providers + management-api wrapper`

一句话版本：

**主参考选 `Refine + shadcn/ui`，实际落地采用“shadcn blocks 做视觉、内部组件层做母版、保留现有业务架构”的渐进改造方案。**

## 6. 不建议直接选 Ant Design Pro 的原因

这个地方单独写清楚，免得后面有人拍脑袋：

- 它确实成熟，但成熟不等于适合当前工程
- 你们现在已经有一套 Tailwind + Radix + chat 模板 + 自定义 provider 的现实代码
- 换 Ant Design Pro，本质是重新押注另一套设计系统和组件生态
- 最终不仅是“美化页面”，而是“重写页面”

所以：

- 想拿它当参考，没问题
- 想拿它当迁移目标，当前阶段不划算

## 7. 推荐落地策略

第一阶段只做“平台 UI 基座”：

- 统一工作台壳子
- 统一页面头部
- 统一筛选工具栏
- 统一数据表格容器
- 统一表单区块
- 统一空态 / 错态 / 成功提示

第二阶段再批量替换页面：

- 登录页
- `Projects`
- `Assistants`
- `Users`
- `Graphs`
- `Audit`

第三阶段处理复杂工作区：

- `Chat`
- `Threads`
- `SQL Agent`
- `Testcase`

## 8. 参考资料

- Refine `shadcn/ui` 集成：
  - https://refine.dev/core/docs/ui-integrations/shadcn/introduction/
- Refine `Next.js` 集成：
  - https://refine.dev/docs/routing/integrations/next-js/
- shadcn 官方 Blocks：
  - https://ui.shadcn.com/blocks
- shadcn Blocks 文档：
  - https://ui.shadcn.com/docs/_blocks
- Ant Design Pro 官方仓库：
  - https://github.com/ant-design/ant-design-pro
- ProComponents 官方仓库：
  - https://github.com/ant-design/pro-components
- React-admin 官方站点：
  - https://marmelab.com/react-admin/
- React-admin Next.js 集成：
  - https://marmelab.com/react-admin/NextJs.html

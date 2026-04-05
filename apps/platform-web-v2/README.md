# Platform Web V2

`apps/platform-web-v2` 是当前仓库中为新一代平台工作台 UI 单独开辟的隔离前端目录。

它的存在目的很明确：

- 不直接在 `apps/platform-web` 上继续堆改动
- 在零成本前提下重建更成熟的中后台 UI 基座
- 以渐进迁移方式承接旧工作台能力
- 在迁移完成前，避免对当前线上/联调中的 `platform-web` 产生额外隐患

## 当前定位

`platform-web-v2` 不是全新产品，也不是推翻重做的平台。

它是：

- 面向 `platform-web` 的 UI 重构承接层
- 新版工作台壳子和页面母版实验场
- 后续管理页、工作区页面逐步迁移的目标前端

## 基本原则

1. 保持零成本开发
2. 不引入新的重型商业 UI 框架
3. 保持当前技术路线：
   - `Next.js App Router`
   - `React`
   - `Tailwind CSS`
   - `Radix UI`
   - `shadcn/ui`
4. 不让新 app 反向污染旧 `platform-web`
5. 先建设 UI 基座，再逐页迁移

## 运行环境

- 推荐使用 `Node 20 LTS`
- 当前验证通过版本：`20.17.0`
- 不建议使用 `Node 25.x` 作为本项目开发基线，`Next.js 15` 在该非 LTS 版本下开发态存在不稳定现象

启动前建议执行：

```bash
source "$HOME/.nvm/nvm.sh"
nvm use
pnpm install
pnpm dev
```

## 当前推荐 UI 路线

- UI 基座：`shadcn/ui + Blocks`
- 页面模式参考：`Refine + shadcn/ui`
- 架构策略：保留现有平台 API 契约与前端 provider 思路，按需迁移
- 默认主题：`Refine HR 系`
- 备选主题：`Workspace Neutral` / `Soft Admin`

## UI 组件库策略

`platform-web-v2` 不是没有 UI 组件库，而是明确不再引入一套新的重型组件体系。

当前采用的策略是：

- 基础 UI 组件库：`shadcn/ui`
- 低层交互能力：`Radix UI`
- 页面块与布局参考：`shadcn/ui Blocks`
- 平台层复用组件：在 `platform-web-v2` 内部继续建设 `platform` 组件层

也就是说，后续真正会形成两层：

1. 基础组件层
   - button
   - input
   - dialog
   - sheet
   - tooltip
   - avatar
   - skeleton
   - table 相关基础能力
2. 平台组件层
   - `WorkspaceShellV2`
   - `PageHeader`
   - `FilterToolbar`
   - `DataPanel`
   - `FormSection`
   - `DetailPanel`
   - `StateBanner`

这套方式的好处是：

- 零成本
- 和当前技术栈一致
- 不会引入第二套 UI 体系
- 能沉淀真正适合本项目的平台组件库

## 文档入口

1. `docs/architecture-plan.md`
2. `docs/migration-plan.md`
3. `docs/phase-1-ui-foundation.md`
4. `docs/project-structure-and-component-plan.md`
5. `docs/feature-migration-inventory.md`
6. `docs/migration-roadmap.md`
7. `docs/master-checklist.md`

## 样板参考

- UI 风格样板已放入 `apps/platform-web-v2/examples/style-lab`
- 这个目录用于保存 `platform-web-v2` 的静态视觉样板，不参与正式构建
- 后续页面迁移、布局调整和主题校准，优先参考这里

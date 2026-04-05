# Platform Web V2 Phase 1 UI Foundation

更新时间：2026-04-01

## 1. 第一阶段目标

第一阶段不追求页面数量，追求“基座成型”。

必须完成的事：

- 定义新版视觉基线
- 定义主题 token 与默认主题
- 落地新版工作台布局
- 落地页面母版组件
- 让首批页面有统一承载方式

## 2. 第一阶段范围

### 必做

- 登录页母版
- 左侧导航
- 顶部上下文条
- 主题切换能力
- 页面头部
- 列表容器
- 表单容器
- 统一状态反馈

### 暂不做

- 复杂图表系统
- 复杂拖拽交互
- 页面级高度定制动画

## 3. 组件清单

建议在第一阶段优先定义这些组件：

- `WorkspaceShellV2`
- `SidebarNav`
- `SidebarSection`
- `TopContextBar`
- `TopContextProject`
- `TopContextActions`
- `PlatformPage`
- `PageHeader`
- `PageActions`
- `FilterToolbar`
- `DataPanel`
- `FormSection`
- `SectionDescription`
- `EmptyState`
- `ErrorState`
- `SuccessBanner`

以及这些主题基础设施：

- `ThemeProvider`
- `ThemeToggle`
- 主题 token 映射
- 主题持久化存储

## 4. 页面打样顺序

### 样板页面 1：登录页

目标：

- 一眼看起来不再像 demo
- 作为新版视觉语言的起点

### 样板页面 2：项目页

目标：

- 跑通“页面头部 + 筛选工具栏 + 数据表格 + 行操作”的完整母版

### 样板页面 3：用户页

目标：

- 验证列表与表单混合场景

### 样板页面 4：助手页

目标：

- 验证复杂配置表单和详情区块承载能力

## 5. 第一阶段验收标准

完成后至少应满足：

- 工作台布局一眼能看出是成熟中后台
- 侧边导航、顶部条、主内容区层级明确
- 至少 3 个页面共用同一套页面母版
- 不改业务接口也能显著提升观感

## 6. 当前讨论结论

本项目第一阶段已经固定：

- 零成本开发
- 不动 `apps/platform-web`
- 在 `apps/platform-web-v2` 中建设新版前端
- 使用左侧主导航 + 顶部上下文条 + 主内容区
- 使用 `shadcn/ui + Blocks` 作为 UI 基座
- 默认主题使用 `Refine HR 系`
- 保留 `Workspace Neutral` / `Soft Admin` 作为可切换主题
- 主题切换是正式能力，不是演示功能

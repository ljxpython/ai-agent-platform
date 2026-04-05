# Platform Web V2 目录结构与组件清单

更新时间：2026-04-01

## 1. 目标

这份文档用于固定 `platform-web-v2` 的初始目录结构和第一批基础组件边界。

目的只有一个：

- 让后续开发从一开始就按统一结构推进
- 避免边写边长歪
- 让 UI 基座、业务页面、主题系统、接口层各归各位

## 2. 推荐目录结构

建议 `platform-web-v2` 初始按下面结构组织：

```text
apps/platform-web-v2/
├── README.md
├── docs/
├── public/
├── src/
│   ├── app/
│   │   ├── auth/
│   │   ├── workspace/
│   │   ├── layout.tsx
│   │   └── page.tsx
│   ├── components/
│   │   ├── ui/
│   │   ├── platform/
│   │   └── icons/
│   ├── providers/
│   ├── lib/
│   │   ├── management-api/
│   │   ├── auth/
│   │   ├── config/
│   │   └── utils/
│   ├── hooks/
│   ├── theme/
│   └── styles/
└── tests/
```

## 3. 各目录职责

### `src/app`

负责：

- Next.js App Router 路由入口
- 页面 layout
- 页面级组合逻辑

约束：

- `app` 里不堆通用组件
- 页面只负责组装，不负责沉淀可复用 UI

### `src/components/ui`

负责：

- 基于 `shadcn/ui` 的基础组件
- button / input / dialog / sheet / tooltip / avatar 等

约束：

- 这里是基础层，不写业务语义
- 优先保持和 `shadcn/ui` 习惯一致

### `src/components/platform`

负责：

- 平台工作台语义组件
- 布局壳子
- 页面母版
- 平台级反馈与容器组件

约束：

- 平台语义只放这里
- 这是 `platform-web-v2` 真正的“平台组件库”

### `src/components/icons`

负责：

- 项目内统一使用的图标封装
- Logo / 品牌图形 / 少量业务图标映射

### `src/providers`

负责：

- auth
- theme
- workspace
- thread / stream 等跨页面状态

约束：

- provider 只管理跨页面共享状态
- 页面内部局部状态不要乱塞到 provider

### `src/lib`

负责：

- API client
- auth storage
- 配置
- 数据转换
- 非 React 的纯函数逻辑

### `src/theme`

负责：

- 主题 token
- 主题映射
- 主题切换逻辑
- 主题持久化配置

### `src/styles`

负责：

- 全局样式
- reset / base / typography
- theme token 的 CSS variables 映射

## 4. 第一批基础组件清单

第一批必须落地的组件如下。

## 4.1 App Shell 类

### `WorkspaceShellV2`

职责：

- 承载整个工作台的外层结构
- 组合左侧导航、顶部上下文条和主内容区

边界：

- 不负责业务数据获取
- 只负责壳子布局和公共入口位置

### `SidebarNav`

职责：

- 左侧主导航
- 一级分组
- 当前页面高亮

### `SidebarSection`

职责：

- 导航分组标题与分组内容容器

### `TopContextBar`

职责：

- 顶部上下文条
- 当前项目、角色、环境、全局动作入口

### `TopContextProject`

职责：

- 展示当前项目摘要
- 为后续项目切换预留承载位

### `TopContextActions`

职责：

- 放顶部全局按钮
- 例如创建、管理、用户入口、主题切换等

## 4.2 Page Template 类

### `PlatformPage`

职责：

- 统一页面内容宽度、边距和纵向节奏

### `PageHeader`

职责：

- 页面标题
- 副标题
- 右侧主操作和次操作

### `PageActions`

职责：

- 页头操作按钮容器

### `FilterToolbar`

职责：

- 搜索框
- 筛选入口
- 刷新、导出、批量动作等

### `DataPanel`

职责：

- 包裹表格、列表、统计面板
- 统一容器边框、背景、标题区

### `FormSection`

职责：

- 表单分区
- 说明文案
- 分组操作区

### `DetailPanel`

职责：

- 承载详情页的基础信息、metadata、config 等分组内容

### `StateBanner`

职责：

- 顶部提示
- 成功、错误、warning、notice

### `EmptyState`

职责：

- 空列表或空页面反馈

### `ErrorState`

职责：

- 错误页、错误块

### `SuccessBanner`

职责：

- 成功反馈条

## 4.3 Theme 类

### `ThemeProvider`

职责：

- 提供当前主题上下文
- 初始化默认主题
- 读取本地持久化配置

### `ThemeToggle`

职责：

- 一键切换主题
- 触发主题持久化

## 5. 第一批页面与组件对应关系

### 登录页

优先依赖：

- `PlatformPage`
- 主题 token
- 基础表单组件

### Projects

优先依赖：

- `WorkspaceShellV2`
- `PageHeader`
- `FilterToolbar`
- `DataPanel`
- `StateBanner`

### Users

优先依赖：

- `PageHeader`
- `FilterToolbar`
- `DataPanel`
- `FormSection`

### Assistants

优先依赖：

- `PageHeader`
- `FilterToolbar`
- `DataPanel`
- `FormSection`
- `DetailPanel`

## 6. 当前明确不做的事

为了控制复杂度，当前先不做：

- 一开始就重建所有 provider
- 一开始就迁移 chat / threads / testcase
- 一开始就做大量动画系统
- 一开始就做深度图表平台

## 7. 当前结论

`platform-web-v2` 已经可以按这套结构推进：

- 底层基础组件：`shadcn/ui`
- 平台组件库：`src/components/platform`
- 主题系统：`src/theme`
- 页面入口：`src/app`
- 第一批页面：登录页、项目页、用户页、助手页

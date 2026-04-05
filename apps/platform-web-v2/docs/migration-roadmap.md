# Platform Web V2 迁移路线规划

更新时间：2026-04-01

## 1. 目标

这份文档用于把 `platform-web-v2` 的迁移过程拆成可执行阶段。

目标不是模糊地“未来全部迁过去”，而是：

- 每一阶段都有明确产出
- 每一阶段都能验证成果
- 每一阶段都服务最终目标：
  - 功能全迁移
  - 审美升级
  - UI 工程化

## 2. 阶段总览

### Phase 0：规划冻结

产出：

- 架构方案
- 主题方案
- 目录结构
- 组件清单
- 功能迁移台账

### Phase 1：工程骨架与 UI 基座

产出：

- `platform-web-v2` 工程初始化
- 主题系统
- `WorkspaceShellV2`
- `PageHeader`
- `FilterToolbar`
- `DataPanel`
- `FormSection`
- `StateBanner`

验收：

- 新版工作台壳子能独立展示
- 默认主题与可切换主题可用

### Phase 2：首批样板页迁移

产出：

- 登录页
- Projects
- Users
- Assistants

验收：

- 样板页能体现新版 UI 基座能力
- 主要查询和操作链路可跑通

### Phase 3：标准管理页扩展

产出：

- Projects detail / members / create
- Users detail / create
- Assistants detail / create
- Graphs
- Runtime models / tools
- Audit
- Me / Security

验收：

- 主要标准管理页迁移完成
- 平台组件库复用稳定

### Phase 4：复杂工作区承接

产出：

- Chat
- Threads
- SQL Agent
- Testcase generate / cases / documents

验收：

- 复杂工作区保持原有能力
- 视觉与工作台结构统一

### Phase 5：旧前端替换准备

产出：

- 路由覆盖核对
- 功能覆盖核对
- 验收清单

验收：

- `platform-web-v2` 已具备替代旧前端的条件

## 3. 每阶段必须遵守的原则

### 原则 1：先壳子后页面

没有母版组件，不允许大面积迁页。

### 原则 2：先标准 CRUD，后复杂工作区

不要一上来就冲 chat / testcase。

### 原则 3：视觉和工程化同步推进

不能只把页面画好看，不沉淀组件。

### 原则 4：迁移不等于复制垃圾

旧页面逻辑可以借，但旧页面结构和 UI 不应原样照抄。

## 4. 当前建议的实施顺序

### Step 1

初始化基础工程文件：

- `package.json`
- `tsconfig.json`
- `next.config.mjs`
- `postcss/tailwind` 配置
- `src/app/layout.tsx`
- `src/app/page.tsx`
- `src/app/globals.css`

### Step 2

实现主题系统：

- `ThemeProvider`
- `ThemeToggle`
- 主题 token
- 默认主题与本地持久化

### Step 3

实现工作台壳子：

- `WorkspaceShellV2`
- `SidebarNav`
- `TopContextBar`

### Step 4

实现页面母版：

- `PlatformPage`
- `PageHeader`
- `FilterToolbar`
- `DataPanel`
- `FormSection`
- `DetailPanel`
- `StateBanner`

### Step 5

迁移首批样板页：

- 登录页
- Projects
- Users
- Assistants

## 5. 当前建议的验收策略

### UI 基座阶段

- 以肉眼确认布局、风格和复用程度为主

### 页面迁移阶段

- 以构建通过、页面可打开、核心交互可跑为主

### 最终替换阶段

- 要求对照功能迁移台账逐项核验

## 6. 当前结论

`platform-web-v2` 后续应严格按以下顺序推进：

1. 工程骨架
2. 主题系统
3. 工作台壳子
4. 页面母版
5. 标准管理页
6. 复杂工作区

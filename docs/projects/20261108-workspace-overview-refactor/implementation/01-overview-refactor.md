# 工作区总览工业级重构实现记录

## 改动概览
- **日期：** 2026-11-08
- **服务：** `platform-web`
- **主要文件：**
  - `apps/platform-web/src/modules/overview/pages/OverviewPage.vue`
  - `apps/platform-web/src/modules/overview/pages/OverviewPage.spec.ts`

## 详细改动

### 1. 废除废话副标题与紧凑化 Header
- 移除 `PageHeader` 上的 `description="从当前项目继续工作。"` 属性并配置 `compact`；
- 将原本突兀插在项目卡片左上角的 `<router-link to="/workspace/control-plane">` 移除，并在 `PageHeader` 的 `#actions` 插槽中按 `can('platform.config.read')` 权限优雅收纳为带有 `shield` 图标的快捷按钮；
- 刷新按钮整合 `refresh` 图标并支持加载中旋转动画。

### 2. 4 联指标看板（MetricCards Grid）
- 在项目卡片上方引入 4 联卡片，网格自适应（`grid grid-cols-2 lg:grid-cols-4`）：
  - **项目 Agents**：展示项目已挂载智能体总数；
  - **活跃会话**：展示最近会话数；
  - **装配工具**：接入 `listRuntimeTools(projectId)` 异步查询工具总数，并在只读或异常时优雅显示 `--`；
  - **运行时引擎**：透出 `LangGraph` 运行时在线状态与健康探针。

### 3. 主辅双栏工作流与卡片增强
- **项目 Hero 卡片**：
  - 增强视觉层次，左侧展示项目图标、项目名称、绿色就绪脉冲微胶囊；
  - 右侧聚合【发起新对话】、【管理 Agents】、【浏览 Graphs】与【切换项目】操作组。
- **左栏（7fr）：最近对话流**：
  - 会话时间采用轻量纯函数 `formatRelativeTime`（刚刚、X分钟前、X小时前、X天前）；
  - 每条会话呈现主题标题、可恢复状态指示灯、右侧悬浮滑动箭头反馈。
- **右栏（5fr）：项目 Agents 矩阵**：
  - 卡片透出模型微胶囊 Tag（如 `deepseek-v4.1-flash`）与启用/停用状态；
  - 右侧提供【立即对话】快捷图标按钮，点击携带 `agentId` 直达对话工作台。

### 4. 自动化测试套件补齐
- 新建 `OverviewPage.spec.ts`，涵盖：
  - 4 联指标卡片与数值映射测试；
  - 废话副标题彻底清除断言；
  - Agent 模型 Tag 与快捷对话直达链接测试；
  - 最近对话相对时间格式化与可恢复链路测试；
  - 平台治理按钮基于权限的隐显控制。

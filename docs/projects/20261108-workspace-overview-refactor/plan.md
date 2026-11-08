# 工作区总览工业级重构与信息密度治理 - 整体方案

## 背景

当前 `OverviewPage.vue` 呈现出非常原始的 Demo 级草稿状态：
1. **废话文学占位**：顶部 Header 的“从当前项目继续工作。”纯属无意义模板字符，白白消耗 40px 纵向高度。
2. **布局割裂与反人类入口**：`进入平台治理 / 健康视图` 作为平台运维入口，被直接硬编码放置在项目卡片左上角正文上方，视觉流混乱突兀。
3. **严重的信息稀薄与留白灾难**：项目卡片占据大半屏视口，却仅展示项目名称与描述两个孤立字段，右侧大面积死白；平台已有现成 `MetricCard`，但没有任何运行、智能体、会话维度的指标透出。
4. **操作链路深、静态无活力**：底部的 Agents 和最近对话列表仅为基础文字展示，无模型信息、无快捷“立即对话”动作、无对话状态感知，无法支撑用户“0成本恢复上次会话”和“1秒发起核心任务”的高频诉求。

## 目标

1. **精简紧凑顶栏**：删除废话副标题，压缩 PageHeader，腾出首屏黄金视口。
2. **构建四联关键指标看板（KPI Metrics）**：复用现有的 `MetricCard`，聚合展示【项目 Agents】、【最近对话数】、【装配工具数】及【运行时状态】。
3. **主辅双栏工业级工作流布局**：
   - **左侧核心主栏（约 62%）**：快捷开工通道（支持一键选 Agent 发起对话）+ 增强型最近对话流（带相对时间、关联 Agent、状态指示与直达链接）。
   - **右侧辅助视口（约 38%）**：主力 Agent 矩阵卡片（展示 Model Tag、状态灯、悬浮直达“立即对话”快捷图标）+ 项目基础配置与治理快速收纳区。
4. **收敛平台治理与管理动作**：将平台治理入口优雅地收纳至顶部操作区或右侧辅助卡片，保持普通项目总览的整洁纯粹。

## 方案设计

### 整体架构与布局推演

```text
┌────────────────────────────────────────────────────────────────────────┐
│ PageHeader：工作区总览 [项目: test 🟢]          [刷新] [管理治理入口]    │
├────────────────────────────────────────────────────────────────────────┤
│ 4联指标看板（MetricCards Row）：                                       │
│ [ 智能体总数: 4 ]  [ 最近对话: 6 ]  [ 扩展工具: 8 ]  [ 运行时: 🟢 正常 ]  │
├──────────────────────────────────────────────────┬─────────────────────┤
│ 左侧核心工作流（主栏 ~62%）                      │ 右侧项目资产（副栏 ~38%）│
│                                                  │                     │
│ 1. 快捷开工横幅（Quick Launcher）                │ 1. 项目主力 Agents 矩阵│
│    - 快速选择 Agent 发起新对话                  │    - 头像/徽章 + 模型Tag│
│                                                  │    - 状态指示 + [立即对话]│
│ 2. 最近对话高密度流（Recent Threads）            │                     │
│    - 会话标题 + 相对时间（X小时前）              │ 2. 核心能力与工具概况 │
│    - 关联 Agent 徽章 + 悬浮视觉反馈              │    - Tools/Graphs 快捷跳转│
│    - 空态友好引导                                │ 3. 项目管理与治理收纳 │
└──────────────────────────────────────────────────┴─────────────────────┘
```

### 关键改动点

#### 1. PageHeader 与项目概览收纳
- **文件：** `apps/platform-web/src/modules/overview/pages/OverviewPage.vue`
- **改动：**
  - 去除 `description="从当前项目继续工作。"`；
  - 接入 `compact` 属性优化紧凑度；
  - 顶栏右侧 `#actions` 插槽整合刷新按钮以及平台治理视图快捷按钮（仅 `can('platform.config.read')` 时渲染），彻底移除卡片内部突兀的狗皮膏药按钮。

#### 2. 指标看板接入
- **文件：** `apps/platform-web/src/modules/overview/pages/OverviewPage.vue`
- **改动：**
  - 引入 `@/components/platform/MetricCard.vue`；
  - 基于已加载的 `agentTotal`、`threads.length`，以及追加查询的 `listRuntimeTools` 或 `listRuntimeGraphs` 数据组装 4 联指标卡片；
  - 增加对空状态、只读状态的自适应降级显示。

#### 3. 增强型最近对话流（Recent Threads）
- **文件：** `apps/platform-web/src/modules/overview/pages/OverviewPage.vue`
- **改动：**
  - 改进时间显示逻辑（引入相对时间格式化，如 `10 分钟前` / `2 小时前`）；
  - 卡片左侧增加对话主题图标，右侧显示“继续对话”箭头动效与更新时间；
  - 提升卡片 hover 反馈与阴影细腻度。

#### 4. 增强型项目 Agents 矩阵
- **文件：** `apps/platform-web/src/modules/overview/pages/OverviewPage.vue`
- **改动：**
  - 透出 Agent 绑定的模型信息（`agent.context.model_id`）与执行模式；
  - 状态标签采用平台标准 `StatusPill` 或微胶囊样式；
  - 每行 Agent 卡片右侧直接放置【发起对话】快捷图标按钮，点击直接带 `agentId` 跳转到对话工作台，减少二次跳转成本。

### 技术选型与复用规范
- 严格遵循 `apps/platform-web/docs/frontend-development-playbook.md`：
  - 复用现有组件：`PageHeader`、`SurfaceCard`、`MetricCard`、`BaseButton`、`BaseIcon`、`EmptyState`、`StateBanner`；
  - 样式使用统一的 Tailwind 平台标准原子类（`pw-page-shell`、`pw-stat-card`、`pw-card-subtle`、`pw-btn`）；
  - 杜绝重复造轮子，严禁随意引入第三方重量级依赖。

## 链路影响

### 受影响的调用链路
```text
OverviewPage.vue → agents.service.ts / session.service.ts / runtime.service.ts → Platform API / LangGraph API
```
- 无任何破坏性契约变更，完全基于现有的前端 Service 接口进行数据聚合与交互提升。

## 风险和依赖
- **权限边界：** 部分成员仅具备普通对话权限，可能无法读取 Agents 或 Tools。
  - **应对：** 严格基于 `canReadAgents`、`canReadChat` 做条件门禁渲染，无权限时显示占位或隐藏对应卡片，严禁出现控制台 403 抛错红条。

## 实施计划
1. **Phase 1: 顶栏精简与治理入口收纳**（干掉废话，重构 PageHeader 工具栏）
2. **Phase 2: 核心指标看板与状态装配**（组装 4 联 MetricCards 与异步数据补全）
3. **Phase 3: 主辅双栏布局重构与 Agents/Threads 增强**（重构下半部分工作流，加模型Tag、快捷对话与微交互）
4. **Phase 4: 全量构建、单测验证与页面视觉自检**（运行前端测试与类型检查，确保 0 报错）

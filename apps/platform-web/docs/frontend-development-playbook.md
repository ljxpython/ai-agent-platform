# Platform Web Frontend Development Playbook

- 文档类型：Current Leaf Standard
- Owning locus：`apps/platform-web`

本文定义页面 archetype、UI composition 和复用边界。正式控制面页面的
service/state/permission/audit 规则仍由 `control-plane-page-standard.md` 管理。

## 1. Source Of Truth

- 功能、路由和当前实现：`apps/platform-web`
- 视觉与交互基线：当前 `apps/platform-web` 壳层和共享组件
- 外部参考 `../research/open-swe` 只借鉴交互；正式构建不内嵌参考源码
- Chat 的 live messages/tools/interrupt/loading/error/lifecycle 由官方 SDK controller 维护；线程
  列表、历史快照和当前流订阅分离，页面不得再建立第二套运行状态机。

## 2. 先选页面 Archetype

新增页面先归类：

1. list
2. detail
3. create/edit
4. workspace
5. resource/help

优先复用同类当前页面和共享组件，不为单页建立新的布局体系。

## 3. 页面基本结构

### List

`PageHeader -> optional summary/filter -> DataTable -> PaginationBar`

搜索、空态、分页、排序和批量操作优先复用现有组件。

### Detail

`PageHeader -> summary -> grouped content -> related resources/activity`

先展示上下文和摘要，不把所有字段堆成一张长表单。

### Create/Edit

`PageHeader -> [Form (左) + Live Inspector / Preview (右)] -> actions`

- **表单布局**：字段较多（≥4 个）时严禁单列空洞平铺，优先采用双栏工作台布局：
  - **左侧 (约 1.25fr)**：按领域将输入项收敛入独立 `SurfaceCard`（如基础信息、推理参数、能力权限），下拉统一强制使用 `<BaseSelect>`，范围微调使用滑块双向联动，大额数字提供药丸预设。
  - **右侧 (约 0.75fr)**：所见即所得呈现当前实体的实时卡片预览、绑定底层资源特性及审计元数据，消灭空白留白。
- **字段契约**：字段、默认值和失败语义必须来自 leaf contract，不在页面里自行发明。
- **标杆代码样本**：
  - 创建/编辑页标杆：`src/modules/agents/pages/AgentEditorPage.vue`（双栏、BaseSelect、滑块、Token预设、实时卡片透视）
  - 列表页标杆：`src/modules/agents/pages/AgentsPage.vue`（防挤压搜索、卡片列表、首字母头像、权限按钮）

### Workspace

`context/navigation -> primary work area -> optional inspector`

工作区保持主任务突出，调试信息不能变成正式用户主界面。

## 4. Reuse Rules

- 使用现有 shell、tokens、forms、tables、feedback 和 navigation primitives
- 新抽象至少要解决两个真实调用点
- 业务语义留在 module 内，共享组件只承载稳定 UI 行为
- 不整页复制历史参考应用

## 5. Verification

按改动范围选择：

- 单项目：对应测试、lint、类型检查。
- 链路：加上 `platform-web -> platform-api -> runtime-service` 最短链。
- 治理：按 `docs/projects/20260910-platform-web-refactor/06-delivery-and-acceptance.md` 的关键链路、安全、性能和回退门禁验收。

页面完成必须同时满足响应式布局、错误态、空态、加载态和基本可访问性。

HTTP错误统一经 `src/utils/http-error.ts` 解析；SDK嵌套 `error` 对象和 `extra` 不得覆盖。只有合法请求ID追加到可见文案，Thread创建结果未知时先按平台UUID对账。完整边界见[错误出口标准](../../../docs/standards/error-envelope.md)。

## 6. Chat 实现边界

`ChatPage` 负责 URL/目标/列表；`ChatSession` 与 `useChatSession` 绑定固定身份/项目/Thread，官方 SDK 持有实时投影；`run-actions` 只持有动作幂等快照。`Transcript` 保留消息顺序和稳定 ID，`SubtaskDetail` 展开时订阅 scoped 数据，详情只用一个 Inspector。

普通消息、审批 resume、运行中消息入队是三个动作。审批禁止覆盖运行配置；入队 ACK 不等于消费，unknown 必须复用原 ID/key/body。历史 checkpoint 只在用户打开时读取，不覆盖实时消息。

## 7. 新增代码粒度规范

> **适用范围：仅约束新增代码。存量代码不在此规范的覆盖范围内，不得借此规范触发对旧代码的"顺手重构"。**

### SFC（单文件组件）

| 部分                  | 新增目标 | 超出信号                               |
| --------------------- | -------- | -------------------------------------- |
| `<script setup>`      | ≤ 150 行 | 超出时抽 Composable                    |
| `<template>` 嵌套层数 | ≤ 5 层   | 超出时提取子组件                       |
| Props 数量            | ≤ 6 个   | 超出时用 object prop 或 provide/inject |

### Composable（`use*.ts`）

- 一个 Composable 只管一个关注点（状态、数据请求、事件处理三类不混用）
- 新增 Composable 内单个函数目标 ≤ 60 行
- 暴露的返回值保持最小：只导出调用方真正用到的 ref / 函数，不把内部状态全量暴露

### 函数原子化

- 一个函数只做一件事：要么计算/转换数据，要么触发副作用，不混用
- 新增函数参数目标 ≤ 4 个；超过时用 options object 包裹
- 嵌套层数目标 ≤ 3 层；优先用 early return 扁平化

### 信号而非硬阻

上述数字是设计目标，不是 CI 门禁。若某组件确需更多行（如复杂表单编排、富文本渲染），在文件顶部注释说明原因。

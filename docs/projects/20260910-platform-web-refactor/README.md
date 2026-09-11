# Platform Web 架构与 Agent Chat 重构

## 项目概述

- **启动日期：** 2026-09-10；本期开发收尾日期 2026-09-11。
- **目标：** 重建可维护的正式平台前端，完整对接重构后的 Platform API，以 open-swe 的工作过程展示和对话交互为主要参考。
- **级别：** 治理改动。涉及前端架构、身份与项目隔离、执行及审批交互；不是单纯页面换皮。
- **负责人：** 待指定；方案由 AI 整理，架构批准和产品验收由人完成。
- **状态：** **01—07 非后置开发完成；08 按用户确认的完整旧工作台重新验收（partial）**；双浏览器同 Thread 入队、完整文件/Skills API、PTY 为 deferred。旧前端组件已直接取回，最新实施与验证见 [14](implementation/14-copy-original-chat-components.md)。
- **预计工作量：** 原前端 22–30 人天；新增队列 10–16 人天，合计约 32–46 人天（若纳入全部范围）。不含待确认的 GraphHarbor 扩展、评审等待与部署窗口，见 [06](06-delivery-and-acceptance.md) 与 [07](07-message-queue-and-middleware.md)。

## 阅读顺序

1. [01 现状审查与退役清单](01-current-state-and-retirement.md)：哪些确实有问题、证据在哪里、保留和删除什么。
2. [02 目标架构、信息架构与 UI](02-architecture-and-ui.md)：目录职责、状态归属、路由、控制面和 Chat 的布局设计。
3. [03 后端契约与接入边界](03-api-contracts.md)：Agent/Graph/Model、鉴权、schema、SDK 与网关、幂等和能力缺口。
4. [04 Chat 会话与交互](04-chat-session-and-interaction.md)：发送、恢复、取消、切换项目、多 interrupt、编辑重发的完整流程。
5. [05 渲染能力矩阵](05-rendering-matrix.md)：逐项对照参考文档的 13 项能力，细化文本、工具、子智能体、文件和产物。
6. [06 实施顺序与总体验收](06-delivery-and-acceptance.md)：阶段门禁、工作量、测试场景、切换和回退。
7. [07 多端消息入口、队列与 Middleware](07-message-queue-and-middleware.md)：最后实施；四项借鉴点覆盖、三服务责任、持久化/消费/回执、竞态与 GraphHarbor 边界。

8. [08 旧 Chat 视觉恢复与 Agent 入口归一](08-visual-and-agent-alignment.md)：本仓库进程启停、旧视觉恢复、已授权 Graph 自动对齐。
9. [09 完整工作台功能核对与补齐清单](09-chat-workbench-restoration-audit.md)：直接对照旧源码与当前实现，记录 14 项逐项恢复状态、实测证据、待验及后置边界。

采用多专题模板：平台基础、API 契约、Chat 交互、渲染和交付可分别验收，且预计跨多个阶段。任务与验证就在各专题中，不再重复维护全局 plan/tasks/verification 文件。

## 范围与默认决策

| 范围 | 决策 |
| --- | --- |
| `apps/platform-web` | 主实施范围；允许替换旧实现、旧路由和旧本地存储，不建立兼容层 |
| `apps/platform-api`、`apps/runtime-service` | 原前端基于当前契约实施；新增消息接口、持久收件与根 Agent 中间件详见 07，独立记录新增扩展评审 |
| `interaction-data-service` | 不新增浏览器直连，不恢复退役的知识库/测试用例产品 |
| 技术栈 | 保留 Vue 3、TypeScript、Vite、Pinia、Vue Router、Tailwind、官方 LangChain Vue SDK；不因参考项目使用 React 就整体换栈 |
| SDK 升级 | 用户已允许升级最新稳定版本；已安装 Vue 1.0.35 / LangGraph SDK 1.10.2；GraphHarbor post27 发布包兼容链路通过，见 10 |
| 视觉 | 保持当前风格和浅/深主题，复用已有成熟组件；只做更简约的布局/密度调整，不重建一套设计系统 |
| Chat | 新建一条会话编排和渲染主链，替换 `BaseChatTemplate` 及重复投影；不继续在其上叠补丁 |
| 控制面 | 按能力重新组织和收敛页面，保留有效项目、用户、Agent、模型、授权、审计和治理能力 |
| 冗余代码 | 退役资源模板站、内嵌参考源码、固定 SQL Agent 入口、旧聊天投影和无消费者组件；逐项核对引用后删除 |
| 运行中追加消息 | 07 放在前端主体 G6 验收之后完成，Q0 也后置；此前保留草稿/停止后发，不预建队列抽象、接口占位或组件。完整四项借鉴点必须以队列验收为准 |
| 新增组件与基础设施 | 复用现有 Vue 组件、服务进程和 PostgreSQL；队列是业务服务内部模块，不新增独立队列服务、消息代理或 UI 组件库 |
| GraphHarbor | 定位等价于官方 LangGraph Server，只维护通用执行引擎能力；可修复经复现的引擎缺陷，禁止加入平台/Agent 业务逻辑 |
| 多 interrupt | **本期必做**，与“运行中追加消息队列”是两个不同问题 |
| Sandbox/Skills/Diff/Artifacts | 本期做基于已公开 state/tool output 的可信展示；完整文件浏览、交互终端等缺口明确后置 |
| 兼容 | 不迁移旧 Thread、审批、偏好、旧 URL；支持新版本上线之后产生的 Thread 刷新恢复 |

## 事实源与冲突裁决

- 后端交接：[05-frontend-handoff.md](../20260910-platform-api-refactor/05-frontend-handoff.md)。其“后续不重搭架构”是上一阶段范围限定，**本轮用户明确允许推翻前端，该范围限定被本需求覆盖**；字段、安全和运行约束继续有效。
- 后端公开网关：[runtime-gateway-interface-standard.md](../../../apps/platform-api/docs/standards/runtime-gateway-interface-standard.md)。当前为 20 条公开路由，不把 SDK 所有方法都当作已暴露。
- 主要参考项目：相对仓库根目录 `../research/open-swe`，审查版本 `ad417d64`。
- 必读参考：`../research/open-swe/docs/frontend-rendering-matrix.md`、`../research/open-swe/docs/ui-agent-interaction.md`；源码对照见 [05](05-rendering-matrix.md)。文档中的伪代码不是平台接口规范。
- 本仓库审查基线：`612fbde`，开始时工作区干净；统计只代表此次本地快照。
- 原审查安装版本：`@langchain/vue 1.0.29`、`@langchain/langgraph-sdk 1.9.28`；用户已允许升级。实施时重新核对最新稳定包、peer 依赖、公开类型与真实网关行为，不沿用旧类型限制判断新版。
- 现有前端标准与新后端有矛盾：`agent_key`、Operations、旧视觉参考等内容在实施时修订；本轮已同步更新前端三份活标准。
- GraphHarbor 源码仓库：`~/PyCharmMiscProject/graphharbor`（相对本仓库根为 `../graphharbor`）。开发中发现通用协议、执行或持久化缺陷，可在该源码仓库修复并验证，不改安装目录。详细边界见 [07 §3](07-message-queue-and-middleware.md#3-存储与执行引擎前置门禁-q0)。
- GraphHarbor 发布凭据文件：`~/.my_best/.env`，由用户提供位置。post27 已按用户发布授权在进程内使用凭据；密钥值不写入文档、代码或日志。该授权不等于后续任意版本自动发布。

## 评审记录与新增范围

2026-09-10 用户明确“我同意这个方案，保留 Vue 和官方 SDK，重写 Chat 编排、渲染及相关页面”，并补充 SDK 可升级、保持现有视觉。原决策记录如下：

1. 保留 Vue 技术栈，允许重写 Chat 和控制面编排，不保留旧 URL/数据兼容。
2. 采用 [02](02-architecture-and-ui.md) 的导航和工作区；删除资源模板站及固定 SQL Agent 页面，保留动态部署图入口。
3. [03](03-api-contracts.md) 保留真实后端边界；用户追问的队列已细化到新增 07，完整文件/Skills 浏览、PTY 仍按原边界处理。
4. 将真实流式、并行子智能体、多 interrupt、取消确认、跨项目隔离列为发布门禁。
5. 按 [06](06-delivery-and-acceptance.md) 先打通最短链路，再扩展渲染与全站；旧代码删除以该清单为范围。

| 评审项 | 结果 | 评审人/日期 |
| --- | --- | --- |
| 原前端范围、架构、删除清单、验收与切换条件 | 已批准，已分阶段实施 | 用户 / 2026-09-10 |
| Vue/官方 SDK 保留，SDK 可升级，沿用视觉组件 | 已确认 | 用户 / 2026-09-10 |
| 07 最后实施，不新增独立基础设施；GraphHarbor 保持通用引擎边界，可修复通用缺陷 | 已确认 | 用户 / 2026-09-10 |
| 完成 01—07 全部需求，含最后的队列扩展 | 已授权持续实施；遵守既定服务边界及验收要求 | 用户 / 2026-09-10 |
| 08 本仓库进程启停、旧 Chat 视觉恢复、授权 Graph 自动对齐 Agent | 已批准；保留重构后的 Chat 逻辑 | 用户 / 2026-09-11 |
| 备份后重建本地 Platform API 开发库及 SDK scoped 验收修复 | 已明确批准，备份保留，重建与复验完成 | 用户 / 2026-09-11 |

用户已要求开始并完成全部需求，原方案及新增 07 均按既定范围实施，不重复请求批准。07 后置顺序保持；遇到超出既定服务边界或确需用户决定的事项再说明。各专题先前的待实施描述随实际阶段更新，当前执行状态以本概览和 implementation 记录为准。

## 2026-09-11 实施与验收进度

此次根据实际源码、重新执行的测试及浏览器/产物证据核对，不只读取旧文档。完整记录见 [11 收尾记录](implementation/11-closeout.md) 和 [12 视觉、Agent 与启停验收](implementation/12-visual-agent-and-local-stack.md)。

| 专题 | 开发状态 | 验收依据 |
| --- | --- | --- |
| 01 退役 | `done` | 删除 17 个模块与 262 个参考文件、无消费者依赖/旧脚本；真实路由及生产产物检查 |
| 02 架构与 UI | `done` | 单一导航权限、会话隔离、移动布局、保留管理页面四态 |
| 03 契约 | `done` | 官方 SDK 升级、字段白名单、真实 scoped 流；checkpoint_id 分支修复 |
| 04 Chat | `done` | 发送/冻结 key/恢复/取消、混合审批、编辑分支及旧响应隔离 |
| 05 渲染 | `done`（首期） | 13 项逐行验收，三尺寸并行/嵌套、真实 Showcase、安全/性能 |
| 06 交付 | `done`（非后置） | 构建/解包哈希、恢复产物真实浏览器、竞争 Run/幂等网关验证通过 |
| 07 队列 | `done`（非后置） | PG claim/checkpoint/恢复、消费授权、Web receipt、取消/长任务注入 |
| 08 视觉与入口对齐 | `partial` | Agent/启停既有验收保留；旧组件已直接取回；37 项定向测试及三尺寸审批/子图通过，剩余数据与专项验收见 09、14 |

主要证据：Web 全量 74 passed / 1 skipped，另新增迟到父 Run 单测通过；Runtime 定向 48 passed / 1 skipped（外部模型另测通过）；三尺寸复杂 Chat 及恢复产物各 3 passed；控制面 2 passed；真实 Showcase 1 passed，工作区与 stdout 为 43.50；长会话 input→paint P95=29ms。所有结果按测试范围记录，不把 mock 当真实外部模型。

08 前序复验（不代表后续完整旧工作台要求已通过）：Web 全量更新为 77 passed / 1 skipped；API Agent 4 passed、网关流与 adapter 16 passed；三尺寸并行/嵌套 Chat 3 passed，真实 Graph Agent/移动端 3 passed。lint、类型检查和生产构建通过。旧本地库已完整备份后重建，当时项目/模型待重新配置；本轮模型已录入，详见 13。

旧工作台源码已取回，历史摘要数据及部分专项验收仍有待办，详见 [09](09-chat-workbench-restoration-audit.md)。以下为明确后置范围，不能用来排除 09 的还原缺口：

- 双浏览器同 Thread 同时入队（QV01）。
- 完整文件/Skills API、交互式 PTY；首期公开数据展示已完成。

无新增基础设施，无 GraphHarbor 业务代码，本次未新发布 GraphHarbor、未部署生产、未提交或推送代码。GraphHarbor post27 的发布属于前序已批准操作。产品最终人工签收和生产部署不由 AI 代为批准。

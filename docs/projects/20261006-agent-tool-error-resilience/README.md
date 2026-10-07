# Agent 工具调用容错与生产接线补齐

## 项目概述

- **启动日期：** 2026-10-06；非前端交付日期：2026-10-07。
- **目标：** 借鉴 open-swe 的工具失败反馈机制，补齐生产 Agent 的可恢复错误处理，保留权限、中断、取消和不可恢复错误的真实语义。
- **负责人：** Codex 负责后端/Runtime 实施；前端由用户同事负责。
- **模板类型：** 标准模板。错误分类、消息契约、Agent 接线和前端消费相互依赖，属于同一个专项。
- **改动级别：** 治理改动。涉及 Agent 失败策略、安全错误边界及跨层消息消费；代码主要在 `runtime-service`。
- **状态：** 已完成（done）。2026-10-07 Runtime/后端实施、前端展示适配与浏览器联合验收全部通过，全链路 Final 验证完成，未生产部署。
- **预计工作量：** Runtime/后端 4-6 人天，前端 0.5-1 人天，联合验收 1-2 人天；按一名实施人员估算，不含环境准备和评审等待。

## 阅读顺序

1. [源码对照与方案辨析](open-swe-comparison.md)：open-swe 如何做、当前差距，以及同事方案的逐项取舍。
2. [整体方案](plan.md)：三层职责、错误边界、代码落点、接线顺序及实施范围。
3. [任务拆分](tasks.md)：实施与验收任务，进度唯一来源。
4. [前端交接](frontend-handoff.md)：交给同事的消息样例、页面范围、交互边界与验收清单。
5. [验证计划和记录](verification.md)：已执行的基线检查，以及实施后必须完成的门禁。

## 核心结论

1. “当前没有 `ToolErrorMiddleware`，工具抛异常就会崩溃”不适用于全仓库。`reference_agent` 已使用官方组件；多个工具、MCP adapter 和官方文件系统工具已有错误结果处理。
2. 真正缺口是 `dearflow_agent` 和 Showcase 模板没有统一的选择性异常策略，主/子 Agent 接线及第一方错误内容缺少一致契约。
3. 复用锁定版本的官方 `ToolErrorMiddleware(on_error=...)`，增加小型分类/格式化函数。无需复制 open-swe 的同名中间件类、通知集成或 Sandbox 异常类型。
4. 不采用“所有异常转错误消息”。权限/契约错误、`GraphBubbleUp`、取消和未知程序缺陷继续向外传播；已提交写操作保留 unknown/任务凭据，或使用 `do_not_repeat` 错误摘要，先核对结果。
5. 本期不新增生产自动重试。错误反馈让模型选择下一步，现有调用预算限制循环；示例 Agent 的现有只读重试保留并回归。
6. API 不执行或重试工具。前端已有失败展示，补摘要与联验即可；Runtime 可以独立接入，整个专项验收仍包含同事负责的前端任务。
7. 锁定 LangGraph 的 `tool-error` 流事件可携带原异常文本，离线已复现。T06 已修复独立流出口，T07 补齐公开 fatal/任务错误；安全 ToolMessage 和各流事件分别验证。

## 范围

| 层 | 本期工作 | 是否需要业务代码 |
| --- | --- | --- |
| `runtime-service` | 第一方错误分类/格式化；DearFlow、Showcase 及子 Agent 接线；tool-error 流出口；MCP 和工作区故障边界；回归 | 已实施，使用现有组合根与官方组件 |
| `platform-api` | 保持 ToolMessage、namespace、Run 终态；修正已复现的公开 fatal lifecycle/Thread/原生任务错误泄露 | 已修既有 SDK adapter 出口并补回归，工具执行策略仍在 Runtime |
| `platform-web` | 保留工具失败与 Run 失败分离；结构化错误摘要、旧消息兼容、子任务/历史一致性 | 小范围，由同事实施 |
| GraphHarbor | 复用 Run、checkpoint、取消、中断与事件事实 | 不修改；无法满足的底座问题单独记录 |

本期不扩展成全部 Agent 生产化改造。模型 fallback、持久队列、Harness 重构、Sandbox 重建、PR/Slack/GitHub/Linear 集成、管理配置页面均不在本次开发清单内。

## 评审状态

| 事项 | 当前状态 |
| --- | --- |
| 规划产物 | 已完成；基线验证见 verification.md |
| 错误分类、停止运行边界与结构化内容 | 2026-10-06 用户评审批准，见 tasks.md G0 |
| Runtime 与后端代码实施/非前端验证 | 已完成；完整隔离 HTTP、重启/回退、真实模型、MCP/Docker、安全和扩大回归通过 |
| 前端实施与联合验收 | 已完成；纯函数抽取与单测全绿，浏览器联合验收 F01-F08 全部通过 |
| 生产发布 | 不包含；没有发布授权 |

人工评审结论填写到 [tasks.md 的 G0](tasks.md)，包括批准人、时间、范围和调整项。规划交付不代表功能 `done`。

## 交付定位

本次 worktree 为 `4fc0/ai-agent-platform`，detached HEAD `424ff90e`；无命名开发分支，未提交、推送或部署。
后端实际证据见 [implementation/03-isolated-verification.md](implementation/03-isolated-verification.md)，同事接手
[frontend-handoff.md](frontend-handoff.md)。两者均在本 worktree 的 `docs/projects/20261006-agent-tool-error-resilience/` 下。

## 关联事实源

- [Runtime 开发规范](../../../apps/runtime-service/docs/standards/runtime-service-development-standard.md)
- [既有 Middleware 生命周期与失败语义](../../../apps/runtime-service/docs/knowledge/15-runtime-middleware-lifecycle-and-failure-semantics.md)
- [DearFlow 既有可靠性审计](../20260913-dearflow-agent/14-effect-parity-and-reliability.md)：本专项只处理工具错误，不重置原专项状态。
- [Harness 待评审方案](../20260930-runtime-agent-harness-refactor/README.md)：独立专项，本次不依赖其装饰器/Builder。

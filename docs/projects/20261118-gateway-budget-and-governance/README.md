# AI 网关预算控制与财务熔断治理

> **项目状态：** 部分完成（partial）。2026-11-18 后端实现及本地关键链路验证已具备，前端交接已交付；真实供应商/主备组合、性能阈值、完整回退与人工整体验收仍待接续。
> **启动日期：** 2026-11-18
> **责任服务：** `platform-api`、`runtime-service`、`platform-web`
> **授权边界：** 用户追加授权创建 Worktree 并开发本次功能；前端由同事实施，本轮负责提供交接文档。未授权提交、推送、合并或部署。

## 用户要解决什么问题

管理员需要为当前租户或指定项目设置每日、每周或每月的模型费用预算。用户在用量中心查看已用金额与重置时间；达到额度时收到通知，并按策略决定继续运行还是停止新增模型调用。

现有单 Run Token / 执行次数限制负责约束单次任务，不能替代跨请求累计预算。本项目借鉴 mlflow-eval-platform 的预算策略展示与操作，保留 GLOBAL / PROJECT、USD、固定周期、ALERT / REJECT 和 Budgets 页面范围。

## 修订后的关键方案

- **控制面管理，Runtime 执行：** Platform API 管策略、权限和审计；Runtime 在每次真实模型调用前检查，结束后逐调用记账，覆盖长 Run、子 Agent 和已纳管辅助调用。
- **复用调用账本：** 用 Runtime PostgreSQL、Decimal 与事务窗口派生，不依赖整 Run completion、可选 Trace 或 Redis 浮点金额累计。
- **累计准确与支出上限分开：** 达到额度后拒绝新增调用；已放行的并发在途调用仍可能使支出超额，不增加资金预占。
- **未知不能补零：** 新策略回填本周期历史，迟到费用归开始周期，恢复前标记不可核实。REJECT 在无法核实账务时停止新增调用。
- **持久事件驱动通知：** 两种动作均生成首次超额事件，事务 outbox 重试，站内按事件 ID 去重；外部渠道不承诺端到端 Exactly Once。
- **页面解释真实状态：** 保留三色进度与 CRUD，明确完整、未知 / 恢复中、规则已保存待应用及受控拒绝状态。

费用是现有价格快照计算的估算费用，不是供应商最终账单。ALERT 也不保证基础设施故障时无条件运行：无法持久化新调用开始标记时，不发送模型请求。

## 当前进度与下一步

Task 1、Task 2、Task 4 已完成；Task 3 核心链路接线与本地 HTTP/Worker、通知恢复已验（真实主备/异步恢复组合待补供应商额度）；Task 5 已有阶段证据，完整联合验收仍未完成。任务状态只在 [tasks.md](tasks.md) 维护，不因前端/后端阶段通过标项目整体完成。

前端 Task 4 全栈能力已实施并闭环验证：聊天模块防爆契约与中文友好提示、高精度定点预算计算 Composable、三态进度条矩阵（complete 三色条 / reconciling 脉冲骨架 / unverifiable 斜纹报警）、作用域自适应弹窗及用量中心 Tab 双向驱动与路由下钻联动；47 项用量中心单测 100% 通过，`vue-tsc` 类型检查 0 错误，生产构建（`pnpm build`）打包成功。

后端方面，Runtime 真实 PostgreSQL 专项 34 项、API 专项 30 项通过；实际平台认证→Runtime API/Worker→可控 OpenAI HTTP 证明 0.6+0.5 后 429、ALERT 继续、SSE 停止、历史原因、调额恢复和 Thread 删除不减账。进程重启/投影重建保留 2.5 USD，事件重投站内仍 1 份。模型费用为合成数据，不能当作供应商实际扣费成功。

首选maomaoai模型实际返回403额度不足，由账户维护者补额度后后端继续验证。扩大回归各有1项HEAD可复现的既有失败，另有既有Resilience多轮工具KeyError，均在实现记录保留；不宣称全回归通过。本地8并发性能已测，但没有已确认SLO，不能据此给F9通过。

开发位置为 `../ai-agent-platform-gateway-budget`，分支 `feat/gateway-budget-and-governance`，独立环境 `wt_1c4f0f7fb905`。联调入口：Web24824、API26911、Runtime24254，均为本机回环；启动与当前端口以运维手册和local-stack状态为准。

**启用与回退注意：** Worker领取保护对整个Runtime执行域生效且粘性保留，空策略同步/能力检查也会激活。首次启用须排空running Runs；激活后关开关不会撤销。回退要保留账务保护或暂停整个执行域，不能通过删除栅栏恢复旧Worker运行。

## 文档导航

- [plan.md：执行架构与记账规则](plan.md)
- [tasks.md：任务、状态与独立验收条件](tasks.md)
- [verification.md：阶段验证与整体验收场景](verification.md)
- [frontend-handoff.md：同事前端实施与接口交接](frontend-handoff.md)
- [backend-runbook.md：环境、启用、恢复与兼容回退](backend-runbook.md)
- [implementation/01-backend-validation.md：测试、HTTP、恢复与性能证据](implementation/01-backend-validation.md)

关联背景：[网关观测与用量项目](../20261117-gateway-observability-usage/README.md)。项目状态同步至 [CONTEXT](../../CONTEXT.md) 与 [FEATURES](../../FEATURES.md)。

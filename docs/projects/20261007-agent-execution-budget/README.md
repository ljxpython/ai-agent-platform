# Agent 执行预算、步骤限制告警与软收尾

## 项目概述

- **启动日期：** 2026-10-07；同日用户批准并实施非前端范围。
- **目标：** 借鉴 open-swe，在现有 Agent 组合根中装配通用预算告警和软收尾，并让平台用户准确知道运行为什么停止。
- **负责人：** Runtime/Platform API 由当前开发者接续；前端由用户同事实施；方案由用户指定的人工评审者批准。
- **模板类型：** 标准模板。预算产生、流契约、错误出口和前端展示相互依赖，属于同一个交付闭环。
- **改动级别：** 治理改动，涉及执行限制、失败语义和跨服务公开事件；保留现有三服务架构。
- **状态：** 已完成（`done`）：Runtime、Platform API、Platform Web（F01-F04）开发与全量门禁已闭环完成；单元测试与类型检查 100% 绿色通过。未提交、推送、部署或调整现役配置。
- **预计工作量：** Runtime 4-6 人天、API 1-2 人天、前端 1-2 人天、联合验收 1-2 人天；不含环境准备和评审等待。

## 阅读顺序

1. [源码对照与方案辨析](open-swe-comparison.md)：参考项目实际做法、当前能力、同事方案取舍及代码证据。
2. [整体方案](plan.md)：已批准并实施的预算定义、三层职责、接入方式、事件契约、代码落点和风险。
3. [任务拆分](tasks.md)：评审、实施、同事前端任务和验收；这是唯一进度来源。
4. [前端交付报告](frontend-delivery-report.md)：可直接转交同事的实施入口；[详细交接](frontend-handoff.md)包含类型、文案、状态矩阵、恢复与 H01-H16 验收。
5. [验证计划和记录](verification.md)：基线与修复记录、非前端 Final 和待前端联合验收；[安全事件证据](implementation/budget-http-evidence.json)包含真实公共 SSE 样例。

## 核心结论

1. `recursion_limit` 限制图的 superstep，`ModelCallLimitMiddleware` 限制模型调用次数。两者不能统称为同一种“步骤”。
2. 当前 DearFlow/Showcase 已有 run/thread 模型与工具预算、单次模型超时；Reference/Workflow 已有模型预算。需要补齐的是告警、收尾提示和限制原因的产品展示。
3. open-swe 的 `after_agent` 通知只覆盖官方 `exit_behavior="end"` 产生的人工消息；它不处理 `GraphRecursionError`，也不覆盖我们生产模板的 `exit_behavior="error"`。
4. 保持现有 hard limit 和退出策略；薄扩展官方模型预算中间件，在限制发生处产生结构化通知。图预算使用官方 `RemainingSteps`，不另写 Agent 循环或自建计数器。
5. GraphHarbor post41 已提供 Run 硬超时、事件持久化和重放。复用这些能力，不新增 Run 调度器、通知数据库、轮询 Worker 或通用 Harness。
6. 时间软收尾不等于 Run 硬超时。当前 Runtime 没有 Worker 的权威 deadline 字段，首期明确使用 Agent invocation 的软时间阈值，不能承诺“距 Worker 超时还有 N 秒”。
7. API 基线复现的 `tasks.error` 原文外泄和错误码断言冲突已按人工评审修复；泛化下划线 code 和字符串形状保持兼容，四种预算异常有固定安全码。

## 非前端交付结果

Runtime 受影响回归 **253 passed**；API **81 passed、1 skipped、423 subtests passed**；真实隔离 HTTP/PG/Redis Worker durable 测试 **1 passed，23 个场景全部通过**，包含真实模型 smoke、安全隔离、重放、HITL、取消、硬超时、并行子 Agent 和旧限制器读取新 checkpoint。跳过项不计通过。

模型通知扩展对照官方限制器均为 **2 model calls / 8 supersteps**；时间软收尾缺省关闭。新 Agent 可直接复用共享 middleware；自定义 StateGraph 参考 Workflow/Showcase 适配。没有新增依赖、路由、数据表或 GraphHarbor 补丁。

## 三层职责与必要性

| 层 | 是否需要 | 本期职责 |
| --- | --- | --- |
| runtime-service | 必须 | 读取真实预算、预警、软收尾提示、限制事件、主/子图接线与结构化日志 |
| platform-api | 平台产品闭环必须 | 对已有 SSE/JSON 错误出口做安全投影，透传通知，保护内部状态；不执行 Agent |
| platform-web | 平台产品闭环必须；由同事开发 | 显示告警与停止原因，区分 Run/Thread 限额和子图影响；使用现有 SDK 状态与动作 |
| GraphHarbor | 不修改依赖包 | 继续持有执行终态、checkpoint、取消、中断、硬超时和事件重放；纳入兼容性验证 |

## 范围与验收口径

用户已批准方案并授权实施；模型/图预算告警、停止原因、独立软收尾、四正式 graph 适配、安全出口以及前端 Web 界面层（F01-F04）均已实施完成。

不扩展为所有生产化能力的总改造；工具预算算法、费用计费、全局父子共享配额、自动续跑、任务完成裁决、Slack/Linear/GitHub/PR 通知、配置管理页面和 Harness 重构均不在本期。

本轮全链路范围已达到 `done`；前端 F01-F04、全仓单测（571 passed）、构建与 lint 门禁 100% 绿色通过。子图 `end` 可返回父图继续，现有 DearFlow/Showcase 子图 `error` 会沿父图传播；前端遵循真实父 Run 终态展示。

## 评审状态

人工评审已完成：2026-10-07 用户在会话中明确批准方案及全部非前端开发，R01-R06 结论见 [tasks.md 的 G0](tasks.md#g0-人工评审)。

重点评审：退出策略保持不变；告警余量；Thread 限额的后续动作；软时间阈值独立于 Worker deadline；公开错误码及当前测试/文档冲突；事件缺失的降级语义。

## 与现有专项的关系

- [可观测性与追踪](../20261006-agent-observability-hardening/README.md)：复用本地日志、Langfuse 和既有诊断入口；不扩展诊断 DTO 或新增查询接口。
- [工具容错专项](../20261006-agent-tool-error-resilience/README.md)：保留控制流和非幂等错误的真实语义；本次为预算异常补明确出口，并处理已复现的相邻错误槽位问题。
- [Harness 重构规划](../20260930-runtime-agent-harness-refactor/README.md)：独立待评审，本次不依赖其 Builder/装饰器。
- [LangGraph v3 评估](../20261004-langgraph-v3-delta-evaluation/README.md)：保留 v3 默认和显式旧流兼容，不以本次取代原专项的遗留门禁。
- [当前 SSE 标准](../../standards/sse-event.md)和[错误 Envelope](../../standards/error-envelope.md)：已同步获批预算契约；SSE/JWT 的其他专项门禁仍未完成，状态继续为 draft，不由本项自动毕业。

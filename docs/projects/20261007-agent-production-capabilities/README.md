# Agent 运行准备幂等与有界重试

## 项目概述

- **启动日期：** 2026-10-07；非前端交付日期：2026-10-07。
- **目标：** 借鉴 open-swe 的运行准备与子任务容错设计，提供由各 Agent 组合根显式装配的通用能力，避免重复副作用、重试放大和错误语义丢失。
- **负责人：** Codex 负责已获批的 Runtime/后端开发、验证与交接；用户同事负责前端实施与浏览器验收。
- **模板类型：** 标准模板。两个实施主题共享执行身份、恢复和错误边界；自主唤醒是条件性后置项，不另建实施专题。
- **改动级别：** 治理改动，涉及崩溃恢复、生产失败策略、权限校验和跨服务诊断契约。
- **状态：** 全部任务（非前端 T01-T09/T11/T12 及前端 T10、Playwright 全链路 E2E 验证）均已 `done`。保留 12 项真实浏览器高保真截图证据，未部署现役服务。
- **预计工作量：** Runtime/后端 7-10 人天、前端 0.5-1 人天、隔离环境联合验证 2-3 人天；不含评审等待、环境准备与生产发布。

## 阅读顺序

1. [源码对照与方案辨析](open-swe-comparison.md)：上游实际设计、当前差距，以及同事方案的取舍依据。
2. [整体方案](plan.md)：三层职责、通用组件契约、代码落点、接线与回退。
3. [任务拆分](tasks.md)：唯一进度入口；每项都有代码位置、结果和验收条件。
4. [前端交接](frontend-handoff.md)：同事开发范围、冻结 DTO、实际响应样例、交互边界和浏览器验收。
5. [验证计划与记录](verification.md)：本机 PostgreSQL/Redis、HTTP/Worker 故障与回退、非前端 Final 和待前端补验的边界。

## 关键结论

1. open-swe 的 `task_retry.py` 配合的是 `ToolRetryMiddleware(tools=["task"])`，不是 dispatch 的整个 Run 重试；`task_on_failure` 也不吞掉所有不可重试异常。
2. prepare 的 checkpoint 标记只避免已完成步骤的重复工作，不提供外部副作用的 exactly-once 保证。副作用发生、checkpoint 未提交的窗口必须靠操作自身的幂等性解决。
3. 当前已有提交幂等、同步 checkpoint、工具错误反馈、Skills 执行快照、模型调用超时、调用限额和定时任务。补齐范围是公共 prepare 约定和生产 Agent 的有界重试接线，不重新实现这些能力。
4. 模型调用与只读子任务分别使用官方重试组件；同一个失败单元只设一个负责人。写操作子任务不因 provider 429 或超时就整体重放。
5. GraphHarbor 已有 Worker 基础设施重排。Runtime 必须防止自身耗尽的 provider 重试继续触发 Worker 的整个 Run 重试；真实数据库、租约和进程故障仍由 Worker 处理。
6. 前端不参与幂等判定或自动重试，只扩展现有 Run Diagnostics 的安全摘要并完成联合验收。
7. 当前没有 Agent 自主唤醒工具；本期不新增该工具、计数器或调度服务。未来有明确消费者时，再评审平台原子预算与身份延续设计。

## 三层范围

| 层 | 是否需要 | 本期内容 |
| --- | --- | --- |
| `runtime-service` | 必需，主要开发位置 | 公共 prepare 标记及资源检查；官方模型/只读 task 重试的薄扩展；安全失败语义；DearFlow、Showcase、Reference 及相关子图接线 |
| `platform-api` | 必需但小范围 | 诊断 DTO 的可选字段投影、脱敏与契约测试；回归既有提交幂等/恢复授权/Run 终态；不新增运行队列或 retry endpoint |
| `platform-web` | 展示与联合验收需要，同事负责 | 复用诊断面板呈现准备结果和重试次数；旧响应兼容、目标隔离、停止/中断/恢复回归；不新建配置页或状态机 |
| GraphHarbor | 复用及验证 | 复用 Run/checkpoint/租约/cron；核实 Worker 重排边界，不在本期修改外部包 |

## 不纳入本期

不迁入 GitHub token、PR、Slack、Linear、发送人属性、外部完成通知或 open-swe 的 sandbox 专属实现。不新增通用 Agent Builder、Tool Registry、持久队列表、Run 自动重启服务、模型 fallback 或新的 retry 配置管理页。后置的自主唤醒见方案中的条件清单。

## 评审门禁

G0 在 [tasks.md](tasks.md) 记录用户的人工批准、日期、范围及调整项；本期获批非前端实施已完成，未来扩大范围需另行评审。

评审重点：prepare 只保护什么；写操作不自动重放；重试上限及耗时；provider 耗尽与 Worker 重排的隔离；诊断安全字段；前端交接范围。用户于 2026-10-07 明确批准方案并授权完成所有非前端项，见 G0 记录。本次不提交、推送或部署现役服务。

## 关联项目

- [工具调用容错专项](../20261006-agent-tool-error-resilience/README.md)：复用选择性错误反馈和公开错误脱敏，不重置该项目状态。
- [可观测性专项](../20261006-agent-observability-hardening/README.md)：复用诊断查询、权限和前端面板。
- [定时任务专项](../20261005-scheduled-agent-tasks/README.md)：复用原生 cron 和执行前聚合授权；自主唤醒没有被该专项实现。
- [Harness 待评审方案](../20260930-runtime-agent-harness-refactor/README.md)：独立项目，本期不依赖其装饰器或 Builder。

## 证据基线

当前项目 HEAD：`bf47991b7592b19cbda1051c6a674623450318ae`。参考源码为用户指定的本机 open-swe checkout，HEAD：`ad417d64d91cc349d63d832c7b643637dc1774cf`。本次参考的 prepare、task retry、server、dispatch、wakeup 和测试文件都有未提交改动，`uv.lock` 为未合并状态。HEAD 仅用于定位 checkout，不代表所读内容均已提交，也不能据此宣称远端最新实现或稳定发布依赖。版本、源码依据、37 项实施前基线与实施后证据见 [验证记录](verification.md)。

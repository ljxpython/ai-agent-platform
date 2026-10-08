# Agent 运行取消与中断通用能力

## 项目概述

- **启动日期：** 2026-10-07。
- **目标：** 为所有平台 Agent 提供有授权、可重试、可核实、保留证据的会话停止流程，并返回停止后的实际进度。
- **模板类型：** 标准模板。取消、队列收敛和状态报告属于同一条验收链路。
- **改动级别：** 治理改动，涉及执行控制、持久化、权限和跨服务契约。
- **状态：** done（前端与后端全链路闭环，真实模型 E2E 验收通过；B02 正式发布待发布指令）。
- **分工：** 后端与 Runtime 实施完成；前端由老王完成全链路接入与 Playwright 自动化验证。
- **工作量估算：** 按 tasks.md 分项，后端、Runtime、GraphHarbor 配套及隔离验证约 11-17 人天；前端已完成闭环。

## 阅读顺序

1. [源码对照与同事方案评估](open-swe-comparison.md)：open-swe 的三种停止路径、当前已有能力、真正缺口。
2. [整体方案](plan.md)：三层职责、停止语义、原子边界、数据归属、通用适配方式和代码位置。
3. [任务完成卡](tasks.md)：后端、Runtime、前端完成项及全部验收证据。
4. [前端交接报告](frontend-handoff.md)：实现版接口、类型、状态机、错误处理、代码落点和 F01–F10 验收。
5. [验证计划与证据](verification.md)：单元、真实集成、E2E、故障、性能与回退门禁。
6. [人工评审清单](review.md)：需要人确认的产品语义、权限和引擎配套范围。
7. [发布接入清单](release-handoff.md)：唯一post43四产物、哈希、已验门禁与正式源接入/回退步骤。

`tasks.md` 是进度来源；[implementation/](implementation/01-engine-and-runtime.md) 记录代码位置与原因，evidence/ 保存脱敏验收、迁移与候选 hash。

## 范围

| 服务 | 是否需要改动 | 本项目职责 |
|---|---|---|
| platform-web | 已完成 | 接入会话停止、动作回执与报告；状态机解耦与 45s 超时降级；Playwright 真实模型全链路闭环已验证 |
| platform-api | 需要 | Thread edit 授权、受控取消和查询入口、委托与审计、安全 DTO |
| runtime-service | 需要 | 通用停止请求收敛、inbox 屏障与回执、证据报告、执行资源适配 |
| GraphHarbor 配套库 | 源码与候选已验证，正式发布待完成 | 活动 Run 原子快照、取消意图、固定目标回执、Worker 实际退出确认 |

GraphHarbor 是 Runtime 的依赖，不是新增平台服务。平台不得直接更新其 `runs`、lease 或 checkpoint；Runtime 只能使用引擎正式提供的执行原语。

## 已批准决策

1. 本轮实现“运行取消与中断”非前端范围，不追加模型 fallback、预算、记忆、PR、Slack 等独立项目。
2. 当前已经有前端 Stop、单 Run cancel、`interrupt`、HITL 和 Docker 取消清理。补充的是会话级停止闭环。
3. 用户 Stop 默认停止受理时该 Thread 的工作并取消当时已接受的排队 Run；稍后新提交的动作不属于旧请求目标。
4. `interrupt` 保留 Run/checkpoint，不保证等工具完成；ACK、`interrupted` 状态、Worker 退出和外部副作用停止分别核实。
5. 先交付无模型的证据报告。LLM 润色作为明确后置的可选能力，不在停止链路里重新运行原 Agent。
6. 通用取消在平台与 Runtime 控制层生效，无需每个 Agent 加“停止工具”；仅长工具资源清理与可选业务进度需显式适配。
7. 用户批准已记录在 [人工评审](review.md)。本轮迁移/恢复/重启只针对隔离临时环境，无提交、正式发布、依赖锁升级或现役部署。

## 本轮交付

公开 POST cancel、GET detail/list；持久幂等 Stop、后台租约恢复、固定目标/inbox 屏障、Docker/local 资源证据、确定性报告、精确委托/HMAC 与阶段审计已实现。

唯一post43包版16条真实API→Runtime→Worker/PG/Redis场景、两类Docker取消和7条迁移/恢复通过。Runtime Stop/inbox47 passed/1 skipped；GraphHarbor主回归297 passed/8 skipped、Cron3 passed；API66 passed/376 subtests passed，1条既有无关文案断言失败已HEAD复现。版本矩阵与产物记录见verification.md。

Docker Block已解除。双包源码已准备为唯一post43，四产物/锁步/冷安装/迁移及临时Runtime锁接入完成，SDK保持0.4.3。正式PyPI上传仍需明确发布指令，仓库Runtime仍锁正式post41；未发布候选不能代替正式接入。前端同事按交接报告实施，指定配套环境后联调；现役部署另行授权。

## 关联专项

- [Chat 持久消息队列](../20261005-durable-chat-prompt-queue/README.md)：T4-T6 已标记源码完成，T7 联合验收/本地升级未完成；本项目复用其队列，不重做 FIFO、调序或服务端消费。
- [Runtime 与 GraphHarbor 边界](../20260925-runtime-business-boundary-decoupling/README.md)：业务身份/模型/报告留在 Runtime，执行所有权留在引擎。
- [工具容错](../20261006-agent-tool-error-resilience/README.md)、[运行诊断](../20261006-agent-observability-hardening/README.md)：复用错误出口、追踪和现有组件。
- [v3 与 RunControl 评估](../20261004-langgraph-v3-delta-evaluation/README.md)：本项目不把 `request_drain()` 与 cancel 的 `interrupt` 混用。

## 完成判定

只有必做任务、前端交接实施、真实跨服务验收和回退门禁全部完成，功能才能标记 `done`。可选 LLM 摘要独立标记 `deferred`；生产部署须按指定环境另行授权，不以本轮规划代替批准。

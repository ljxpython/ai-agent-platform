# Agent 运行完成通知与失败回调

## 项目概述

- **启动日期：** 2026-10-09
- **目标：** 补齐所有受管 Agent Run 已确认终态的可靠投递、持久失败摘要和跨会话通知，复用现有错误分类、运行控制和前端在线状态。
- **模板类型：** 标准模板。Runtime、引擎和 API 共同实现一条契约链，不能分别验收为完整能力。
- **改动级别：** 治理改动，包含跨服务契约、可信来源、密钥、持久化和外部引擎配套。
- **状态：** 已完成（`done`）。全范围包括 GraphHarbor post44 双包发布、Runtime 安全终态投影、Platform API 可信来源/HMAC 回调/持久化/通知 feed/已读回执/cron 回填、前端 Pinia 全局通知 Store 单例/双端常驻通知中心/细粒度优先白名单错误码映射/会话执行离开二次确认拦截/历史 Run 安全诊断卡片全部交付；Vitest 722 passed，Playwright + Chromium 端到端真实模型调用与三视口验收全绿（证据截图留存），用户人工验收通过。
- **本轮范围：** P1-P5 全部范围（后端、Runtime、GraphHarbor、Platform Web 前端全栈实装与真实模型自动化/人工联合验收）。未部署现役生产。
- **责任分工：** 当前 AI 执行后端、Runtime 与 GraphHarbor 配套，用户承担治理批准；前端实现由用户的同事负责。
- **估算：** 后端/Runtime/引擎约 10-15 人天，前端约 2-3 人天，联合故障验证约 2-3 人天；评审后校准，不是交付承诺。

## 阅读入口

| 文档 | 用途 |
| --- | --- |
| [整体方案](plan.md) | 推荐架构、替代方案、范围、终态语义与实施顺序 |
| [任务清单](tasks.md) | 唯一进度来源；每项列出改动、文件/函数、结果与验收 |
| [验证计划和记录](verification.md) | 单元、集成、E2E、安全、性能、回滚与真实证据 |
| [人工评审单](review.md) | 用户会话批准 R1-R8 的范围与执行边界 |
| [open-swe 与当前项目对照](01-gap-analysis.md) | 代码证据、同事建议的采纳与纠正 |
| [Runtime 安全原因与接入边界](02-runtime-capabilities.md) | 通用适配、错误白名单与各 Agent 接入 |
| [GraphHarbor 配套交接](03-engine-terminal-delivery.md) | 引擎事务、Outbox、可信回调上下文、版本门禁 |
| [Platform API 契约草案](04-platform-api-contract.md) | 回调、持久化、查询、通知 feed、已读与权限 |
| [前端交接文档](05-frontend-handoff.md) | 同事可以据此实现的 DTO、请求、交互、竞态与验收 |
| [发布与回滚](06-verification-rollout.md) | 灰度、运行指标、保留期、混合版本与回退 |
| [LangGraph Server 官方边界核对](07-langgraph-server-boundary.md) | MCP/OpenAPI/发布包证据、原生 webhook 实现与本期生产增强的区别 |

编号文档是标准模板的支撑材料，不独立维护任务进度。实施细节见 [实施记录](implementation/01-backend-and-runtime.md)。

## 结论先行

1. 当前在线聊天已展示 `error/timeout`；缺的是可靠落库、断连后的失败发现、未打开会话的通知和发送恢复。
2. 借鉴 open-swe 的“统一启动配置、执行现场分类、终态处理、Run 级去重”，不迁移 Slack/GitHub/Linear 等业务渠道。
3. GraphHarbor 对标完整 LangGraph Server，原生 Run/Cron webhook、通用鉴权、配置和扩展属于其边界。推荐“GraphHarbor 原子终态 + 持久 Outbox → Platform API 幂等收件箱 → 当前用户通知 feed”。Runtime 提供安全终态投影和来源关联；引擎可保存通用身份，不硬编码平台项目政策或 provider 文案。
4. Middleware/Tool 可以增加细粒度诊断，不能保证进程被杀、factory 失败、排队超时等场景的终态通知；基础能力必须在所有图共用的执行引擎边界接入。
5. 本期建议使用请求正文 HMAC、数据库唯一约束、重试/死信和当前 ACL；这些可靠增强待评审，不是官方 webhook 已具备的全部保证。只有实现与故障验收后，才可承诺保留期内至少一次投递与幂等投影，不承诺网络上的 exactly-once。
6. 本期提供站内通知；浏览器关闭时先持久化，用户下次进入平台可见。不包含操作系统推送、邮件或第三方渠道。

## 范围与发布前置

涉及 `apps/runtime-service`、`apps/platform-api`、`apps/platform-web`（交接），并依赖外部 `graphharbor`。所有受管 create/stream/Protocol/resume/定时 Run 都必须覆盖；不要求逐个 Agent 写 completion tool。

当前平台依赖锁为 `graphharbor==0.13.0.post44`；GraphHarbor 双包 `0.13.0.post44` 已从 PyPI 独立安装核验。人工批准、前端验收和正式包完整多 Worker 链路齐全之后，才能判定专项 `done`；后端完成不代表全链路完成。

不在本期：渠道适配器、动态 middleware/tool registry、重写已完成的重试/预算/上下文/工具修复能力、补发所有旧历史 Run、配置“成功即弹通知”产品开关。

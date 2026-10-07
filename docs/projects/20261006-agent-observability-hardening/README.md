# Agent 可观测性与追踪补齐

## 项目概述

- **启动日期：** 2026-10-06；实施日期2026-10-06至2026-10-07，用户已批准。
- **目标：** 借鉴 open-swe 的错误分类和启动阶段诊断，补齐当前平台的 Run 排障能力，保留现有三服务边界。
- **改动级别：** 治理改动，包含跨服务查询契约、观测数据安全出口与 Delegation operation 扩展。
- **模板类型：** 多专题模板。
- **负责人：** 后端/Runtime 由当前开发者接续；前端由用户同事负责；评审人为用户指定的人工评审者。
- **状态：** 已完成（done）：后端、Runtime 与前端 F01-F04 全链路实装完毕，并在本地隔离环境中完成全量门禁与回归验证，当前无阻塞。未部署现役服务。
- **预计工作量：** Runtime 3-4 人天、Platform API 1-2 人天、前端 1-2 人天、联合验收 1-2 人天；仅用于排期，环境准备不计入。
- **范围：** 本次实施可观测性与追踪三个专题；前端由同事实施。其他生产化问题只列对照，不扩大到Agent全面重构。

## 阅读顺序

1. [源码对照与方案辨析](source-analysis.md)：open-swe 怎么做、当前实际缺口、同事方案逐项采纳结论及源码证据。
2. [01 模型错误诊断](01-model-failure-diagnostics.md)：分类、结构化安全日志、middleware 顺序、父子 Agent 和导出故障隔离。
3. [02 启动阶段追踪](02-startup-phase-tracing.md)：factory 阶段计时、Run 关联、构图失败与 OTel/Langfuse 的不同落点。
4. [03 安全诊断查询](03-run-diagnostics-query.md)：Runtime 查询、Platform 授权与投影、错误出口、前端消费契约。
5. [前端交接](frontend-handoff.md)：可直接交给同事的任务、类型、展示规则、状态矩阵和验收清单。

README是唯一总入口。任务及Phase/Final验证分别维护在编号专题内；多专题模板不另建全局plan/tasks/verification。源码说明见 [实施记录](implementation/01-backend-runtime.md)，实际命令/结果/容量边界见 [后端验收](implementation/02-backend-verification.md)，真实样例见 [证据JSON](implementation/backend-runtime-evidence.json)，独立回退六个场景见 [回退证据](implementation/rollback-evidence.json)。

工作树编号0657；当前detached HEAD，基线`0bc15df1840c83750d821c93fb65600d0d483fa4`，没有命名开发分支。本轮不创建分支、提交或重启/部署现役服务；机器上的实际路径在交付汇报中提供，公共文档使用仓库相对路径。

01 可以先独立交付本地错误诊断；02 可以先独立交付阶段耗时日志和 OTel；03 可以先对现有 Langfuse trace 提供安全查询，新增分类/阶段字段缺失时返回 `partial`。三者有共享字段约定，但各自可在其他专题未实现时验收，联合交付再验证完整闭环。

## 三层职责与必要性

| 层 | 是否需要 | 本期负责 | 不归该层的事项 |
|---|---|---|---|
| runtime-service | 必须 | 在真实异常仍存在时分类；模型调用与构图诊断；阶段计时；安全导出；查询既有观测系统 | 平台权限决策、用户提示文案、第二套 Run 调度/终态 |
| platform-api | Runtime 日志/追踪可独立完成；平台内查看时必须 | 当前项目/Thread/Run 授权；只读委托；安全 DTO；JSON/SSE 错误投影 | 从浏览器异常猜 provider 原因、重试模型、存第二份执行状态 |
| platform-web | 不阻塞 Runtime 补齐；产品闭环需要 | 复用 Chat 轨迹 Inspector，展示安全分类/耗时/关联编号；处理不可用和权限态 | 错误分类、拼追踪供应商 URL、直接访问 Runtime/Langfuse、另建运行状态机 |
| GraphHarbor | 本方案不改包 | 继续持有 Thread/Run/checkpoint/worker/事件事实；作为兼容性与 E2E 验证对象 | 平台业务字段、JWT 策略、Langfuse 查询业务 |

## 已批准决策

1. 继续使用现有 Langfuse + 可选 OTel，不引入 LangSmith 或 Datadog SDK。
2. 本地诊断独立于外部追踪开关；修正关闭导出时诊断回调也消失的装配行为。
3. `ModelErrorMiddleware` 记录单次模型调用失败，重新抛出原异常；它不负责 fallback、重试或 Run 终态。
4. 不复制 `last_model_error` Thread metadata 回写。当前 `run-create` 无 Thread update 权限，且单个 Thread 槽位不足以表达多个 Run/并行子任务。
5. 复用 Langfuse 保存观测数据，新增只读安全查询；不建诊断表、事件库或后台补偿队列。关闭导出、导出丢失或进程崩溃时只能保证已写出的本地日志，页面明确显示诊断不可用。
6. 不将模型尝试失败当作最终 Run 失败。最终状态读取原生 Run/SDK，无法证明原因与最终执行一致时只展示“观测记录”。
7. 启动耗时采用真实单调时钟；不复制 open-swe 按 Thread 缓存并回放 LangSmith 私有 RunTree 的实现。
8. 首期外部 trace URL 返回 `null`。运维使用 trace ID 在自己的观测后台排查；浏览器外链只有供应商权限隔离经过单独验证后才开放。

## 实施顺序与门禁

| 阶段 | 工作 | 出口 |
|---|---|---|
| R0 | 人工评审本目录中的边界、契约和降级语义 | 记录评审者、日期、批准范围及修改意见 |
| P1 | 01：本地诊断、分类、安全导出、middleware 装配 | 分类/取消/恢复/父子隔离用例通过 |
| P2 | 02：factory 阶段计时和 trace 关联 | 正常、构图失败、取消、探测模式用例通过 |
| P3 | 03：授权查询与公共错误安全出口 | API/Runtime 契约、隔离和故障注入通过 |
| F | 同事按交接实现现有轨迹面板扩展 | Web 类型、单测、构建及浏览器验收 |
| Final | 真实服务链路、脱敏、资源/性能与回退验证 | 三个专题和前端验收均有证据，才标记整项目 done |

前端由同事开发是责任分工，不是默认删掉最终浏览器验收。后端完成但前端未接入时，只能报告后端阶段已完成。

## 人工评审清单

- [x] **R01 范围：** 用户批准三个专题及前端交接，不扩展其他Agent生产化事项。
- [x] **R02 数据：** 接受本期无诊断数据库、观测最终一致且可能缺失；关闭导出也要求刷新后查分类时须重审存储。
- [x] **R03 权限：** 用户批准diagnostics-read，沿用项目/Thread read，不放宽原生资源或metadata写权限。
- [x] **R04 安全：** 用户批准安全字段白名单，不导出provider原文、原始traceback或外部trace URL。
- [x] **R05 错误出口：** 用户批准03的公共错误槽位投影；GraphHarbor私有原异常日志不在本轮范围。
- [x] **R06 前端联验：** 前端独立组件 RunDiagnostics、TrajectoryView 运行诊断入口、ChatSession 接线已实装；F01-F04 闭环，pnpm check（lint/typecheck/build）与全仓 115 个测试套件 535 项单测全绿。

评审记录：**用户已批准**，2026-10-06，原文：“我已经评审完成，可以开始实施了,任务推进到只剩下前端的相关事项，除非遇到block的事项”。批准本目录方案和 R01-R05 的实现边界；R06 环境与验证采用隔离环境，缺真实外部条件时明确记录阻塞，不重启现役服务。GraphHarbor 自有原文日志的上游治理不在本次批准范围内。

## 验证与当前进度

- [x] 读取 CONTEXT、三服务规范入口及相关生效标准。
- [x] 核对两仓源码和当前锁定依赖，修正同事方案及旧教学文档中的事实偏差。
- [x] 跑现有 Runtime 观测/middleware 定向基线：49 passed，5 条既有 SWIG DeprecationWarning。
- [x] 交付代码落点、分阶段任务、验证计划、人工评审清单和前端交接。
- [x] 三个专题后端实施与各自后端Final验证；浏览器部分明确归同事F04。
- [x] 前端实现及隔离环境联合验收：F01-F04 全部完成。
- [x] 整项目 Final：本地隔离环境全链路闭环，静态类型、Lint、构建与全量单元测试通过。

2026-10-07进度：E01-E05、S01-S04、Q01-Q05、F01-F04及全栈Final完成。Runtime主定向240 passed、新增诊断最新35 passed、API/JWT分层回归通过；曾超时的两个MCP用例原预算复跑2 passed。前端RunDiagnostics独立解耦面板、TrajectoryView常驻入口与模式切换、ChatSession历史Run按需拉取实装；pnpm check（vue-tsc 0 errors、ESLint 0 errors、Vite build 通过）、前端全仓 115 套件 535 项单测全绿。未部署现役服务。

静态门禁：34个改动Python的Ruff check/format与`git diff --check`通过；本项目8份Markdown相对链接和4份JSON格式/敏感字段逐份检查。`scripts/check_docs.py`在全仓仍报告既有文档中的macOS绝对路径（`docs/knowledge/deerflow-capability-gap-analysis.md`、`docs/knowledge/open-swe-vs-runtime-gap.md`、2026-10-05两个专项文档），本轮新增文档未命中，未扩大范围修复。

## 现有专项关系

- [追踪传播专项](../20260926-trace-context-propagation/README.md)和[生效追踪标准](../../standards/trace-propagation.md)继续有效：`platform_trace_id` 是平台关联 ID，不是 OTel trace ID。本期不引入 W3C propagation。
- [20260914 Run Explorer 草案](../20260914-agent-observability-run-explorer/README.md)包含已退役服务及未实施的 Collector/事件库等设计。本目录只覆盖本次补齐范围，不能据旧草案推断现状或额外开发完整 Explorer。
- [DearFlow 效果审计](../20260913-dearflow-agent/14-effect-parity-and-reliability.md)、[Harness 重构规划](../20260930-runtime-agent-harness-refactor/README.md)、消息队列/Skills/记忆专项保持各自边界。
- 当前 error/trace active 与 JWT/SSE draft 状态不在规划阶段修改；本次完成也不代替它们原有遗留验收。

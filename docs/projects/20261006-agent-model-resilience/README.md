# Agent 模型调用稳定性治理

## 项目概述

- **启动日期：** 2026-10-06。
- **目标：** 借鉴 open-swe 的模型故障处理，为平台 Agent 补上受管备模型、可分类的有界重试和真实失败终态。
- **负责人：** 用户负责方案评审；后端与 Runtime 后续按批准范围实施；Platform Web 由用户同事实施。
- **模板类型：** 标准模板。配置、执行和验证属于同一条调用链，不拆成独立子专题。
- **改动级别：** 治理改动。涉及跨服务模型连接契约、BYOK 授权边界、流式失败语义和生产运行预算。
- **状态：** 已完成（`done`）：后端/Runtime/Web 全链路与 GraphHarbor post42 默认取消/实际子图已通过；前端 F01/F02 实施与单测（559 passed）完成，修复 FastAPI 500 与表单 step 缺陷；故障注入主备降级实测通过，经用户在浏览器真实测试验收合格。
- **预计工作量：** 已完成验收。

## 阅读顺序

1. [源码对照与建议评估](reference-analysis.md)：open-swe 实际怎么做、当前项目有什么、哪些建议不能直接照搬。
2. [整体方案](plan.md)：服务分工、配置和内部契约、重试边界、具体代码位置、灰度与回退。
3. [任务拆分](tasks.md)：规划完成项与后续开发任务，明确负责人和验收条件。
4. [验证计划与基线](verification.md)：本轮真实执行结果、后续故障注入、完整链路和回退门禁。
5. [前端交接](frontend-handoff.md)：2026-10-07 开发任务书；五字段表单、逐文件差距、平台取消响应映射、停止 12 项验收和联调分工，交由同事实装。

真实改动记录在 [implementation](implementation/01-managed-model-resilience.md)，脱敏链路证据在 `evidence/`；项目进度以 `tasks.md` 为准。

用户已确认沉淀取消经验，平台记录在 [跨服务经验库](../../lessons/cross-service.md)，GraphHarbor 记录在其仓库 `docs/lessons/runtime-persistence.md`。本轮只补交接/经验文档，F01/F02/V02/V03 保持未完成。

## 本期范围

| 层级 | 是否需要开发 | 本期责任 |
|---|---|---|
| Platform Web | 需要少量配套，由同事开发 | Agent 编辑页配置、既有聊天失败态适配、验证实际模型展示；不承担模型重试 |
| Platform API | 需要 | 配置持久化、候选模型授权、受管连接与策略快照、所有 Run 入口统一组装、审计 |
| Runtime Service | 需要，是核心 | transient 分类、受控 retry/fallback、timeout 与取消、流式安全、父/子 Agent 装配和观测 |
| GraphHarbor / SDK | 独立专项修复，平台联验 | 通用取消传播、Worker 停止确认和 `wait` 语义在 GraphHarbor 仓库实施；本项目不修改 site-packages，不向依赖加入模型业务策略 |

本期聚焦用户提出的第 1 项「模型调用稳定性」。其他 Agent 能力仅用于核对现有基础，不扩展为沙箱、记忆、计费、全局熔断或 Harness 重构项目。

## 关键决策建议

1. 优先复用已锁定的 LangChain `ModelRetryMiddleware`、`ModelFallbackMiddleware` 和现有 `ModelCallTimeoutMiddleware`；补充平台必需的策略保护，不复制 open-swe 整套中间件体系。
2. 备模型使用当前项目可用的 Catalog UUID，经同样的 BYOK/项目授权和 opaque reference 兑换；不通过全局 `AGENT_FALLBACK_MODEL_ID` 绕开平台治理。
3. 模型重试只包围一次推理，不能重跑整个 Agent、工具或 Run。候选重试共享物理调用次数和时间预算。
4. Runtime 配置/权限检查和 Deep Agents 原生摘要在可靠性策略外侧，单次 timeout 在内侧。把 fallback 放在 timeout 之后会使其捕获不到外层 timeout；保留摘要的 ContextOverflow 恢复路径。
5. 已产生正文、reasoning 或 tool-call 内容的流式调用，本期不自动重新生成或拼接另一模型的输出。
6. 重试耗尽使用脱敏的稳定 Runtime 错误，让原生 Run 进入真实失败状态；不返回故障 `AIMessage` 伪装成功。
7. 先以默认关闭的配置灰度；前端未交付时可通过已批准的管理 API 验收后端，不能把后端通过记成全项目完成。
8. 主/子生成实例关闭 SDK retry；摘要和记忆提取使用共享主连接的辅助实例保留既有设置。N/total 按受管 invocation，不等于整个 model 节点或全 Run 请求预算；实际 general-purpose 必须显式核对/装配。
9. 2026-10-07 用户确认采用 Redis 持久控制标记 + 即时通知 + Worker 停止确认。`wait=false` 仅受理，`wait=true` 等实际执行退出；1 秒心跳不作为根因修复，前端不增加取消策略配置。详见 [取消传播决策](plan.md#取消传播决策2026-10-07)。

## 人工评审入口

2026-10-06 用户明确「不需要精简，我们就按照原方案来推进吧，可以开始实施了」，批准以下原方案议题，详见 `plan.md` 评审表。前端继续由同事开发，发布/提交未获授权。

- **R01：** 候选模型的项目隔离，以及当前 Delegation 模型名单与 BYOK 作用域差异如何收敛。
- **R02：** 真实失败终态、流式已输出后的终止行为，以及 Worker 对原始 timeout 的整 Run 重试风险。
- **R03：** 支持的模型组合、跨协议历史消息兼容、模型选择覆盖和辅助推理的范围。
- **R04：** 重试次数、单次/总预算与 SDK 重试归属。
- **R05：** 采用现有 JSON 保存管理配置和提交快照，以及混合版本发布、回退要求。

## 本轮交付证据

- 核对本仓库、用户提供的 open-swe 检出源码及锁定依赖；证据入口见 [对照文档](reference-analysis.md)。
- Runtime 既有相关测试：**37 passed**，包含模型构造、timeout、参考 Agent 组合与重试耗尽行为。
- Platform API 既有相关测试：**11 passed，8 subtests passed**，包含 model reference、BYOK 生命周期与 Agent 存储/契约。
- 新策略后端/Runtime 已实现；基线之外的真实证据、失败出口与限制见 `verification.md` Phase 记录。前端浏览器、现役部署、完整回退门禁仍未完成，不能形成 Final done。
- 旧默认取消 ACK 后访问备用、释放延迟 7.925 秒与 1 秒心跳对照 0.705 秒保留为基线。post42 默认 heartbeat 复验 ACK/停止确认/最终都只有 primary，ACK→释放 0.123 秒；实际子图 9 项清理 barrier 与候选数不增长通过，V01-C 已完成。双包发布由 GraphHarbor 专项管理，现役服务未升级。

## GraphHarbor 协作入口

GraphHarbor 仓库根目录下 `docs/projects/20261007-worker-cancel-propagation/README.md` 为通用 Worker 项目入口，`tasks.md` 为跨包进度事实源，`verification.md` 管理官方 SDK、故障和回退门禁。平台仍负责模型调用计数、实际子图和同事前端验收；两边 Phase 通过均不能代替本项目 Final。

GraphHarbor取消专项done：post42双包四产物已直接发布PyPI，哈希/独立安装/CLI及专项Final通过；发布包两版Python SDK矩阵各24项、回退/kill/混合12项通过。现役仍post41，平台依赖锁定/升级须等完整平台门禁，不因包发布改为已上线。

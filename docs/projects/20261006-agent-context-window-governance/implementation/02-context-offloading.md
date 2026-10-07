# 上下文整理、维护 Run 与公共出口

实施日期：2026-10-06 至 2026-10-07。对应 R01/R02/R03、B03/B04/B05、V01；进度以 tasks.md 为准。

## Runtime

- `apps/runtime-service/src/runtime_service/middlewares/conversation_offloading.py` 的 `ConversationOffloadingMiddleware` 继承锁定版官方摘要，并用相同 `name` 替换默认组件。不复制摘要循环、cutoff、消息 reducer 或 checkpoint 实现。
- 输入预算为可信容量扣除输出预算及安全余量；`ContextBudgetMiddleware.awrap_model_call()` 检查最终 system/messages/tools，含动态记忆、技能和工具装配。未整理时通过官方 overflow fallback 一次，整理后仍超预算明确失败。
- 锁定 OpenAI/DeepSeek SDK 的 `BadRequestError.code=context_length_exceeded` 由同一最终 guard 精确转换为 `ContextOverflowError`；不匹配异常文本、不接管其他 400，压缩后再次超限立即明确失败。受控 HTTP 400 后使用真实 provider 完成摘要与回答，验证 SDK→guard→官方 fallback 的链路。
- 摘要模型是当前授权模型的副本，添加 `nostream`/`langsmith:hidden`，复用超时和 usage callback。完整 Prompt 在调用前再次核对预算。大批历史需要裁剪时保留最早用户目标或上一轮摘要，剩余内容复用官方裁剪器，避免再次整理遗忘早期约束。
- 归档和媒体失败不允许成功摘要带失效指针；取消会取消并等待并发归档任务。成功 command 写有界终态，失败仅发安全 custom 并由 Run 终态核实。
- `OffloadingState` 继承 `DeepAgentState`，保留官方 DeltaChannel。整理状态标记 `PrivateStateAttr`，使 DeepAgents 不把根状态复制给子图，也不把子图状态合并到根；API 按白名单公开 Thread 状态，custom 使用框架 namespace。
- DearFlow/Showcase 的 `agent.py::get_agent()` 是装配入口，根图与声明式子图同策略。schema-only 图也声明同一状态 channel，但不创建执行资源；run_id 沿既有 MessageQueue 范式从 `execution_info` 回退到可信 config metadata。
- 手动模式通过 `abefore_model()`、空 handler 和 `jump_to=end` 结束。组合根跳过 MCP/Memory/Workspace 执行资源准备，skills/queue/memory 的前后处理守卫和 `MaintenanceSafeToolCallsMiddleware` 防止维护改写普通历史或产生业务副作用。
- `messaging/inbox.py` 拒绝维护 Run 的 queued/claimed 接入；既有 FIFO 和 GraphHarbor 并发裁决保持事实源。
- `.env.example` 默认 `AGENT_CONTEXT_MANAGEMENT_ENABLED=0`。开启前要求迁移、模型容量/输出预算和双端 Context 契约已就绪。

## Platform API

- `core/runtime_contract.py`、Runtime `contracts.py/resolver.py` 和 `core/security/tokens.py` 同步 `runtime-context/v5`。`offload_conversation` 严格布尔；省略/false 同 hash，true 仅表示本次维护，不能关闭自动整理。
- `runtime_gateway/application/service.py::_preflight_conversation_offload()` 在现有 runs、runs/stream、commands 共用入口校验当前 Thread/graph/comment ACL、空 input、最新根 checkpoint、能力、活动 Run、审批/澄清、待发消息。pending 状态不可确认时拒绝，最终竞争由 GraphHarbor 原子 reject。
- 复用 `run_requests` 和 `Idempotency-Key`，不新增维护表或执行锁。已接受 Run 重放复用原 run_id；关联审计补 `maintenance_type=conversation_offloading`。
- 已保存的 v4 审批快照经当前权限重新核验、确定性归一后签发 v5；旧 cron 定义同理，禁止借迁移开启维护。新客户端没有双版本旁路，cron/queue/resume 不能带 true。
- `adapters/langgraph/sdk_client.py::redact_runtime_private_fields()` 白名单整理状态，过滤私有摘要/session 与 checkpoint 归档文件。CompositeBackend 会去掉 `/conversation_history/` 前缀，所以同时识别 `/session_<32hex>.md` 和 `/media/<16hex>.<ext>`；普通成果文件继续公开。输入与 state update 拒绝注入私有字段/归档文件。
- 现有 capabilities 增加 `conversation_offloading`，结合当前 comment ACL；标准 Run 默认 stream modes 增加 custom。普通参数 schema 白名单不开放维护标志。
- 新增 async 网关数据库读取复用 `run_in_threadpool`，不阻塞事件循环。

## 验证与修正

测试保持现有 pytest/unittest 范式；新增 middleware、网关、迁移、PG、真实模型与 HTTP 专项测试。真实 Worker 的 schema-only 读取最初丢终态，已以根图显式 state_schema 修正；并行子图会合并普通状态，已采用官方 PrivateStateAttr 修正并验证两份归档独立。

质量探针后来补测“大批历史再整理”复现官方 strategy=last 裁掉上一轮摘要，薄扩展现在保留 lead 并仍核对最终摘要 Prompt。真实测试检查多次整理后的回答锚点，不仅检查 Run success。

结果与失败记录均在 [verification.md](../verification.md)。前端代码本轮未修改；交接见 [frontend-handoff.md](../frontend-handoff.md)。未提交、未部署现役平台、未变更锁定依赖或 GraphHarbor。

# P3 子 Agent 展示与观测实施记录

用户已批准实施 P3。入口为 [P3 执行包](../phases/P3-子%20Agent%20展示与观测.md)，本记录逐项更新代码与证据。当前 partial：后端代码与组合回归完成，真实完整成功运行和外部观测尚未通过；前端明确 deferred。

## 范围与起点

- 复用普通同步 research 子图、已有队列／父 Run 取消、官方 namespace 和回调；独立 child 控制与用量账本仍后置。
- 用户已再次确认“仍只做后端，前端保留交接”。本轮不修改前端，F3 deferred；后端必要测试完成后单独标记 done，不将整阶段含前端标为全部完成。
- P2 真实研究闭环成功，但重复运行存在 Redis／Worker 超时；P3 真实平台验证需继续检查，不能沿用旧证据直接勾选。

## 已发现问题及处理

1. 已修复：`apps/runtime-service/src/runtime_service/observability/langfuse.py:_TRUSTED_METADATA` 未包含 Dear 传入的 execution_mode／effective_reasoning／skills_hash／policy_hash，导致装配记录在公共边界被丢弃。已补受信白名单并验证普通 metadata 不能伪造。
2. `apps/platform-web/src/modules/dear-agent/components/SubagentCard.vue` 按角色名称兜底匹配，并在缺少 discovery 时猜测 namespace；同角色并发需用真实官方事件验证后修复。

## 验证

- `apps/runtime-service/tests/services/dearflow_agent/test_subagents.py` 新增确定性模型驱动真实 Deep Agents 图：两个同角色并发、父输入隔离、子消息／usage 独立 namespace、父回调关联、取消传播且无假成功回执。
- `apps/runtime-service/tests/observability/test_langfuse.py:test_dear_assembly_metadata_requires_trusted_boundary` 与上述测试合跑：**3 passed、24 deselected，81.06s**。命令：Runtime 目录 `.venv/bin/python -m pytest -q tests/services/dearflow_agent/test_subagents.py tests/observability/test_langfuse.py -k 'parallel_children or dear_assembly' --tb=short`。这是组合测试，模型为确定性替身，不冒充真实模型／平台部署。
- 已修改公共 `observability/langfuse.py` 的受信字段白名单；普通 metadata 仍不能注入这些字段。其余观测及真实部署验证继续进行。
- `test_research.py` 扩展 Ultra 子角色禁止 execute／write_file／再次 task 的参数化回归。
- `test_platform.py` 在已有测试入口增加 `DEAR_PLATFORM_SUBAGENT_TEST=1`（Ultra 两个同角色 task、根消息隔离、checkpoint 回读）；`DEAR_PLATFORM_CANCEL_CHILDREN=1` 另验父 Run 取消。没有新增生产探针 Graph 或模型后门。

## 本轮追加证据

- 子角色 execute／write_file／再次 task 拒绝，以及观测白名单、调用方身份不能注入、并发元数据隔离：**7 passed、31 deselected，124.27s**。Runtime 执行 `.venv/bin/python -m pytest -q tests/services/dearflow_agent/test_research.py tests/observability/test_langfuse.py -k 'ultra_uses or binding or untrusted_identity or dear_assembly or concurrent_runs' --tb=short`。
- 子图来源与父取消组合：**2 passed，91.50s**。两个子图使用相同 `same-inner-call`，来源按不同 namespace 区分、线程相同；模型 usage 保留在各自消息中。此后增加 native v3 与 GraphHarbor 适配器测试，待最新结果。
- 首条真实双子任务：project `1b388510-16a8-41aa-8d6c-fb6ddf2946e6`／thread `6e1b5c20-6403-4b65-b6bb-334f9ffe47c1`／run `88e5dd0e-0154-41dc-b60f-347509f5be98`；两个 task 均返回成功的 ALPHA／BETA，父 Run 最终 timeout。测试 **失败，333.34s**，不能标为端到端通过。
- 真实父取消：project `8dc7cc55-479f-4b2c-8ed2-e6c0d64e7b16`／thread `f21da1c8-a737-4691-92fc-495555a9359b`／run `e8c52cff-ee08-4c87-b631-ce135fa90294`；观察到两个 task 后调用既有父 Run cancel，持续查询直到真实 interrupted。**1 passed、1 deselected，138.14s**。命令：`DEAR_PLATFORM_TEST=1 DEAR_PLATFORM_SUBAGENT_TEST=1 DEAR_PLATFORM_CANCEL_CHILDREN=1 .venv/bin/python -m pytest -q tests/services/dearflow_agent/test_platform.py -k creates_and_completes --tb=short -s`。ACK 未被当作取消完成。

## 事件兼容边界

锁版本 LangGraph v3 的子图 lifecycle 外层 `params.namespace` 可以为空，真实子图 scope 位于 `params.data.namespace`，分派关联位于 `params.data.cause.tool_call_id`。初版测试误读外层，已按真实协议修正。

锁版本 GraphHarbor `langgraph_runtime_pg/graph_executor.py:invoke_graph` 过滤外层 namespace 为空的 lifecycle，因此不能承诺上述 lifecycle 关联已经穿透到前端。实测没有独立 tasks wire 事件；已有 debug task 的 `data.payload.input` 是调用列表（不是 `input.tool_call`），列表内 `id` 对应分派 ID，`data.payload.id` 对应子 namespace 的 `tools:<执行任务 ID>`。回归按这一真实数据结构验证。没有增加私有事件或修改 site-packages；SDK／浏览器消费者接入留 F3，缺少映射时必须降级为未知。

## 修改文件与排查入口

| 文件（仓库根相对路径） | 本轮具体改动／排查目标 |
|---|---|
| `apps/runtime-service/src/runtime_service/observability/langfuse.py` | `_TRUSTED_METADATA` 增加4个受信装配字段；P3 唯一生产代码修复 |
| `apps/runtime-service/tests/observability/test_langfuse.py` | `test_dear_assembly_metadata_requires_trusted_boundary` 验证普通 metadata 不得注入、受信字段保留 |
| `apps/runtime-service/tests/services/dearflow_agent/test_subagents.py` | 真实图＋确定性模型验证双子图并发、输入隔离、来源 namespace、usage、取消和 native／GraphHarbor 事件关联 |
| `apps/runtime-service/tests/services/dearflow_agent/test_research.py` | `test_ultra_uses_restricted_child_and_pro_cannot_delegate` 增加 execute／write_file／再委派拒绝回归 |
| `apps/runtime-service/tests/services/dearflow_agent/test_platform.py` | 既有真实平台测试增加 Ultra 双 task／父取消入口、最终结果与 checkpoint 回读断言 |

复用但未改：`apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py`、`subagents/researcher.py`、`middleware/delegation.py`、`tools/search.py`、`workspace/backend.py`。只读子图共用线程资料目录，来源用 namespace 区分；未新增子任务目录、数据库表或执行器。

## 真实部署失败记录

短任务复测仍失败：project `80a25110-d523-4285-acd8-3892cafb89b7`／thread `2f1422fa-a4af-4f13-9740-fe1d1381acfd`／run `f13d1a27-cbc4-4d39-a746-262f21fcecc4`，**timeout，346.43s**。Worker 日志为 `production_worker.py:529 RunTimedOut: graphharbor.run_timeout`，300秒限制保持不变。该记录不能证明模型或 Redis 是本次根因；历史 Redis 错误与 Langfuse 导出超时仅作为并存现象。成功双子任务完整链路尚需补齐，禁止用取消通过替代成功链路。

## 2026-09-15 收口验证（执行人：Codex）

- Runtime 目录执行 `.venv/bin/python -m pytest -q tests/services/dearflow_agent/test_subagents.py tests/services/dearflow_agent/test_research.py tests/observability/test_langfuse.py --tb=short`：**39 passed、1 skipped，168.66s**。跳过的是 opt-in Tavily 真实调用，不计通过。native v3 和 GraphHarbor debug 的真实 namespace 关联均已通过。保留依赖的 SWIG、Context 序列化及 v3 beta 警告。
- `uvx --offline ruff check --select F` 检查上表5个修改的 Python 文件：通过。仅声明执行过的 F 规则，不冒称完整类型检查或全仓库 lint。
- 最新平台复测：`DEAR_PLATFORM_TEST=1 DEAR_PLATFORM_SUBAGENT_TEST=1 .venv/bin/python -m pytest -q tests/services/dearflow_agent/test_platform.py -k creates_and_completes --tb=short -s`，**1 failed、1 deselected，324.94s**。project `c23027df-033b-4232-a490-d5857b0f3440`／thread `a195d61a-6c83-4d75-98c5-6d546472791d`／run `aea09889-f4f1-402c-9f85-4851e67865e2`。终态 timeout，不能勾选完整成功验收。
- 对上述 Run 只读查询 `runtime_events`：194条持久事件，包含2条 tools、71条 debug、63条 messages；子消息确实带独立 `tools:<执行任务 ID>` namespace。开始生命周期为00:12:03，task工具事件到00:15:38才持久化，00:17:06终态超时。仅证明本次事件时间线和真实子图 scope，不据此直接归因模型或数据库。
- 进一步对照 debug 的 `data.timestamp` 与数据库 `created_at`：子图 `tools:f5a42289-837e-d03b-4955-9859141cb401` 的 model task 在00:15:42.728生成，00:17:02.240才持久化，约79.5秒滞后；另一个子图 model task 约58秒滞后。注意外层 `params.timestamp` 是转换时间，不能代替原始 debug 产生时间。已确认事件消费／持久化链路存在显著积压，仍未量化各段贡献。
- 依赖排查落点（相对 `apps/runtime-service/.venv/lib/python3.13/site-packages/`）：`langgraph_runtime_pg/production_worker.py:on_event` 每条事件先 `_cancel_requested`（Redis＋DB），再 `_publish_event`（DB＋Redis fanout）；`graph_executor.py:invoke_graph` 顺序等待 on_event。应在 GraphHarbor 上游量化这些环节后修复并发布锁版本，当前项目不修改 site-packages，不削掉事件或放宽300秒限制掩盖问题。
- 仓库根执行 `python3 scripts/check_docs.py` 和 `git diff --check`：均通过。

### 四态与剩余工作

| 项目 | 状态 | 证据／剩余内容 |
|---|---|---|
| 同角色并发、父输入隔离、来源和消息归属 | done | 真实图组合、原生与部署适配器关联通过；未要求独立进程隔离 |
| 子图只读权限、受信追踪字段修复 | done | 禁止 execute／write_file／task；普通 metadata 无法注入，39项回归包含全部相关测试 |
| 父取消 | done（后端最小链路） | 平台返回实际 interrupted，组合取消传播到两个执行中的模型；浏览器竞态另验 |
| 完整成功与历史恢复 | partial | 已有组合成功；真实平台本轮3次 timeout，不能只凭部分 task 回执宣称完成 |
| 外部 tracing 导出 | blocked | 本机 Langfuse ReadTimeout；callback关联已验，外部可查询父子span仍缺证据 |
| F3 前端 | deferred | 用户明确只交接；字段、兼容降级、取消和用量验收列入 frontend-handoff.md |
| 独立 child Run／取消／用量账本／结构化结果框架 | deferred | 沿用已批准范围，不新增运行管理或计费系统 |

下一步从同一 P3 执行包接续：定位真实 Run 的模型、事件发布和持久化耗时，解决或恢复环境后重跑上述成功链路；外部 Langfuse 恢复后核对同一 Run 的 trace。后端权限和并发功能不重做，前端另行安排。此次无数据库迁移、无依赖升级、无前端代码修改、无提交／推送。

## 2026-09-15 GraphHarbor 通用优化

经用户确认后，优化范围扩展到 GraphHarbor 通用 Server，但不带入 DearFlow 业务逻辑。

- 修改 `/Users/lijiaxin/PyCharmMiscProject/graphharbor/libs/langgraph-runtime-pg/src/langgraph_runtime_pg/run_store.py:record_event`：事件序列号优先使用已加行锁的 `thread.event_seq`／`run.event_seq`，避免每条事件扫描 `MAX(runtime_events.sequence)`；仅在游标为0时执行一次旧数据修复查询，保持迁移前数据兼容。
- GraphHarbor 原有 `_publish_event`、取消检查、事件 envelope 和业务边界均未改变；没有添加 DearFlow、租户、技能或 Agent 专属字段。
- GraphHarbor Worker 观测测试 `libs/langgraph-runtime-pg/tests/test_observability.py -k worker`：**2 passed**。数据库合同测试因本机默认 PostgreSQL 角色 `postgres` 不存在而 blocked；代码保留 `test_record_event_repairs_stale_sequence_counters` 的旧游标修复语义，待 GraphHarbor 测试数据库可用后重跑。
- 该优化尚未发布到当前运行中的 Worker；需在 GraphHarbor 仓库完成其自身测试、构建和发布，再重启 Runtime Worker，随后重跑 DearFlow 双子任务成功链路。不能把源码修改当成线上性能修复已生效。

### 后续验证进展

- GraphHarbor `test_observability.py` 全部 **4 passed**；Ruff 对 `run_store.py` 和观测测试检查通过。
- SDK 合同测试仍被同一数据库前置条件阻塞：默认连接 `postgresql://postgres@localhost:5432/langgraph`，本机 `postgres` 角色不存在；没有为绕过错误而修改角色权限或使用业务数据库跑会清表的测试。
- 已尝试构建 `graphharbor-runtime` 工作区包；发布与本地 Worker 替换仍以 PostgreSQL 合同测试通过为前提，不把构建成功替代运行正确性验证。

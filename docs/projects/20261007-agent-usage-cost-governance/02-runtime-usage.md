# Runtime 用量采集与持久化

## 目标

提供与业务 Agent 无关的模型调用采集能力，覆盖主图、子图、摘要和可归属的 Tool 内模型调用。复用官方 callback/usage API，支持 `create_agent`、`create_deep_agent` 和普通 `StateGraph`；不修改 Agent 循环，不由 LLM 自主决定是否记录费用。

## 方案设计

### 1. 两种适配方式，一条记录路径

- 已接线图：在现有 `with_langfuse_tracing()` 内装配 Usage callback，独立于 Langfuse/OTel 开关；无需为每个 graph 重写采集逻辑。
- 新图或自定义 Tool/Middleware：复用新增 `with_runtime_usage(graph, config, trusted_metadata=...)`；图级一次装配。Tool 内另起模型调用且无法继承时，显式传入同一个可信采集 callback，并声明用途。
- 已有传递链出现相同 callback 时按实例去重。模型层提供模型身份和价格快照，不再挂第二个计数 callback。
- 普通无平台身份的本地 Agent 仍能使用官方 `UsageMetadataCallbackHandler` 做临时统计；没有可信租户、Thread/native Run 时，不写平台用量表。
- 不引入专用 `record_run_usage.py` Middleware、采集 Tool、Builder、消息队列或新的第三方 SDK。若后续某 Agent 的模型执行不产生官方 callbacks，由该 Agent 的 Tool/adapter 调用同一标准记录函数，并单独验收。

现有标准 callback 只能按 `model_name` 做进程内聚合，不能独立满足 native Run 关联、模型目录 UUID、缺失覆盖率和持久化。本期复用它的 generation/message 读取方式、`UsageMetadata` 与 `add_usage`，只补这些当前需求。

### 2. ID、模型和调用范围

| 字段 | 来源及规则 |
|---|---|
| `tenant_id/project_id/graph_id` | 工厂已经验证的 Delegation facts；不从消息或任意客户端 metadata 取 |
| `thread_id/run_id` | 现有工厂/GraphHarbor Worker 传入的 native UUID；不使用 callback UUID 代替 |
| `model_call_id` | `on_chat_model_start/on_llm_end/on_llm_error` 的 callback `run_id` |
| `parent_call_id/namespace` | 官方 callback parent ID 与 `langgraph_checkpoint_ns`，仅保留名称段 |
| `model_id` | 实际调用模型的 catalog UUID；不同模型不借用主模型价格 |
| `provider/model_name` | `build_model()` 经可信内部连接解析的 provider/requested model；响应模型名作为可选独立事实，不解析 endpoint/key |
| `purpose` | `agent/summarization/memory_extraction/vision/other`；用途不改变权限 |
| `scope` | `primary/subagent/auxiliary`；子图仍归父 native Run |

模型连接的安全 `pricing` 快照写入独立模型元数据，而不是 `.with_config()` 包装成不再支持 `bind_tools` 的新 Runnable。保持 `build_model() -> BaseChatModel` 契约，修改构造 kwargs 或 model.metadata，不保存连接字典。Callback 在 model start 获取安全元数据，在 end 使用相同调用上下文。

同一用户提交的 HTTP 重试、SSE join/replay、重复 end 回调不得新增费用；实际再次执行模型、SDK 可见重试或 GraphHarbor 恢复后的新调用必须新增。HITL resume 使用实际 native Run ID；同一 Run 内注入多个 HumanMessage 仍聚合在同 Run。Fork 不复制旧调用记录，rollback 不抹掉已发生费用。

### 3. 规范化与费用口径

提取优先级：最终 `AIMessage.usage_metadata` → 已知 `response_metadata.token_usage/usage` → `LLMResult.llm_output.token_usage`。同一次调用只选一份来源，不叠加；streaming 用最终 assembled generation，不逐 chunk 计数。错误时检查 `on_llm_error(..., response=...)` 中确实存在的 usage，其余保持未知。

| 事实 | 规则 |
|---|---|
| input/output | 非负整数，拒绝 bool、负数、溢出；缺失为 null |
| total | 标准定义为 input + output；两者齐全才可派生，来源标记 `derived_from_reported`；与 provider total 冲突则 partial，不悄悄截断 |
| cache_read | 标准 `input_token_details.cache_read`，支持经过测试的 cached_tokens/DeepSeek cache-hit 别名 |
| cache_creation | 公共 `cache_creation_tokens` 表示写入总量；5m/1h 是子项。计价时选择普通写入或 TTL 分桶，不能将总量与子项相加；二者冲突为 invalid，TTL 不完整无法分桶则成本 unknown |
| reasoning | `output_token_details.reasoning`，属于 output 子集，不重复计价 |
| input/output details | 只保留经过验证的数字白名单：cache、TTL、reasoning、audio/image/text 等；不保存原始 provider payload |
| 缺缓存字段 | 仅在 provider adapter 能证明“不存在”时为 0，否则 null/unknown，不猜 |
| 无 usage | 记录发生过调用，数量为 null，不把缺失计为免费 |

LangChain 的 Anthropic adapter 已把原始非缓存 input、cache read/write 合成标准 input；再次加缓存会重复。该 adapter 可能将 generic cache_creation 置 0，而只留下 `ephemeral_5m_input_tokens/ephemeral_1h_input_tokens`。经过该 adapter fixture 证明的 0 占位优先采用 TTL 和派生写入总量，不当作矛盾；其他非零总量与 TTL 明细冲突仍需报 invalid，不能普遍忽略冲突。

统一为互斥桶：

```text
I = 标准 input（已含缓存）
R = cache_read
W = cache_creation_tokens（写入总量）
U = I - R - W
W_generic = W（无 TTL 明细时），或 0（完整 TTL 明细且 W5 + W1 = W 时）
C = (U*P_input + R*P_read + W_generic*P_write
     + W5*P_write_5m + W1*P_write_1h + O*P_output) / 1_000_000
```

校验 `R + W <= I`、`reasoning <= O`。越界标记 `invalid_usage`，不以 max(..., 0) 隐藏错误。只需实际非零桶的对应费率；零价是明确配置的免费费率，空价不是零。TTL 缺价、模型身份不明、不同多模态价格或非线性阶梯无法解释时，保留 Token、费用为 unknown。金额超出 NUMERIC(28,12) 范围时只标记成本 unknown/overflow，Token 事实仍能保存。价格来源与精度见 [03](03-platform-cost-contract.md)。

用量原始计数为 reported/derived；成本一律 `estimated`。SDK 隐藏重试、调用后 SIGKILL、供应商未报告的消费无法精确补账，本期不是账单系统。

### 4. 最小持久化结构

采用两个有明确用途的 Runtime 自有表；第二张不是重复总账，第一张只证明采集覆盖，不复制原生 Run 状态。

| 表 | 必要字段 |
|---|---|
| `runtime_usage_runs` | tenant/project/thread/graph、native run UUID 主键、schema_version、collection_started_at/ended_at、degraded 标记、excluded_operations；不存原生 `run_status` 或 Token 合计 |
| `runtime_usage_calls` | scope/native run、model_call UUID、parent_call、model identity、purpose/namespace、tokens/detail 数字、usage_source、call_outcome、usage_quality、完整 pricing_snapshot/version、estimated_cost_usd NUMERIC(28,12)、cost_reason、started_at/ended_at |

唯一键采用 `(tenant_id, project_id, run_id, model_call_id)`，关联 Run 的外键/约束也带一致作用域；索引覆盖 `(tenant_id, project_id, thread_id, run_id)` 和明细分页 `(run_id, started_at, model_call_id)`。不存在同名模型共用价格或进程内累计 thread_total。

需要 Run 采集表的原因：它能区分确认零调用、旧 Run 未采集、采集开始后崩溃；仅有 calls 表无法区分这些状态。不存另一份 success/error/cancelled 终态。

### 5. Callback 生命周期与故障

使用官方 `AsyncCallbackHandler`，按一次 graph execution 创建实例；不把带当前 Run 的 callback 放全局。

1. root graph start：登记采集 Run；跟踪该 root callback ID，子图结束不能关闭父采集。
2. model start：写带 ID/模型快照的调用占位，数量为 null；每次写是完整短事务。
3. model end/error：用同一 ID 补齐真实数量和观察结果；冲突更新采用“补齐事实”，不执行 `tokens +=`。
4. root end/error：标记采集 ended/degraded；不改 GraphHarbor Run 终态。已经登记的调用若因取消/收尾出现迟到回调，仍可按原 ID 补写，不覆盖其他 Run。
5. querying：native running 为 provisional；native 已终止但采集 ended 缺失、调用占位未完成或 persistence 曾失败，则 partial。没有 manifest 为 not_recorded；确认 ended 且零调用才为真实 0。重新进入同一 native Run 的执行先重置采集 ended；调用去重键保持不变，新 callback ID 仍新增调用。

同步 psycopg 访问按当前项目模式使用 `asyncio.to_thread()`，在一个线程内创建/使用/关闭连接。连接、statement/lock timeout 必须有界；不在 callback 中重试数十秒、不使用 fire-and-forget task。本期每 call 一次 start + 一次 end 事务，记录实际开销，测得瓶颈后才评审批量队列。

写失败只输出安全错误码、计数和已授权关联 ID，保留原异常/取消。恢复可用时标记 manifest degraded；持续故障无法写下标记时查询仍可能 not_recorded，不能保证自动补偿。已落库调用的 token 不因 schema/观测故障丢失；原始日志只作排障，不承诺从日志回灌。

当前 memory 在 `aafter_agent` 内 await 提取模型，不是 detached 后台工作；保持现有执行方式。首期只支持受图生命周期管理的调用，不新增后台任务/计费队列；二开 Agent 自行在 root 结束后才启动模型时，必须先解决调用生命周期和可信父 Run 归属，不能宣称本期自动覆盖。

首期保留建议：不新增定时清理、历史回填或跨库级联；用量行和价格快照随 Runtime 数据备份保留，Thread/Run 删除后不再经授权 API 暴露。若 native Run 被删除但 Thread 保留，Thread 合计仍包含已经发生的已采集调用，Run 明细接口按原生归属校验返回 404。按期物理删除需另行明确保留天数与备份规则，G0 人工评审确认后才实施；不将 HTTP 90 天查询窗口当成数据保留期。

### 6. 接线清单

| 调用路径 | 本期措施 |
|---|---|
| Showcase/Reference/DearFlow/backend/mcp/deep-agent/workflow 的 tracing 组合根 | 在公共 helper 接入一次；schema-only 只构图不建采集记录 |
| DeepAgents child/summarization | callback 继承；按真实 namespace/purpose 标记，用组合测试证明覆盖 |
| `MemoryContextMiddleware.aafter_agent` | 当前 await 提取模型显式接入可信 Run 和采集 callback；保留 hidden/no-stream 和执行方式，不导出正文 |
| `build_image_tools().analyze_image` | 当前 Tool 有父 Run 时显式接入；VISION 环境模型无 catalog 映射时 Token 记录、成本未知，不能借主图价格 |
| HTTP suggestions/title | 无 native Run，首期排除；DTO 的 excluded_operations 声明 |
| images generate/edit、search/MCP | 不是标准 LLM Token 调用，排除供应商费用；Tool 自己发 LLM 时需显式适配 |

### 7. 代码落点与公共契约

路径均相对仓库根；新符号为规划命名，现有符号必须保持兼容。

| 位置 | 新增/修改符号和职责 |
|---|---|
| `apps/runtime-service/src/runtime_service/observability/usage.py`（新增） | `normalize_usage()`、`estimate_usage_cost()` 纯函数；`RuntimeUsageCallback` 与 `with_runtime_usage()` 接线 |
| `apps/runtime-service/src/runtime_service/observability/langfuse.py::with_langfuse_tracing` | 复用 usage helper，统一模型 Token metric 提取，避免两套落库计数 |
| `apps/runtime-service/src/runtime_service/runtime/modeling.py::build_model/fetch_model_connection` | 安全模型身份/价格快照，修改连接返回的结构化类型；所有消费者核对 |
| `apps/runtime-service/src/runtime_service/db/repositories/usage.py`（新增） | `begin_collection/upsert_call/finish_collection/read_run_usage/aggregate_thread_usage`；只负责 SQL |
| `apps/runtime-service/src/runtime_service/db/migrations/versions/0002_usage.py`（已新增，前序 `0001_application`） | 两表、唯一约束、作用域和索引；走现有 Runtime upgrade，不碰引擎迁移 |
| `apps/runtime-service/src/runtime_service/http/usage.py`（新增）、`apps/runtime-service/src/runtime_service/webapp.py` | `run_usage_endpoint/thread_usage_endpoint`，注册受保护只读路由 |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/middleware/memory.py`、`apps/runtime-service/src/runtime_service/tools/images.py` | 当前旁路模型显式接线，不修改其业务、批准和权限逻辑 |

内部接口为 `GET /internal/threads/{thread_id}/runs/{run_id}/usage` 与 `GET /internal/threads/{thread_id}/usage`。使用 Thread 绑定的 `usage-read`，核对 principal/scope 并 `authorize_thread_targets(..., action="read")`。完整 DTO/分页见 [03](03-platform-cost-contract.md)。保持 GET 与 SSE 分离，不新增 SSE usage 事件。

## 任务拆分

进度以本节为准；实现理由和实测修正见 [实施记录](implementation/01-runtime-and-platform.md)。

| 状态/任务 | 改动与代码位置 | 预期结果 | 最小验证 |
|---|---|---|---|
| [x] R02-1 规范化 | `observability/usage.py::normalize_usage` | 标准/别名只采一次，cache TTL/reasoning 非加法 | 参数化 OpenAI/Anthropic/DeepSeek、bool/负数/缺失/冲突、error response |
| [x] R02-2 采集 callback | `RuntimeUsageCallback/with_runtime_usage`、`with_langfuse_tracing` | 每 graph 实例独立，父子/摘要/同步异步路径同一事实源 | Fake model + 实际 create_agent/deep_agent/StateGraph，重复事件、v3 assembled usage |
| [x] R02-3 持久化 | `db/repositories/usage.py`、`0002_usage` | manifest + calls，唯一键约束，多进程可读，无调用和缺失可区分 | 隔离 PG 并发 upsert、重启、超时、索引/约束、0/missing 区分 |
| [x] R02-4 成本 helper | `estimate_usage_cost`、`modeling.build_model/fetch_model_connection` | Decimal + 完整价格快照，不同 catalog 不串价 | 03 测试价、5m/1h、0/空价、未知 VISION 模型、改价 |
| [x] R02-5 旁路覆盖 | `memory.py`、`images.py` 及所有 tracing 调用者 | 隐藏内容不外泄；有父 Run 的 LLM 开销可查；其余有排除声明 | await memory/vision、子图并发、取消、显式 callbacks=[]，检查去重 |
| [x] R02-6 内部查询 | `http/usage.py/webapp.py` | 受保护摘要/分页，跨作用域不返回记录 | usage-read 允许与其他 operation/原生资源拒绝，ACL 撤权，范围上限 |

### R02-1 完成卡：规范化

- **改动内容/预期：** 单一 generation 来源、provider 别名、缓存/TTL/reasoning 白名单；非法/缺失值保留未知。
- **代码位置：** `apps/runtime-service/src/runtime_service/observability/usage.py::normalize_usage`。
- **验证项：** `tests/observability/test_usage.py` 参数化标准/别名、错误 details、超界/冲突和单来源；通过，见下方 Phase R02-1。
- **状态：** [x] 2026-10-07 开发和定向验证完成。
- **合规检查：** [x] 实现；[x] 验证；[x] 本节状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG（本专项能力行）。

### R02-2 完成卡：采集 callback

- **改动内容/预期：** native Run 与 model_call_id 分开；图级一次装配，根收尾与子图调用独立，迟到回调只补已有事实。
- **代码位置：** `apps/runtime-service/src/runtime_service/observability/usage.py::RuntimeUsageCallback/with_runtime_usage`、`observability/langfuse.py::with_langfuse_tracing`。
- **验证项：** 实际 create_agent、StateGraph 同步/异步/并发、DeepAgent 子图与摘要、取消/重入；定向和真实 Worker 通过。
- **状态：** [x] 2026-10-07 开发和定向验证完成。
- **合规检查：** [x] 实现；[x] 验证；[x] 本节状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG（共用专项行）。

### R02-3 完成卡：持久化

- **改动内容/预期：** 两表唯一键、幂等补齐、短事务、作用域 SQL 汇总/keyset 分页；确认零调用、未采集和不完整分别返回。
- **代码位置：** `apps/runtime-service/src/runtime_service/db/repositories/usage.py`、`db/migrations/versions/0002_usage.py`。
- **验证项：** 真实 PG 两进程、重复升级、锁/连接故障、SIGKILL、索引；2 passed。PG 实际重启后历史 Token/金额保持不变。
- **状态：** [x] 2026-10-07 开发和定向验证完成。
- **合规检查：** [x] 实现；[x] 验证；[x] 本节状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG（共用专项行）。

### R02-4 完成卡：估算成本

- **改动内容/预期：** Decimal 六桶计价和完整快照；非零桶缺价/溢出/未知模型身份只保留 Token，不借主图价。
- **代码位置：** `apps/runtime-service/src/runtime_service/observability/usage.py::estimate_usage_cost`、`runtime/modeling.py::build_model/fetch_model_connection`。
- **验证项：** TTL `0.002580000000`、generic `0.002540000000`、缺价/零价/溢出；内部快照、bind_tools 与未知 vision 身份通过。
- **状态：** [x] 2026-10-07 开发和定向验证完成。
- **合规检查：** [x] 实现；[x] 验证；[x] 本节状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG（共用专项行）。

### R02-5 完成卡：旁路与图覆盖

- **改动内容/预期：** hidden memory/vision 仅继承可信 Usage handler，内容 exporter 隔离；无 native Run 的 suggestions/title 明确排除。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/middleware/memory.py`、`tools/images.py`、`observability/usage.py::usage_only_config`。
- **验证项：** memory/vision 组合测试、真实 Summarization 不同模型、四类 demo/DearFlow 组合根；Reference/Showcase/workflow 真实 HTTP smoke；通过。
- **状态：** [x] 2026-10-07 开发和定向验证完成。模型为确定性 fixture，不声称供应商真实账单完整。
- **合规检查：** [x] 实现；[x] 验证；[x] 本节状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG（共用专项行）。

### R02-6 完成卡：内部查询

- **改动内容/预期：** 仅两个 Thread-bound usage-read GET；授权后 SQL 查询，历史可读，存储故障 200 unavailable。
- **代码位置：** `apps/runtime-service/src/runtime_service/http/usage.py`、`observability/usage_query.py`、`webapp.py`、`runtime/auth.py`。
- **验证项：** 内部 route/参数/operation 互拒、native/capability/title 拒绝、真实错项目/错 Run/成员撤权；通过。
- **状态：** [x] 2026-10-07 开发和定向验证完成。
- **合规检查：** [x] 实现；[x] 验证；[x] 本节状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG（共用专项行）。

## 验证要求与记录

### 验证要求

- 单元：R02-1/R02-4 的数字口径；缺失不伪造，unknown 不变 0。
- 组合：一次父图、多子图、摘要、工具模型、收尾记忆提取、两 Run、入队多 HumanMessage、HITL、fork/rollback。
- 集成：两进程 callback、数据库重启、SIGKILL 留未完成占位、connection/lock timeout、只读查询。
- 观测：Langfuse/OTel 关闭或失败仍采集 Token，原生 Agent 结果与开关关闭时一致。
- 安全：只存数字/ID/快照，不写 Prompt/Completion/连接、原始异常；API 不透传内部快照与 parent callback 栈。
- 支持矩阵：当前各接线图逐个 smoke；未经接线的二开图不能宣称自动覆盖。

测试落点：`apps/runtime-service/tests/observability/test_usage.py` 覆盖归一化/成本/隐藏调用；`test_usage_lifecycle.py` 覆盖组合根、摘要和生命周期；`tests/durable/test_usage_ledger.py` 覆盖真实 PostgreSQL；`tests/http/test_usage.py` 覆盖授权与 DTO。既有 tracing/modeling/memory/image 测试同时回归，不新增测试框架。

### Phase 验证记录（2026-10-07，6 项任务）

| Task | 已执行证据 |
|---|---|
| R02-1 | usage+lifecycle+http 定向 26 passed；合法与非法原始 Token、details、TTL/source 冲突覆盖 |
| R02-2 | 同一组 26 passed，实际 LangChain/LangGraph graph；真实 Worker 最新 16 项链路覆盖父/子/入队/HITL/fork/replay |
| R02-3 | 真实独立 PG `tests/durable/test_usage_ledger.py` 2 passed；[重启证据](fixtures/restart-evidence.json) 历史一致 |
| R02-4 | usage/modeling 初始 23 passed、modeling 后续回归；未知身份携价 vision 最后一项 1 passed |
| R02-5 | memory/image/title 定向 40 passed、2 个外部 e2e deselected；隐藏调用+生命周期追加测试通过，5 条既有 SWIG 警告 |
| R02-6 | 内部 route/usage/langfuse 26 passed 与 API 双端契约；[真实 HTTP 证据](fixtures/e2e-evidence.json) 含当前撤权和故障 |

命令均在 Runtime 服务目录用既有 `$RUNTIME_PYTHON -m pytest -q` 执行，`PYTHONPATH=src`。真实 ledger 仅设置 `USAGE_TEST_DSN` 指向隔离库；详细复跑入口见 05。上表定向集合存在重叠，不将各行相加成测试总数。Final 单独写 05。

## 状态

六项开发及 Phase/Final 完成，Runtime 范围 done；44 项修复后相关复验通过，全量既有失败见 05。前端亦已全部闭环，整项目 done。

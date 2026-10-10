# F01：通用 Run Token 额度保护评审

## 目标

评估同事提出的 TokenBudgetMiddleware 是否值得开发，并给出符合当前三服务范式的最小完整方案。结论：**补齐按 Token 用量限制后续执行的能力有价值；整套移植 DeerFlow 会重复建设。** 建议把 F01 改为“基于现有 Usage ledger 的单 Run Token 额度保护”。

此项按**治理改动**管理。用户于 2026-10-09 完成人工评审并批准实施到仅余前端；Runtime/API 非前端实现与必要验证现已完成，F01 整体 **partial**，剩余前端 F-T01—F-T04、E02 与联合 Final。前端由同事按 [16 实现版交接](16-token-budget-frontend-handoff.md) 接续。未提交、部署现役、修改实际 env 或依赖锁；迁移和故障验证只操作临时隔离库。

沿用本项目多专题模板和 2026-09-13 启动日期，不另建重复项目。本文任务表是 F01 的唯一进度来源；[12 补齐计划](12-completion-plan.md) 的其他任务继续独立推进。本篇不重开已经完成的执行预算、用量跟踪、上下文、超时或停止专项。

## 方案设计

### 1. 证据基线与限制

| 来源 | 本次核对范围 |
| --- | --- |
| 当前项目 | HEAD `85d63d87bdf84dabbb963f79e8dd4b2db4432ade`，开始读取时工作树干净；读取 CONTEXT、服务规范、相关 lessons、源码和测试 |
| DeerFlow | 本机 DeerFlow 参考工作区，HEAD `cc664451`；相关 token budget middleware/config 无 HEAD 差异，其他文件有本地修改 |
| Open-SWE | 本机 Open-SWE 参考工作区，HEAD `ad417d64`；usage、cost、server 等有本地修改，结论对应本机工作区，不冒称干净上游行为 |
| 锁定依赖 | `apps/runtime-service/uv.lock`：LangChain 1.3.17、Core 1.6.0、LangGraph 1.2.11、DeepAgents 0.7.8、GraphHarbor 0.13.0.post43 |
| 官方依据 | 已查询 langchain-docs 与 langchain-reference MCP：[Middleware hooks/顺序](https://docs.langchain.com/oss/python/langchain/middleware/custom)、[AgentMiddleware](https://reference.langchain.com/python/langchain/agents/middleware/types/AgentMiddleware)、[AsyncCallbackHandler](https://reference.langchain.com/python/langchain-core/langchain_core/callbacks/base/AsyncCallbackHandler) |

以上是规划开始时的基线；实施后已在本工作树隔离 `.venv` 核对安装版本并完成测试，不代表现役部署。`docs/quickstart/` 当前不存在，入门信息参考根 README 和各服务入口。旧文档中的 post37/post42、max(mode, env) 和历史测试数字不能替代本次代码事实。

### 2. DeerFlow 实际怎么做

以下路径相对 DeerFlow 仓库根目录。

| 文件/符号 | 当前行为 | 可借鉴之处与局限 |
| --- | --- | --- |
| `backend/packages/harness/deerflow/config/token_budget_config.py::TokenBudgetConfig` | 默认 enabled=false、max_tokens=200000、warn=0.8、hard=1.0；input/output 独立限额默认 None，显式值 >=1；校验 hard>=warn | 同事示例的 input/output=0 不能原样传入当前配置；hard=0.95 是自选策略，不是默认值 |
| `.../agents/middlewares/token_budget_middleware.py::before_agent` | 将旧 AIMessage 用量标为 seen，避免历史 Thread 用量进入本次 Run | Run 与 Thread 分开是正确语义；不能用最新 HumanMessage 代替真实 Run 边界 |
| `...::after_model/_apply` | 遍历 messages，用 message.id 的 input/output 正增量累计；兼顾子任务用量回填；取 total/input/output 最大占用比例 | 防重复思想值得保留；消息扫描、压缩、无 ID、失败物理调用和恢复后的用量缺失使它不适合作为我们新的事实源 |
| `...::wrap_model_call/awrap_model_call` | 下一次请求临时注入 `HumanMessage(name="budget_warning")`；模型异常时重新入队 | 避免在 AI(tool_calls) 与 ToolMessage 中间写持久警告；无需复制队列，我们已有 system 收尾函数 |
| `...::_build_hard_stop_update` 与 `.../tool_call_metadata.py::clone_ai_message_with_tool_calls` | 达限后删除结构化、raw、provider content blocks 中的 tool calls，追加固定停止说明 | 必须处理多个 provider 表面；它结束循环，但不保证模型生成完整总结，也不能撤回已经发出的流式参数 |
| `...::_stop_reason/consume_stop_reason` 与 runtime.context | 记录 token_capped，子执行器/Worker 区分触限结束与普通完成 | 语义值得借鉴；本项目 RuntimeContext 是 frozen dataclass，不可照抄 dict 写入方式 |
| `.../agents/middlewares/_bounded_dict.py::BoundedDict` | 多个 run_id 字典各限 1000 条，普通插入顺序淘汰；部分调用自行 move_to_end | 只限制外层 Run 数，不限制每个 seen_messages 大小；进程重启丢状态，容量淘汰也不是额度恢复机制 |
| `.../agents/lead_agent/agent.py`、`.../tool_error_handling_middleware.py`、`.../subagents/executor.py` | 主图条件挂载；子任务另有默认/覆盖配置和中间件实例；主图依赖 TokenUsageMiddleware 回填子用量 | 不等于并行子任务事前共享一个严格全树额度；不迁移其 subagent executor 或全局 AppConfig |
| `frontend/src/core/tasks/subtask-result.ts` | 解析后端 subagent_stop_reason，包括 token_capped | 前端消费停止事实，不计数、不裁决费用；无需迁移它的子任务状态机 |

DeerFlow 的关键边界：检查在模型响应之后，已发生消费无法收回；最后一次调用和同时在途的子调用可能超额。没有 usage 的响应不触发累计；有界字典不解决多进程与重启。`cannot raise` 是其自然结束方案的实现选择，并非 AgentMiddleware 或 GraphHarbor 的通用禁令。

### 3. Open-SWE 与当前项目：哪些已经覆盖

Open-SWE 本机 `agent/{server,chat,reviewer,analyzer}.py` 已使用官方 ModelCallLimitMiddleware；`agent/middleware/conversation_offloading.py` 管理摘要；`agent/utils/run_usage.py::summarize_run_usage` 聚合主消息用量；`agent/agent_cost.py` 在结束后延迟补充 LangSmith 成本。核对这些位置及 middleware 目录，未见与本次 F01 等价的按累计 Token 拒绝后续调用能力。不能因为已经借鉴 Open-SWE 就认定成本保护全部完成。

下表路径相对当前项目根目录。

| 能力 | 当前实现/事实源 | 本轮判断 |
| --- | --- | --- |
| AgentMiddleware 接口 | `apps/runtime-service/src/runtime_service/middlewares/{execution_budget,model_resilience,retry}.py`；四图使用 create_agent/create_deep_agent | **已具备**。无需开发 GraphHarbor middleware 适配器或升级依赖 |
| 模型/工具次数与图步骤上限 | `middlewares/execution_budget.py::ExecutionBudgetMiddleware`；官方 ToolCallLimitMiddleware/RemainingSteps | **已具备，复用**。计迭代次数，不等于物理重试次数或 Token |
| 预警、收尾、停止原因 UI | `execution_budget.py::{add_wrapup_instruction,build_budget_notice,emit_budget_notice}`；API `adapters/langgraph/sdk_client.py`；Web `modules/chat/budget/`、`useRunBudget.ts` | **已具备，增量扩展**。新增 Token 单位/code，不再造通知通道或状态机 |
| 用量归一化和物理调用记录 | `observability/usage.py::{normalize_usage,RuntimeUsageCallback,with_runtime_usage,usage_only_config}` | **已具备，作为唯一采集入口**。主/子、摘要、可信 memory/vision 使用同一口径 |
| 持久去重、Run/Thread 用量与成本 | `db/repositories/usage.py::{upsert_call,read_run_usage,aggregate_thread_usage}`；`observability/usage_query.py`；API/Web Usage 模块 | **已具备，复用 ledger**。唯一键是 tenant/project/native run/model_call_id；没有 Token 强制停止 |
| 上下文窗口与单次输出 max_tokens | `middlewares/conversation_offloading.py`、`runtime/modeling.py`、Context 字段 | **已具备**。控制单次输入容量/输出长度；不限制整个 Run 累计消费 |
| Worker 时限和用户取消 | `runtime/run_budget.py`、`run_control/`、对应已完成专项 | **已具备，保留**。不新增 Worker 定时器、取消工具或第二份 Run 表 |
| 统一主子图 Token 额度/恢复后保护 | 当前无 token_budget 执行逻辑；usage 持久化是 fail-soft 观测 | **真实缺口，建议补**。直接把观测值接成安全约束还需明确失败策略 |
| 每 Agent token_budget 配置 | `runtime/contracts.py::RuntimeContext`、`runtime/resolver.py::parse_runtime_context` 当前严格字段；平台公开 options 无此字段 | **首期不做**。未经授权的输入不能成为平台成本上限；先用部署侧策略 |

已完成能力由 [执行预算](../20261007-agent-execution-budget/README.md)、[Usage](../20261007-agent-usage-cost-governance/README.md)、[上下文](../20261006-agent-context-window-governance/README.md)、[超时](../20261006-agent-run-timeout-governance/README.md)、[停止](../20261007-agent-run-cancellation/README.md)专项维护。源码接线证明实现存在，现役启用和完整质量仍须按它们的验证记录判断。

### 4. 对同事五项建议逐条裁剪

| 原建议 | 决定 | 对当前项目的调整 |
| --- | --- | --- |
| 确认 GraphHarbor 支持 AgentMiddleware | 已确认代码接线，跳过开发 | 钩子来自 LangChain agent factory；GraphHarbor 执行编译图 |
| 新写 TokenBudgetMiddleware | 部分采纳 | 只写额度决策、收尾和阻止新增工具的薄层；Token 采集继续由 RuntimeUsageCallback 负责 |
| 新写 BoundedDict | 不采纳 | 一次受信 Run/attempt 绑定对象共享，持久事实用已有 ledger；无全局 run_id 缓存 |
| 注册 Agent 工厂 | 采纳接线 | 四个正式图的现有 agent.py 显式装配，并覆盖声明式子图和 Workflow 内层；不造通用 Builder |
| platform-api Agent 配置新增 token_budget | 首期不采纳 | 没有逐 Agent 配额的已确认需求；这会扩大 CRUD、签名 Context、schema、调度快照和前端表单范围 |

### 5. 其他通用能力的取舍

本次实施候选仅 F01。以下是去重后的研究优先级，不新增其他开发承诺。

| 候选 | 当前与 DeerFlow 的差距 | 建议 |
| --- | --- | --- |
| 循环/无进展检测 | 当前有总次数限制；未见等价工具参数滑窗检测，14/E05 是历史复现 | 在既有 T07 按失败场景重验后评审，可能比更多配置有价值；不随 F01 搭售 |
| 完成证据、Todo、length/空输出 | 已有 Todo 和研究证据文件；不能据此证明“全部完成”，14/E01—E07 仍须按当前代码重验 | 继续 T07，不复制完整判断 Agent 或强行追加无限续跑 |
| 压缩后任务连续性 | 摘要、初始目标保护、手动整理已完成；完整用户约束/来源/未完成项跨多次压缩质量未在本轮验证 | 先跑现有 T07 的质量集，只补丢失事实；不造第二套摘要或记忆系统 |
| 工具大输出与回读 | 已有分页/证据落盘/官方外置、公共命令 128KiB 上限；截断前全文能否回查仍有区别 | 在原任务下验证，不批量移植 ToolOutputBudgetMiddleware |
| 重试、错误分类、Workspace 容错、观测、定时、推荐问题 | 已有专项与代码落点 | 复用，按剩余真实验收推进；不重新实现同名中间件 |
| Goal、自主多 Run 续跑、IM/TUI、业务媒体、知识产品 | 超出本次通用 Token 保护目标，部分还涉及独立计费/授权 | 略过；不得为迁移 DeerFlow 顺带增加产品入口 |

### 6. 建议的首期语义

**额度定义：** 一个受信原生 Run 的已观测总 Token，包含主 Agent、同 Run 子 Agent、物理重试/备模型、隐藏摘要和能证明归属的 memory/vision。`total_tokens = input_tokens + output_tokens`，缓存读取仍算 Token，reasoning/cache 明细不二次相加。Token 与模型价格不同，费用继续使用现有 Decimal 估算；本期不承诺金额上限。

**部署策略草案：** `RUNTIME_TOKEN_BUDGET_ENABLED=false`、`RUNTIME_TOKEN_BUDGET_MAX_TOKENS=100000`。上限为 1 至 JS safe integer 的正整数，拒绝 bool/非法值；固定 `warn_at=ceil(max_tokens*4/5)`、停止点为 max_tokens，避免再引入两个比例配置。100000 是评审起点，不是现役值或已校准生产值。启用要求 `RUNTIME_USAGE_ENABLED=true`、应用迁移就绪、完整受信 Run 身份；缺条件明确拒绝启用，不静默降级。schema/probe 不读 ledger、不建立预算。

| 边界 | 首期约定 |
| --- | --- |
| 主子/重试 | 同 native Run 全树共享同一策略和用量视图；不给每个子图重新发一份 max_tokens |
| Worker 重建/接管 | 从同 Run ledger 恢复消耗和策略；attempt 时钟可以更新，Token 不能清零 |
| 新 Run/审批 resume | 按当前原生 Run 语义生成新额度；同一 Thread 累计只是展示。HITL resume 仍只携当前 interrupt ID 和原快照 |
| 同 Run 入队用户消息 | 不按 HumanMessage 重新计额；只有真实新 native Run 才有新额度 |
| 正常最后回答 | 恰好耗尽额度且已自然返回无 tool calls 的回答，不标成“因额度停止”；后续被拒绝的工作才记录 stop_code |
| 已达上限 | 不启动新的模型调用、task 或工具副作用；已开始的调用/命令按既有超时、取消和清理完成，不强杀且不承诺回收 provider 费用 |
| 缺失/无效用量或 ledger 故障 | 预算启用时将可验证性记为不足，在下一新增工作边界拒绝并给 token_budget_unverifiable；不得记为0或继续宣称受保护 |
| 失败物理调用 | 若有可信 usage 就计入；失败未给 usage 的潜在消费未知，停止追加付费调用。provider 明确拒绝且能够证明未执行的例外需证据，不先加猜测规则 |
| 流式/并发 | 响应后记账；可以超过阈值。只禁止检查点之后的新派发，不宣称逐 Token 实时制动或并发预留 |
| 非 LLM 副作用/旁路 | suggestions/title、无父 Run 调用、图片生成/搜索/部署供应商费用继续明确排除；Token cap 不控制这些外部费用 |

触限策略建议采用**受控错误停止**，与现有 Runtime 执行错误边界融合；不采用 DeerFlow 改写已生成 AIMessage/tool_calls 的自然 success 退出。80% 时复用 `add_wrapup_instruction()` 给后续模型机会收尾；硬限不发起额外付费“总结调用”，不保证保存未产生的成果。最后回答与工具配对不改写；停止后续工具的 checkpoint 在下一次合法用户请求仍可恢复，必须验证 RuntimeConfigMiddleware 现有消息清理。

建议错误为专用 `TokenBudgetExceededError` / `TokenBudgetUnverifiableError`，继承既有 RuntimeExecutionError 以维持非基础设施失败语义；API 精确投影为 `runtime_token_budget_exhausted` / `runtime_token_budget_unverifiable`。名称与载荷须在 Phase 0 真实 Worker 证明后冻结。不得被模型 retry/fallback、只读 task retry、Filesystem 的 ValueError 处理或 memory 后处理吞掉，也不得被误记为 provider 故障。若真实引擎不能支持该边界，先回到评审，不临时复制 DeerFlow 执行器。

**这是基于已观测用量的保护，不是严格账单封顶。** 供应商处理与本地持久化不可能形成同一事务；中途断流、SIGKILL、SDK 内部隐式重试和在途并行均可能产生未知/额外消费。严格金额配额若成为验收要求，须另评审事前估算与预留、每请求输出限额、并发协调、供应商账单对账；不能靠 hard_stop=0.95 保证。

### 7. 最小实现落点

下表保留已批准的施工定位；最终实际改动、未需改动的复用入口和验证证据见 [实施记录](implementation/21-f01-token-budget.md)。新增迁移固定为 `0003_token_budget`，在现有 Usage callback 之外附加仅做派发检查的同步守卫，以覆盖 Core 1.6.0 吞异步回调异常的同步桥接。

| 层/文件 | 拟补内容与调用影响 |
| --- | --- |
| Runtime `src/runtime_service/runtime/token_budget.py`（新） | `RunTokenBudget`：受信身份、冻结策略、额度视图及拒绝判断；每 Run 绑定，不挂全局缓存。只消费已有物理调用事实，不扫描 messages，不重复计价 |
| Runtime `src/runtime_service/observability/usage.py` | 给 `RuntimeUsageCallback` 绑定可选预算；`on_chat_model_start` 在实际调用前检查，覆盖主子/摘要/vision/memory/物理 retry；`_finish_call` 沿 normalize_usage 更新同一 call 事实并持久化。重复完成/晚到更完整 usage 替换旧贡献，不再累加；停机原因只在确实拒绝新工作时写入 |
| Runtime `src/runtime_service/db/repositories/usage.py` | 扩展 begin/load/stop 的短事务函数，按完整 tenant/project/thread/graph/native Run 读取已有事实；旧 call 唯一键继续去重。恢复后不把相同 call 再加到已恢复小计；区分当前在途调用与前 attempt 的不可确认 started |
| Runtime `src/runtime_service/db/migrations/versions/<next-token-budget-revision>.py`（拟新增） | 接当前 Alembic head（现状为 `0002_usage → 0002_run_control`，具体 revision 在实施前由 `alembic heads` 冻结）；仅在 runtime_usage_runs 增加可空 token_budget_policy（冻结 max/warn/版本）和 token_budget_stop_code（固定两码），不增加账本表/Run 状态表、不删历史。策略首写固定，同 Run 接管不覆盖 |
| Runtime `src/runtime_service/middlewares/token_budget.py`（新）与 `middlewares/__init__.py` | `TokenBudgetMiddleware`：在模型请求前检查、在模型结果后区分自然完成/需要继续工作，并在工具副作用前再次读取共享预算；`wrap_model_call` 复用收尾转换；复用现有通知函数。不能只依赖 `after_model`，因为它无法阻止模型本次消费，也无法覆盖模型外工具/任务副作用。导出显式 `__all__` |
| Runtime `src/runtime_service/observability/langfuse.py::with_langfuse_tracing`、`usage.py::with_runtime_usage` | 透传受信预算对象到唯一 usage callback。Langfuse 关闭也工作；开启预算时需验证 callback 的 run_inline/raise_error 与同步桥接，不能假设默认回调异常会传播 |
| Runtime `services/dearflow_agent/agent.py`、`services/demo/showcase_demo/agent.py`、`services/reference_agent/agent.py`、`services/demo/workflow_demo/agent.py` | 在各自组合根建立一次预算，共享给声明式子图及内层模型。复用 Worker `read_run_budget()` 的身份核对；Workflow 不得因清 metadata/run_id 而静默失去预算，沿外层 writer 发布 root 通知 |
| Runtime `middlewares/{retry,model_resilience,model_errors,conversation_offloading}.py`、`tools/errors.py`、`tools/images.py`、Dear `middleware/memory.py` | 只补需要的错误传播/隐藏调用关联，防重试或吞掉保护异常；memory 在 cap 后跳过新的后台抽取并保留已完成主回答，记安全跳过原因，不把未知用量变成完整数据 |
| Runtime `observability/usage_query.py::query_run_usage` 与 `http/usage.py` | 现有 Run Usage GET 增加可选 token_budget 摘要，支持重放过期/刷新后的历史停机原因；无新 endpoint |
| Runtime `.env.example`、两个 deploy `.env.runtime-service*.example`、`scripts/validate_runtime_config.py::validate` | 示例及 doctor 校验两项部署策略、Usage 依赖、API/Worker 一致性；实际 .env 不改。额外 Compose 传参只在现有 env_file 无法传递时补 |
| API `adapters/langgraph/sdk_client.py::{project_budget_notice,project_execution_error,normalize_runtime_object}` | 精确扩展通知单位/组合和错误白名单；JSON、普通 SSE、Protocol/v3、tools/tasks/debug/checkpoint 各错误槽位安全出口一致 |
| API `core/runtime_contract.py`、`modules/runtime_gateway/application/usage.py` | 写入口拒绝预算私有字段/伪造通知；Run Usage DTO 增可选预算摘要并交叉校验，沿当前 usage-read/ACL，不新增 operation/管理配置/数据库 |
| Web | 只扩展现有 budget types/view-model/useRunBudget/状态栏及 Usage DTO，详见16；由同事实现 |

同步/异步接线、隐藏模型和失败边界是范围的一部分。只挂 `after_model` 会漏摘要、重试和工具内模型；只给主 Agent 挂 middleware 会漏子任务；只在外层 wrapper 检查会漏同一次 handler 内的物理重试。所有调用检查共享预算，所有记账只走 RuntimeUsageCallback。

本地预算视图可缓存 ledger 的已确认基线及本 handler `_calls` 的增量；它是可重建投影，不是第二份事实源。更新必须按 model_call_id 幂等、并发安全，并与 SQL upsert 的“更完整事实替换”规则一致。若锁定版本 callback 在物理请求前无法可靠阻断，Phase 0 必须失败并重新评审，不默许付费调用穿透。

### 8. 三层契约草案与前端责任

沿现有 `runtime_budget_notice` v1 增加下列组合，不新增 SSE channel。全树预算 notice 使用受信根 Run writer，`scope=primary`、root namespace；子任务也不能生成独立额度。notice_id 含真实 Run 和固定 Token 维度，同一阶段确定性去重。

| code | unit | budget_scope | 数值/含义 |
| --- | --- | --- | --- |
| token_budget_approaching | tokens_total | run | limit=max_tokens，used=已知总量，remaining=max(0,limit-used)；进入80%且用量可验证 |
| token_budget_exhausted | tokens_total | run | 同上；确实阻止了新工作，不是仅仅观察到最后回答等于上限 |
| token_budget_unverifiable | tokens_total | run | limit=max_tokens，used=已知小计或null，remaining=null；用量/持久化不足而拒绝新工作 |

该 notice 表示额度决策，不等于 Run 终态 ACK。错误由上面的两个精确类型映射。费用、prompt、provider 原文、密钥、绝对路径或完整配置均不入通知；数值只接受安全非负整数/null。输入中旧 `max_tokens` 仍是单次模型输出参数，不能当作 Run cap。

现有 `GET /api/langgraph/threads/{thread_id}/runs/{run_id}/usage` 草案增可选字段 `token_budget`；无策略/旧记录返回 null，旧 DTO 缺字段也按 null 处理。字段建议为 version=1、budget_scope=run、unit=tokens_total、max_tokens、warn_at_tokens、known_used_tokens、remaining_tokens、coverage（complete/partial/unavailable）、stop_code（null/token_budget_exhausted/token_budget_unverifiable）。remaining 仅在用量可验证时给值；已超额时为0，不钳制真实 used。stop_code 仅为预算停止原因，不能覆盖 GraphHarbor 原生 run_status。正常完成但消耗等于 cap 的 stop_code=null。

API 执行授权与白名单投影；Runtime 生产额度和用量事实；Web 只消费。Thread Usage 和模型价格 DTO 不扩展。服务端停止不依赖浏览器在线；断线不重发整个 Run。新枚举和 GET 字段已通过后端真实链路，16 和 [实际 fixture](fixtures/token-budget-v1.json) 已冻结，前端尚未实施。

### 9. 风险、评审点与回退

| 编号 | 待评审建议/风险 | 处理 |
| --- | --- | --- |
| G1 | 采用本篇最小首期：总 Token、native Run、全树共享、部署侧开关 | 明确批准，不把逐 Agent 表单/Thread/月度配额加入首期 |
| G2 | 80%提醒；100%后受控 error；unknown 拒绝新增调用 | 比 DeerFlow 宽容未知用量更严格，会降低缺失 usage 的模型/失败重试可用性；启用前用真实 provider 确認质量 |
| G3 | runtime_usage_runs 两个可空字段和 Run Usage 可选 DTO | 确认保留、迁移、原生 Run 状态归属；不直接改 GraphHarbor 表 |
| G4 | 首期不提供严格金额封顶，100000 待真实任务校准 | 不把95%阈值误作预留保证；多价模型和缓存折扣仍由现有成本观测解释 |
| R1 | 默认 AsyncCallbackHandler 不能假设能阻止请求，sync/async/重试传播可能不同 | Phase 0 实际模型请求计数+真实 Worker 证据是进入实现的必要条件 |
| R2 | 隐藏 memory 后处理吞异常；Workflow清Run metadata；工具可能转换 ValueError | 明确列入接线与组合测试，不能凭四个类名认定覆盖 |
| R3 | ledger 失败会让原本可继续的任务停止 | 开关默认关闭；观测单独开启时沿原 fail-soft；严格预算启用时不足可验证必须说明原因 |
| R4 | 在途并发/晚到回调/SIGKILL 与数据库之间有空窗 | 已消费记实数，无法确认记unknown；恢复拒绝追加而不补造消费，声明保护能力边界 |
| R5 | `sdk_client.py::project_execution_error` 现有字符串包含匹配与 active `error-envelope.md`“不从字符串含类型分类”存在差异 | 仅标记，AI不裁决或顺手重构。新增 Token 映射要求精确；进入相关出口实施前由人确认该既有差异的处理范围 |

实施后先隔离迁移，后部署 API/Worker/Web；启用前确认新 DTO/事件两端就绪。回退时暂停新提交并 drain 或按既有 Stop 确认已运行任务，统一关闭新预算开关/恢复已验证应用源码；保留扩展列和全部 Usage 事实，不做破坏性 downgrade。已停止 Run 不自动续跑，历史成本不重算。未授权生产部署或 Git 操作。

## 任务拆分

估算为有效工程日，不含人工评审和外部环境等待；Runtime/API 约6—9日，前端约1—2日，Phase 0 后校准，不作为排期承诺。

| 状态 | 任务 | 交付 |
| --- | --- | --- |
| [x] | P01 源码去重与官方接口核对 | 本篇2—5节，三仓事实、配置差异、已有能力和排除项已记录 |
| [x] | P02 方案、代码落点和前端交接 | 本篇6—9节及16；只交付规划 |
| [x] | P03 规划文档一致性检查 | 本篇验证记录中的只读检查；不代表运行能力通过 |
| [x] | R00 人工方案评审 | 用户于 2026-10-09 明确批准实施；推进到仅余前端，遇到真实 block 时报告。沿本方案新增 Token 精确出口，既有 R5 字符串投影差异保留，不扩展处理范围 |

### Phase 0：锁定版本的接线验证（0.5—1日，评审后）

- [x] T00 最小真实 compiled graph/Worker 验证。
- **改动内容：** 在项目测试中验证 callback 物理调用前拒绝、sync/async 传播、retry/fallback 不穿透、专用 RuntimeExecutionError 不被 Worker 再排队；固定受信 Run 与子图/Workflow 归属。
- **代码位置：** `apps/runtime-service/tests/middlewares/test_token_budget.py`、`tests/durable/test_token_budget.py`、`tests/fixtures/token_budget_platform.py`；复用 `tests/support` 和原隔离 stack fixture。
- **预期结果：** provider 请求计数在阻断后不再增长；异常保持精确；schema/probe无I/O。无法证明则回到评审，后续实施不开始。
- **验证项：** V01、V06、V08、I02。记录实际依赖来源/版本，不以锁文件或最新官网代替安装证据。
- **结果与状态：** 已完成 2026-10-09；sync/async compiled graph 及四图真实 Worker 请求计数、精确失败与 retry_count=1 通过。见 Phase T00 和 [实施记录](implementation/21-f01-token-budget.md)。
- **合规检查：** [x] 实现；[x] 直接验证；[x] 本任务状态；[x] CONTEXT/FEATURES/CHANGELOG 同步。

### Phase 1：策略与唯一账本（1.5—2日）

- [x] T01 持久策略和恢复读取。
- **改动内容：** 增加可空列、Run首写策略、读取/停机短事务；旧记录不补账；已保存停止原因不可被普通结束清掉。
- **代码位置：** `runtime/token_budget.py::RunTokenBudget`、`db/repositories/usage.py::{begin_collection,read_budget,finish_collection}`、迁移 `0003_token_budget → 0002_run_control`、`tests/durable/test_token_budget_ledger.py`。
- **预期结果：** 同native Run重建使用原策略与消耗；新Run独立；原Usage查询仍正确。
- **验证项：** V02、V03、I01、I03、I04；迁移重复运行、旧行兼容及保留式回退。
- **结果与状态：** 已完成 2026-10-09；真实 PG 幂等/晚到替换、策略冻结、同 Run SIGKILL 接管/未知 started、锁超时与旧 HEAD 源码读扩展库通过。
- **合规检查：** [x] 实现；[x] 直接验证；[x] 本任务状态；[x] CONTEXT/FEATURES/CHANGELOG 同步。

- [x] T02 Usage callback 接入额度。
- **改动内容：** 一套 normalize/upsert 加预算投影；dispatch前检查、完成后幂等替换；缺用量/失败持久化使保护不可验证。保留关闭预算时原观测行为。
- **代码位置：** `observability/usage.py::{RuntimeUsageCallback,_TokenBudgetDispatchGuard,usage_only_config}`；复用未改动的 `observability/langfuse.py`，旧 Usage/生命周期与新 middleware 测试共同验证。
- **预期结果：** 重试真实调用累加；重复观测不累加；同步/异步、摘要/旁路一致，成本不重复。
- **验证项：** V02—V06、V10、I01—I04。
- **结果与状态：** 已完成 2026-10-09；唯一采集/去重、并发在途、sync/async、摘要/vision/memory、unknown/数据库失败拒绝、关闭无新增 budget read 全部通过。
- **合规检查：** [x] 实现；[x] 直接验证；[x] 本任务状态；[x] CONTEXT/FEATURES/CHANGELOG 同步。

### Phase 2：预警、停止与四图接线（1.5—2日）

- [x] T03 薄 middleware 和控制流边界。
- **改动内容：** 复用收尾与custom，阻止达限后新工具；明确自然完成与触限的区别；异常绕过 retry/fallback/工具容错，memory不追加消费。
- **代码位置：** `middlewares/token_budget.py::TokenBudgetMiddleware`、四个 `services/*/agent.py`、`runtime/errors.py`、`runtime/modeling.py::build_model`、Dear `middleware/memory.py::aafter_agent`；Workflow 保留可信 metadata.run_id，复用原 respond/retry/工具容错。
- **预期结果：** 主子共享额度，达限不写新文件/不再delegate，不强行生成总结；历史AI/Tool配对、HITL和取消不损坏。
- **验证项：** V01、V05—V09、V11、I02、I05；实际副作用spy和provider请求数，不只mock middleware。
- **结果与状态：** 已完成 2026-10-09；四图16基础 HTTP 场景、两类真实子图共享、自然触限成功、工具无新增副作用、警告 writer 失败幂等、HITL/取消和恢复通过。SDK 隐式重试在开关开启时设0。
- **合规检查：** [x] 实现；[x] 直接验证；[x] 本任务状态；[x] CONTEXT/FEATURES/CHANGELOG 同步。

- [x] T04 配置、doctor与公开schema边界。
- **改动内容：** 两个部署变量、启用依赖检查、同Run冻结策略；公开Context仍拒绝token_budget，schemas不暴露私有对象。
- **代码位置：** Runtime `.env*.example`、`scripts/validate_runtime_config.py`、现有resolver/schema/probe测试。
- **预期结果：** 非法或不完整启用明确失败；默认关闭；无需改AgentEditor、Catalog或JWT schema。
- **验证项：** V01、V12、回退B01。
- **结果与状态：** 已完成 2026-10-09；非法开关/cap、Usage/存储依赖、缺可信身份拒绝、四图 enabled schema/probe 零 I/O、关闭开关与旧源码兼容通过。实际 env 未改。
- **合规检查：** [x] 实现；[x] 直接验证；[x] 本任务状态；[x] CONTEXT/FEATURES/CHANGELOG 同步。

### Phase 3：安全出口、历史查询及交接冻结（1—1.5日）

- [x] T05 API投影与Run Usage可选摘要。
- **改动内容：** Token notice/错误精确映射、私有写入拒绝、现有Run GET预算摘要校验；保持当前ACL和usage-read。
- **代码位置：** API `adapters/langgraph/sdk_client.py`、`core/runtime_contract.py`、`modules/runtime_gateway/application/usage.py`、`tests/test_execution_budget_projection.py`、`test_run_usage.py`；Runtime query/http。
- **预期结果：** 普通/Protocol/v3和JSON统一安全；事件过期仍能读取可信停止原因，不用Thread.error猜旧Run。
- **验证项：** V13、I06、S01—S03。
- **结果与状态：** 已完成 2026-10-09；61 API 测试/177 subtests、v3 递归 tools.error 投影、普通/Protocol/JSON 白名单、旧 DTO/null/安全整数、两用户两项目/撤权/无效认证和私有注入真实 HTTP 全通过。
- **合规检查：** [x] 实现；[x] 直接验证；[x] 本任务状态；[x] CONTEXT/FEATURES/CHANGELOG 同步。

- [x] T06 前端冻结交接与后端最短E2E。
- **改动内容：** 根据实际DTO生成契约样例；16从草案更新为实装版本，记录成功/触限/未知/旧行样本。前端实现由同事按16执行。
- **代码位置：** 本专题及16；项目内 `fixtures/token-budget-v1.json`（实现后创建）；Runtime接受测试与API跨服务测试。
- **预期结果：** 同事有真实样本、字段语义、准确错误与权限行为；服务端可离开浏览器独立保护。
- **验证项：** E01/E03 已通过；E02 归前端 F-T04。接线差异已回填，不把受控 provider 证据标成真实模型。
- **结果与状态：** 已完成 2026-10-09；完整后端测试1 passed/30场景，DTO/schema/7样本/3notice/2error已冻结，真实 DeepSeek摘要+child两次调用43 tokens、用量 complete。
- **合规检查：** [x] 实现/交接；[x] 直接验证；[x] 本任务状态；[x] CONTEXT/FEATURES/CHANGELOG 同步。

### Phase 4：Final联合验证（0.5—1.5日，前端完成后）

- [x] T07-B 非前端完整验证、性能/恢复/回退与文档收口。
- **改动内容：** 下面矩阵除 E02/浏览器外已完成；记录真实命令、版本、全量基线失败与修复；同步服务活规范和FEATURES/CONTEXT/CHANGELOG。
- **代码位置：** Runtime/API现有测试、16前端任务与相关E2E、项目verification记录。
- **预期结果：** 非前端可先完成并明确前端pending；整项全部达到验收才done，不把规划P01—P03或Phase通过当实现完成。
- **验证项：** 157 Runtime 定向回归、61 API/177 subtests、30 HTTP场景、真实 PG/旧源码回退、真实 provider 与12组性能矩阵通过；两服务全量未全绿，基线归属见下，不伪称通过。使用 verify-change，Phase 与联合 Final 分开。
- **结果与状态：** 非前端 done 2026-10-09；详见 Phase T07-B。无 F01 后端 blocker，不涉及生产发布。
- **合规检查：** [x] 实现；[x] 适用非前端验证；[x] 本任务状态；[x] CONTEXT/FEATURES/CHANGELOG 同步。

- [x] T07-F 前端实施后的 E02 与联合 Final。
- **负责人/依赖：** 前端完成 16/F-T01—F-T04；联合三服务真实浏览器、1440/768/390、在途过渡态、不可验证、自然完成、刷新对账及真实大模型验收。
- **结果与状态：** done 2026-10-09。前端 F-T01—F-T04 全部落地，单元测试 46 passed，typecheck/lint/build 全绿；Playwright Chromium E2E 6 项测试全部通过（耗时 19.1s），留存 8 张 1440/768/390 及真实百炼·qwen-plus 全链路调用截图证据。

## 验证要求与记录

### 单元与真实组合图矩阵

| 编号 | 验证内容 | 关键断言 |
| --- | --- | --- |
| V01 | 默认关闭/启用、非法值、graph schema/probe、缺身份 | 默认行为无变化；enabled而缺条件不得无保护调用模型；probe零数据库/网络 |
| V02 | 同call重复start/end/error、晚到更完整usage、真实新retry call | 消耗等于唯一物理调用事实之和；更完整替换，不产生双账；provider成本算法不变 |
| V03 | 新Run、同Thread历史、同Run多HumanMessage、图重建 | 只新native Run重置；Thread和消息数不能偷偷重置额度 |
| V04 | 79%/80%/99%/100%、跨阈值大响应、cache/reasoning/不同价格模型 | 只按统一total判断；remaining不负；真实超额保留；固定80%取整可执行 |
| V05 | create_deep_agent父子并行、readonly task重试、Workflow内层 | 一个cap；子图不各发新额度；请求数能证明阻止，root显示全树原因 |
| V06 | sync/async、retry/fallback、摘要、vision、memory | 每个新物理调用可被拒绝；隐藏调用不绕开；memory跳过不覆写已有回答；中断/取消保留 |
| V07 | 达限响应有工具/空回答/正常最后回答 | 不执行新副作用；自然最后回答不误标强停；不通过新增模型生成“总结” |
| V08 | 未恢复provider错误、专用预算异常、工具ValueError处理 | 预算错误不被当provider错误/参数失败，不fallback/重新delegate/Worker重排队 |
| V09 | HITL、审批ID、用户取消、工具cleanup、后续合法用户输入 | 预算不批准审批、不自动resume、不清busy；checkpoint配对不损坏，已保存成果保留 |
| V10 | missing/partial/invalid usage、失败带usage、ledger读写超时 | unknown不填0；启用预算后下一新增工作明确拒绝；预算关闭仅观测时fail-soft |
| V11 | 警告注入幂等、warning发送失败、旧Run迟到/回放 | 使用原system message保留blocks；custom发送失败不单独导致失败；确定性ID无串Run |
| V12 | 客户端context/config/input/state/update/command/resume伪造 | 私有额度对象/字段拒绝；公开单次max_tokens不能提升部署cap |
| V13 | API DTO可空旧行、恶意字段、无效Token/stop_code、JSON/SSE各槽位 | Zod/Pydantic一致；精确安全码，不泄provider正文/凭据/路径 |

拟新增 Runtime `tests/middlewares/test_token_budget.py`、`tests/runtime/test_token_budget.py`、`tests/durable/test_token_budget.py`；复用 `tests/support/BindableFakeMessagesChatModel`、既有 usage/lifecycle/retry/composition 测试与 API unittest，不重造测试框架。

### 集成、端到端与安全

| 编号 | 环境/步骤 | 通过条件 |
| --- | --- | --- |
| I01 | 隔离真实PG执行迁移两次；写同Run多call、重复/晚到事实，读摘要 | 旧查询不丢数据，重复不增额，策略不覆盖，旧行null |
| I02 | 隔离PG/Redis/API/Worker+受控provider，四正式graph、主子/Workflow | 触限停止后provider数不增、不重派Worker，root真实终态可查 |
| I03 | Worker退出/接管，同native Run继续；保留已完成和未确认started | 已用不清零；不明消费拒绝新增；不会按attempt重新给100000 |
| I04 | 用量落库失败、恢复、并行跨阈值、完成后迟到callback | 保留真实消费/unknown；已在途允许完成但无新派发，停止原因不被清掉 |
| I05 | 真实checkpoint：tool calls后触限、下一请求、HITL、取消 | 无悬挂/重复副作用；原interrupt ID有效；已有产物不删除 |
| I06 | 当前授权Run/Thread usage GET、事件过期后刷新/读旧Run | 精确预算stop_code仍可读；旧Run不套最新Thread.error |
| E01 | Platform API→Runtime API/Worker→主子模型→ledger→JSON/SSE/Usage GET | 同一次native Run的累计、stop、事件和查询一致；允许无Web先完成后端链路 |
| E02 | 三服务浏览器链路，同事按16进行80%预警、超额、unknown、切Run/刷新 | UI原因准确、cancel保留、不自动重发/追加额度；1440/768/390无重叠 |
| E03 | 授权真实provider任务，包含摘要/子Agent，记录实际usage字段 | 证明provider用量质量可用；不以fake替代，试验上限事先给定 |
| S01 | 两项目/两用户/撤权、伪造Run/Thread/cap/stop_code | ACL仍生效，不泄跨项目用量/预算，不新增权限 |
| S02 | 普通/Protocol/v3、tools/tasks/debug/checkpoint错误，canary正文 | 仅完整类型/机器码匹配；不从任意字符串含token字样分类；原正文不公开 |
| S03 | 开关/迁移缺条件、旁路、流式断开、没有usage的provider | 不误宣称严格费用保护，不额外购买/执行未知动作 |

### 性能与回退

- **P01：** 用同一fake provider/graph对照开关前后，记录100与1000次call、1/4/8个独立Run的P50/P95、SQL次数和峰值内存；不设未经批准SLO。单个Run受原调用/时间限额约束；内存随活跃call而非所有历史Run增长。
- **P02：** 证明不在每轮扫描整个Thread messages，关闭预算时无新budget SQL或网络访问；启用后的额外短事务和回调耗时有证据。不能用本地fake延迟声称生产时延达标。
- **B01：** 隔离环境暂停提交/drain后关闭预算，恢复原次数/步骤/时间限额和Usage观测；旧Token停止原因可读，扩展列/用量不删除。
- **B02：** 新旧Run/旧行查询和前端忽略未知字段；API/Web升级协同，无第二份Run终态，未完成Run不自动恢复执行。

### 实际验证命令

以下命令均在本轮对应服务隔离环境执行。集成 DSN 来自本次临时 PG（端口58141），HTTP stack 自行分配临时端口；测试已结束后不可直接复用该 DSN。

```bash
# apps/runtime-service
uv run --frozen --no-sync pytest -q tests/runtime/test_token_budget.py tests/middlewares/test_token_budget.py tests/runtime/test_runtime_config_validation.py tests/runtime/test_modeling.py tests/observability/test_usage.py tests/observability/test_usage_lifecycle.py tests/middlewares/test_execution_budget.py tests/services/test_execution_budget_composition.py tests/runtime/test_run_budget.py tests/services/reference_agent/test_middleware_order.py
USAGE_TEST_DSN="postgresql://postgres@127.0.0.1:58141/postgres" uv run --frozen --no-sync pytest -q tests/durable/test_token_budget_ledger.py tests/durable/test_usage_ledger.py -k 'not real_model and not performance'
TOOL_ERROR_PLATFORM_TEST=1 PLATFORM_API_TEST_PYTHON="/absolute/path/to/platform-api/.venv/bin/python" TOKEN_BUDGET_FIXTURE_PATH="/absolute/path/to/project/fixtures/token-budget-v1.json" TOKEN_BUDGET_EVIDENCE_PATH="/absolute/path/to/project/implementation/token-budget-backend-evidence.json" uv run --frozen --no-sync pytest -q tests/durable/test_token_budget.py
uv run --frozen --no-sync pytest -q -m 'not integration and not durable and not e2e' tests

# apps/platform-api
UV_OFFLINE=1 uv run --frozen --with pytest --no-sync python -m pytest -q tests/test_execution_budget_projection.py tests/test_run_usage.py tests/test_runtime_gateway_event_redaction.py
UV_OFFLINE=1 uv run --frozen --with pytest --no-sync python -m pytest -q tests
```

真实模型另显式提供 `TOKEN_BUDGET_REAL_MODEL_ENV_FILE` 和 evidence 路径，仅运行 `test_real_model_summary_and_child_report_usage`（Run cap4096，输出128，两次调用）。性能另以 `TOKEN_BUDGET_PERFORMANCE=1` 运行 `test_budget_performance_matrix`。改动 Python 文件执行 `uvx ruff check` 和 `uvx ruff format --check`；工具只是执行前缀，不写入文档命令。无环境 skip 不算通过。

收尾另执行 `pytest -q tests/runtime/test_runtime_config_validation.py`、`git diff --check`、仓库根 `python3 scripts/check_docs.py`；通过当前 Pydantic DTO/投影函数核对冻结 fixture，检查本次新增或修改的 Markdown 链接。全仓文档检查的基线失败与本次文件检查分开记录。

### 2026-10-09 规划阶段记录

- 已静态核对三仓实现、依赖锁、公开Context/错误/事件/Usage DTO和已有测试入口；已查询两个官方MCP。
- 当前能力覆盖与新缺口按本篇记录；已确认同事配置示例与实际源码的差异。
- 文档链接、拟改/现存路径、任务引用和仅文档改动检查见本次工具执行结果。
- **未运行**单元、PG、Worker、provider、E2E或性能测试；既有专项成绩仅为其历史证据，没有转换为F01成绩。

### Phase 验证记录

2026-10-09，使用 implement-feature/verify-change。以下八条分别对应八个已完成的非前端 Task；联合 Final 仍独立待前端。

| Task | 实际最短验证与结果 |
| --- | --- |
| T00 | Core1.6.0 sync桥接吞异步callback异常实测；附加同步仅检查守卫后 sync/async 物理请求计数不增。四图 Worker failure不重派；实际安装 LangChain1.3.17/Core1.6.0/LangGraph1.2.11/DeepAgents0.7.8/GraphHarbor双包post43。通过 |
| T01 | 真实PG两次upgrade、call幂等与更完整替换、同Run策略首写冻结、SIGKILL租约接管、unknown started、stop保留；旧HEAD源码在扩展库begin/finish/Usage读回通过 |
| T02 | 单唯一callback、safe integer聚合溢出、并发在途完成后新派发拒绝、隐藏summary/vision/memory、missing/partial/invalid与begin/read/upsert故障、关闭budget无新增恢复read。通过 |
| T03 | 四图16基础HTTP场景、Dear/Showcase child共用cap14、工具未新执行、retry/fallback保护异常不穿透、80%自然回答警告、writer失败幂等、memory耗尽跳过、HITL真实ID无override、取消无新增派发。通过 |
| T04 | 非法部署开关/cap、Usage/storage依赖（含on别名）、enabled缺可信身份拒绝；四图schema/probe无I/O且无私有额度；关闭开关仍Usage观测。通过 |
| T05 | API 61 passed /177 subtests；可空旧DTO、cross-field约束、安全数值、普通/Protocol/v3与递归tools.error安全码、私有伪造拒绝；两用户两项目、无效token、撤权真实HTTP。通过 |
| T06 | HTTP完整测试1 passed，内含30场景；7 Usage样本、3 notice、2error和DTO schema导出成功。真实DeepSeek摘要+child两次物理调用43 tokens、coverage=complete。通过 |
| T07-B | 最终Runtime定向157 passed/5个既有Swig告警；API安全回归61 passed/177 subtests；真实账本/兼容测试通过；12组性能矩阵（100/1000调用×1/4/8 Run×开关）通过。两服务全量基线失败如下面记录，F01非前端边界证据齐全；lint/format与文档一致性检查通过 |

完整HTTP最终命令使用 basetemp `/private/tmp/f01-token-budget-7604-20261009-f`，**1 passed /344.24秒**。证据：[30场景及真实HTTP样本](implementation/token-budget-backend-evidence.json)、[真实provider](implementation/token-budget-real-provider-evidence.json)、[性能12组](implementation/token-budget-performance-evidence.json)、[前端冻结fixture](fixtures/token-budget-v1.json)。证据不包含凭据或客户内容。

性能：1000次/1 Run 的 P50 46.988→48.281ms、P95 197.470→214.891ms；1000次/8 Run P95 896.754→942.655ms，峰值2,280,551→2,409,695 bytes。关闭budget新增恢复事务0；开启每Run只新增1次恢复短事务，既有开始/每call开始及完成/结束事务保持。基于本机共享负载和受控模型，不代表生产SLO，也不把事务数写成SQL statement数。

**全量回归未全绿，未计为通过：** Runtime 1008 passed、16 failed、81 skipped、58 deselected、1 teardown error；API 414 passed、37 failed、18 skipped、866 subtests passed。前者50分33秒，后者32分40秒。本轮F01定向测试未失败。

- API35项失败在临时 `git archive HEAD` 源码+旧测试中同样复现，均使用不合法的project UUID；剩余两项Workspace HTTP在低负载复跑后启动成功，转为已批准HTML/CSP放行与旧“无script”断言冲突。本轮未改其功能或测试。
- Runtime过期fetch_model_connection monkeypatch、Workspace钩子参数、ACL verify参数、局部取消和子任务等待问题在旧HEAD同样复现。模型恢复/主子收尾及Workflow重建6项在清除DB环境后新旧均为6 failed/8 passed/9 skipped，错误和断言一致。MCP启动超时、inbox默认外部PG连接/teardown为环境边界，本轮改动未触达其实现；不把skip当通过。
- 这些是全仓既有门禁问题，不扩展为F01开发任务；F01使用自建临时PG/Redis/真实Worker完成恢复、取消、ACL和主子路径，不依赖上述失败测试推断通过。未宣称仓库整体可直接合并/上线。

**收尾检查：** Runtime 24 个/API 6 个改动 Python 文件 Ruff check/format 全通过；配置校验重跑 17 passed（1.03秒），`git diff --check` 通过。冻结 fixture 与当前两个 DTO schemas、7 个样本、3 类通知、2 个安全错误一致；本次 13 份 Markdown 规范检查及 67 个新增/修改相关本地链接通过。全仓 `check_docs.py` 报 38 条绝对路径违规，来自 9 份未改文档，已逐行与旧 HEAD 核对一致，未计为全仓通过。F01 任务表仅 T07-F 及16前端任务/验收未勾选；本轮临时 PG（58141）已 fast stop 并收回会话，无遗留测试进程。

实施中修复：Core异步回调同步桥接不能拒绝；async守卫避免未await协程；HITL测试移除新context；冷导入启动窗口设测试专用600秒、lease改回60秒；fixture导出显式API源码路径/Run上下文；doctor on别名；关闭预算finish不引用新列。修复后定向、实际HTTP及导出均通过。实现细节见 [记录](implementation/21-f01-token-budget.md)。

### Final 验证记录

**三服务与真实模型联合 Final 验收已全绿闭环通过。** 2026-10-10，在本地隔离端口（Runtime 8125, Platform API 2145, Web 3005）及本地 PG/Redis 基础设施上完成前端与全链路联合验收：
1. **静态门禁**：`platform-web` 执行 Vitest（46 passed）、TypeScript `pnpm typecheck`（0 errors）、`pnpm lint`（0 errors）及 `pnpm build`（生产构建产物打包正常）。
2. **自动化端到端闭环**：Playwright + Chromium 执行 `apps/platform-web/e2e/token-budget-governance.spec.ts` 6 项专项测试全部通过（耗时 19.1s），涵盖：
   - 额度水位条与 Usage Meter 紧凑结合及 1440/768/390 多端响应式适配；
   - 在途硬停过渡态防抖、原生终态安全错误码映射及草稿输入框保护；
   - 用量不可确认安全防线（`usage_unverifiable`）；
   - 自然完成边界防误报（`used >= max` 但 `stop_code=null` 依然判定正常成功）；
   - 刷新页面后首屏单次静默对账恢复停机原因；
   - 真实三服务全链路驱动真实大模型（百炼 · qwen-plus）调用闭环，实测 23,969 Tokens / $0.0050 成功上屏与落盘。
3. **存证留存**：8 张关键路径全流程截图已在 `docs/projects/20260913-dearflow-agent/screenshots/` 归档。用户已于 2026-10-10 验收通过。


## 状态

**F01 done。** R00、T00—T06、T07-B、16/F-T01—F-T04 与 T07-F 联合浏览器验证全部完成。全链路覆盖 80% 预警、在途过渡态防抖、终态错误码精确分流、刷新单次静默对账闭环、自然完成边界防误报、Usage 水位条紧凑结合与 1440/768/390 多端响应式，并通过真实三服务和真实大模型（百炼·qwen-plus）端到端闭环验证。原 DearFlow 其他待办独立，不随 F01 扩大。默认关闭、未部署现役、未提交；在途可超额，unknown 拒绝新增，不承诺严格金额上限。

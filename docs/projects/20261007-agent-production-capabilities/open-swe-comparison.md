# 源码对照与同事方案辨析

## 事实来源

核对日期：2026-10-07。当前仓库和上游 checkout 的 HEAD 见 [README](README.md)。下表中的 `agent/` 和 `tests/` 路径属于用户指定的本机 open-swe checkout；当前项目路径均以仓库根为基准。本表的“当前/缺口”描述实施前基线，实施后状态见 [任务](tasks.md) 和 [验证](verification.md)。

参考 checkout 不是干净工作树：下表涉及的 prepare、task retry、server、dispatch、wakeup 和两份测试文件均有暂存但未提交的改动，`uv.lock` 处于未合并状态。本表描述当前本地文件的实际行为，不把这些行为归属到参考 HEAD 的已提交版本。该锁文件虽然可解析，版本信息仍不能作为上游稳定发布基线；本项目的实现依据是自己的锁定依赖、源码和验证。

| 资料 | 实际观察 |
| --- | --- |
| `agent/middleware/prepare_run.py:18`，`PrepareRunState` | `run_prepared`、`run_prepared_for`、工作目录及渲染后 prompt 进入图状态 |
| 同文件 `BasePrepareRunMiddleware.abefore_agent():54` | 指纹一致才跳过 `_prepare()`；成功后返回标记，随后由 LangGraph checkpoint |
| 同文件 `_latest_message_fingerprint():25`、`_prepare_fingerprint():75` | hash 包含最后一条消息的类型、ID、内容，中间件类名和子类提供的配置；不是单纯 `hash(last_message_id)` |
| `agent/server.py:651`，`PrepareAgentRunMiddleware._prepare_config_fingerprint()` | 实际子类还纳入 `invocation_id`、thread、模型、effort、repo、来源和业务模式 |
| 同文件 `_prepare():715` | 包含 GitHub token、sandbox ready、工作目录和发送人上下文等业务准备；不能整体移植 |
| `agent/dispatch.py:204`，`prepare_run_config()` | 分配/保留 invocation ID，绑定 v3 配置；`create_durable_run():223` 统一 sync durability、可恢复事件流和派发参数 |
| `agent/server.py:1309` | 使用官方 `ToolRetryMiddleware(max_retries=2, tools=["task"], retry_on=task_retry_on, on_failure=task_on_failure, initial_delay=1, max_delay=10)` |
| `agent/middleware/task_retry.py:62` | 判断 HTTP 状态及若干异常类型名称，包含 408/409/425/429/5xx/529 和传输错误 |
| 同文件 `task_on_failure():69` | 只返回 `invalid_prompt`、`context_length_exceeded` 或满足特定条件的 invalid request；其他错误 `raise exc` |
| `tests/agent/test_task_retry.py` | 测 predicate 与直接调用 failure helper；不能证明不可重试错误会经过 middleware 的 `on_failure` |
| `tests/middleware/test_prepare_run_middleware.py` | 测 latch、指纹改变、prompt 注入；还含业务发送人和缓存测试，移植时应剥离 |
| `agent/tools/schedule_thread_wakeup.py:22`、`:250` | 一次性 thread cron，用户消息代际计数，上限 10，thread metadata 持久化，进程内 asyncio.Lock，创建前先占预算 |

## prepare 的真实保证

```text
factory 构图及获取执行依赖
  -> before_agent 计算指纹
  -> _prepare 外部副作用
  -> 返回图状态更新
  -> checkpoint 成功
  -> 后续模型和工具执行
```

`BasePrepareRunMiddleware` 的 docstring 明说：如果失败发生在 checkpoint 之前，setup 会再次执行，因此 `_prepare()` 及其所有操作必须容忍重做。它是“已提交准备结果的复用”，不是外部事务。

三个不能忽略的边界：

1. factory 在 latch 之前执行；模型构造、授权、凭据查询和对象重建仍会发生。只在 state 增加两个字段不会减少 factory 里的工作。
2. `messages[-1]` 会随 AI 回复、ToolMessage、队列注入、摘要或恢复而变化；上游还依赖子类提供 invocation ID。仅最后消息 ID 无法可靠区分同 Run 重排和新 invocation。
3. checkpoint 里存在成功标记，不代表 sandbox、目录或进程内对象还在，更不代表身份、权限或凭据仍有效。跳过业务准备前仍须检查这些边界。

可借鉴的是独立的生命周期节点、稳定执行身份、成功后提交的标记、幂等资源操作和恢复验证。本项目不需要上游的通用 `work_dir`/`rendered_system_prompt` 字段：目录由当前 scoped backend 管理，静态 prompt 本来是纯配置。

## 当前项目已有能力及真实缺口

| 能力 | 当前代码证据 | 缺口/决定 |
| --- | --- | --- |
| 提交幂等 | `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py`，`RuntimeGatewayService.launch_runtime_run()`；`apps/platform-api/src/platform_api/modules/runtime_gateway/infra/sqlalchemy/models.py`，`RunRequestRecord` | 已有 key、摘要、submission、Run 关联与 unknown 恢复。不能用新的 invocation 表替代 |
| 同步 checkpoint | 同方法对 Reference/Showcase/DearFlow 强制 `durability="sync"` | 已有。扩展新 Agent 时按既有受管入口验收，不能称所有 demo 都默认获得该保证 |
| 配置/授权解析 | `apps/runtime-service/src/runtime_service/runtime/resolver.py`，`resolve_runtime_config()`、`runtime_context_hash()`；`middlewares/runtime_config.py`，`RuntimeConfigMiddleware._resolve()` | 大部分是纯计算或安全校验，不应被 prepare 标记跳过 |
| 模型连接 | `apps/runtime-service/src/runtime_service/runtime/modeling.py`，`fetch_model_connection()`、`build_model()` | factory 按 opaque ref GET 获取连接；是读取，不是已证明的“重复申请 token”。凭据必须新取，不进 state |
| Workspace prepare | `services/demo/showcase_demo/backend.py`，`_ThreadWorkspaceBackend.prepare()`：独占创建文件和 `.initialized`；`services/dearflow_agent/workspace/backend.py`，`DearWorkspaceBackend.prepare()`：目录创建 | 已有操作级幂等。缺少通用 checkpoint 标记/恢复检测；加 latch 后仍需防缺根和路径篡改 |
| Skills 执行快照 | `services/dearflow_agent/middleware/skills.py`，`ExecutionSkillsMiddleware._prepare()`、`_restore()` | 已有 task 身份、flock、原子 rename 和内容 hash。保持语义，不迁成最后消息 hash，不重复建快照机制 |
| 模型重试 | `services/reference_agent/agent.py`，`get_agent()` 中 `_runtime_model_retry` 测试适配分支 | 仅 Reference 显式测试分支；DearFlow/Showcase 没有统一生产策略 |
| SDK 内部重试 | `runtime/modeling.py` 未显式传 max_retries 时沿 SDK 默认；本机 OpenAI/Anthropic 默认为 2 次 retry | 当前不是“完全没有重试”。需要明确负责人和总尝试数，避免 SDK × model × task × Worker 放大 |
| 工具重试 | Reference 的 `ToolRetryMiddleware(tools=["read_reference"])` | 已有只读示例。生产图缺少按只读子角色筛选的 `task` 重试 |
| 错误反馈/安全 | `tools/errors.py`，`tool_error_content()`；生产组合根的 `ToolErrorMiddleware` | 已有。增加 task 专属的少量可恢复分类，禁止整图 catch-all |
| 调用限制 | DearFlow `ModelCallLimitMiddleware`、`ToolCallLimitMiddleware`、task 上限与 `DelegationConcurrencyMiddleware` | 已有。需验证物理尝试与逻辑调用的计数区别、重试取消和预算上界 |
| 模型超时/诊断 | `middlewares/model_call_timeout.py`；`observability/errors.py`、`diagnostics.py`、`query.py`；前端 Run Diagnostics | 已有。缺 prepare/retry 的有界、安全结果摘要 |
| Worker 恢复 | 安装的 GraphHarbor post41 `langgraph_runtime_pg/production_worker.py`，`_is_infrastructure_error()` 和失败分支 | 已有 lease/基础设施重排；builtin TimeoutError/ConnectionError/OSError 会触发。新增 Runtime 重试不能绕过此边界 |
| 定时执行 | Platform `modules/scheduled_tasks/service.py`；Runtime `runtime/scheduled.py`，`scheduled_execution()` | 已有受权 once/cron/manual；没有 Agent 自主唤醒工具，不需要现在加自唤醒计数 |

表中 `services/`、`runtime/`、`middlewares/`、`tools/`、`observability/` 均位于 `apps/runtime-service/src/runtime_service/`。GraphHarbor 观察来自主 checkout 同版本虚拟环境，未改外部包。

## 同事方案逐项判断

| 建议 | 判断 | 本项目采用方式 |
| --- | --- | --- |
| state 存 prepare 完成标记 | 采纳思想，调整结构 | 私有、有界的 component -> fingerprint 映射；单条记录即可表达已完成，不再重复 bool |
| 指纹为最后消息 ID + config hash | 不足 | 可信 Run 身份 + tenant/project/thread/graph + 作用域 namespace + component + 当前 config_hash/prepare revision；不以最后消息作为唯一身份 |
| 所有副作用、配置读取统一搬进 `_prepare()` | 部分采纳 | 可复用的幂等资源准备进入 hook；factory 授权、连接读取、模型/MCP 装配和实例重建保留；纯渲染不为 latch 搬动 |
| 同 invocation crash retry 自动跳过 | 有条件成立 | 仅已提交 checkpoint 且外部资源有效时；未提交窗口靠操作级幂等，恢复语义靠真实 worker 测试证明 |
| 所有 dispatch Run 配置 retry_policy | 不采纳 | 当前 dispatch 是服务端 Runs API。LangGraph `RetryPolicy` 是 node/task 配置，上游实际用 ToolRetry；本期不重放整个 Run |
| 所有 409/425/5xx 或同名异常可重试 | 收窄 | typed provider/transport 正向白名单；409/425 需要具体 provider 协议证据，未知异常/状态不自动重试 |
| 所有不可重试异常转 ToolMessage JSON | 不采纳 | 仅已声明的安全只读 task 可反馈受信 provider 的 context/prompt 可修复错误或 transient 耗尽；写角色、授权/资源/中断/取消/未知错误继续终止或传播 |
| retry 的 on_failure 处理不可重试错误 | 与锁定版本不符 | LangChain 1.3.17 非匹配异常立即抛出，不执行 on_failure。可修复错误由 retry 外层现有 ToolErrorMiddleware 处理 |
| 自唤醒上限 10 | 条件性借鉴 | 当前 deferred。未来上限由评审决定；不能直接复制进程锁 + metadata 读改写用于多 Worker 原子预算 |

## 为什么不能对所有 task 开重试

DearFlow 的 `researcher()` 函数定义的实际角色名是 `general-purpose`，它只提供研究/读取工具，可以作为接入样本。Showcase 的 `research` 只读，但它自己的 `general-purpose` 可以写文件、执行命令，`chart-agent` 会调用外部图表工具。不能跨 graph 按同名角色或父工具 `task` 给相同策略；必须核对代码声明的完整工具闭包。

一个子 Agent 写出文件后，下一次模型调用 429：重试模型调用不重放已执行的工具；重试整个 task 可能重做写入。checkpoint 能否复用子图进度还受实际 task 调用、namespace 和 pending writes 影响，必须测试，不能以“LangGraph 有 checkpoint”替代证明。

同一个错误的显示分类与可重试裁决也应分开。当前 `observability.errors.classify_exception()` 有文本兜底，适合安全摘要；不应把含有“rate_limit”的任意程序错误变成自动重试依据。

## 官方文档与版本核验

已查询 `langchain-docs` 和 `langchain-reference` MCP，并与安装源码核对：

- [Tool retry](https://docs.langchain.com/oss/python/langchain/middleware/built-in#tool-retry)：重试次数不含首次；非匹配异常绕过 `on_failure`；默认可重试范围比本项目允许的范围宽。
- [ToolRetryMiddleware API](https://reference.langchain.com/python/langchain/agents/middleware/tool_retry/ToolRetryMiddleware)：复用退避、抖动、取消和 ToolMessage 构造。
- [LangGraph RetryPolicy](https://reference.langchain.com/python/langgraph/types/RetryPolicy) 与 [task](https://reference.langchain.com/python/langgraph/func/task)：node/task 能力，不能当成 Runs API 的 dispatch 参数。
- [Durable execution](https://docs.langchain.com/oss/python/langgraph/durable-execution) 与 [durability modes](https://docs.langchain.com/oss/python/langgraph/checkpointers#durability-modes)：sync checkpoint 不能把外部副作用和图状态变成同一事务。
- [Deep Agents fault tolerance](https://docs.langchain.com/oss/python/deepagents/fault-tolerance#retries)：按模型调用、明确工具配置重试，避免给所有工具统一重试。

本项目锁定 LangChain 1.3.17、LangGraph 1.2.11、DeepAgents 0.7.8、GraphHarbor post41；参考 checkout 当前可解析但未合并的锁文件包含 LangChain 1.3.18、DeepAgents 0.7.13，仅用于识别版本差异。本期不为迁入模式升级核心依赖，后续开发以当前锁定源码和测试为准。

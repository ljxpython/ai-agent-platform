# Runtime 安全原因与通用 Agent 接入

> 已批准并实现；平台依赖正式 `graphharbor==0.13.0.post44`。实施进度仅维护在 [tasks.md](tasks.md)，验收见 [verification.md](verification.md)。

原生 webhook、顶层字段过滤、通用错误序列化和发送配置由 GraphHarbor 实现；Runtime 提供应用安全分类。[官方核对](07-langgraph-server-boundary.md) 未发现 `terminal projector` 标准 hook，本期实现的是已批准的通用扩展。

## Runtime 负责什么

基础 completion 在所有图共用的引擎层启用；Runtime 提供受信来源与安全失败投影。新 Agent 注册后无需增加“通知 Tool”或 after_agent 才能收到基础通知。模型 Middleware 可以提供更细原因，但不是可靠送达的前提。

`apps/runtime-service/src/runtime_service/run_completion/projector.py::project_terminal_outcome(exc: BaseException)` 是 Runtime 所有的纯函数，通过引擎启动期 callable hook 装配；输入为最终异常，输出仅 reason_code/model_error_code。引擎自己决定 final status/reason 并处理 timeout/success/interrupted，不向 projector 传入整份 State。不得访问网络、Langfuse、平台数据库或逐 Agent 工具。

GraphHarbor 的 hook、固定受管目标、私有来源与独立 Outbox 已在 post44 发布，详见 [引擎交接](03-engine-terminal-delivery.md)。基础投递仍由引擎负责，Middleware 只增加精细分类。

## 最终原因的提取规则

1. 引擎最终 `timeout` 优先于任意旧模型错误，原因映射为 `runtime_run_timeout`。
2. 引擎 `success` 没有失败码，即使前面的模型 retry/fallback 曾出错。
3. `interrupted + hitl_interrupt/cancel_requested/rollback` 不生成失败通知；只有真正停止/提交之后才写 completion。
4. Runtime 已知类型的稳定 `.code` 优先，未知异常只输出 `runtime_execution_failed`。
5. 模型调用现场可以复用 `classify_exception` 提取安全分类，但不得在全图异常上无条件调用：未知工具/工厂异常不能全部归类成模型失败。
6. `RuntimeResolutionError` 在 resilience 路径故意在 except 外抛出，避免保留 provider 上下文。如补细分类，只附 allowlist 字符串 `model_error_code`，不恢复原始 cause/context。
7. 可选细分类只来自导致最终退出的模型 invocation；必须与最终 Runtime 稳定码相容。暂存“最后模型错误”、子图回调和 Thread.error 均不能覆盖本次最终结果。
8. 已被 ToolMessage 转成可恢复结果、被子图处理后根图成功的异常，不生成独立 Run 失败通知。独立入队的子 Run 才有自己的 completion。

## 字段与白名单

内部 v1 分开 `reason_code`（运行最终安全码）和 `model_error_code`（可空 provider/context 分类）；前端展示优先看 status，再看 reason_code，再看可用细分类。不要拿 provider timeout 伪装成 Worker 超时。

| 来源 | `reason_code` | `model_error_code` |
| --- | --- | --- |
| `RuntimeModelRetryMiddleware._raise` | runtime_execution_failed | provider_rate_limited / provider_overloaded / provider_timeout / provider_unavailable / provider_auth_failed / provider_access_denied / context_too_long / model_unavailable / model_call_failed |
| ModelResilience 最终失败 | runtime.model.retry_exhausted / runtime.model.retry_budget_exceeded / runtime.model.stream_interrupted / runtime.model.provider_rejected / runtime.model.fallback_incompatible | 仅现场可提取时为上述 9 个分类，其他 null |
| Worker hard timeout | runtime_run_timeout | null |
| 已有预算/步骤限制 | runtime_graph_step_limit_reached / runtime_model_call_limit_reached / runtime_tool_call_limit_reached | null |
| Workspace | runtime.workspace.unavailable / runtime.workspace.execution_unavailable / runtime.workspace.backend_invalid / runtime.workspace.image_invalid / runtime.workspace.execution_outcome_unknown | null |
| 已有明确 Runtime 认证/配置错误 | 当前已有 code 经显式逐条批准后纳入，否则兜底 | null |
| 未知 graph/factory/infrastructure 错误 | runtime_execution_failed | null |

现有字符串白名单是起点；实施前以 `observability/errors.py`、`runtime/errors.py`、API `sdk_client.py::project_execution_error` 和真实 Worker 的限制 payload 核对。不要通过宽泛 `runtime.*` 前缀让任意错误字符串成为公开码。前端现有在线错误出口仍使用现有契约，completion 新投影不能静默改变它。

## 可信来源

API 在 dispatch 前持久化 `origin_ref`。Runtime 只从已验签 delegation 的新增可选 claim / 受签名的定时任务标记接受它，装入引擎可信 runtime_context 的固定 `callback_context={"origin_ref": "..."}`。

- 浏览器 context/config/metadata/header 不得伪造来源；来源不进入普通 State、Prompt、tool input、Run 公共 kwargs 或 SSE。
- API 的 JWT claims 严格白名单与 Runtime 对称解析都需调整；新增 claim 是安全契约变更，必须人工批准、旧/新版本矩阵验证。
- 已受理 Run 保存的是来源验收事实；completion 不重新验证早已过期的启动 JWT，也不因通知故障取消 Agent。
- 定时任务 fresh/reuse、手动执行、schedule 更新和删除需完整覆盖；cron 在 factory 前就必须带可信来源，不能等 `scheduled_execution` 成功后才获得。
- 裸 StateGraph 不需模型 Middleware；schema 获取、one-shot suggestions 和请求尚未受理的 HTTP 错误不创建虚假 Run completion。

## 预计代码位置

以下 `.../` 均指 `apps/runtime-service/src/runtime_service/`；新文件/函数为建议落点，现有函数为核对后的入口。

| 文件 | 具体动作 |
| --- | --- |
| `.../run_completion/projector.py`（新） | pure safe projector、固定返回 schema、未知异常兜底 |
| `.../runtime/errors.py` | 如有必要给已有安全错误增加可空 `model_error_code`；不改变继承/重试语义 |
| `.../middlewares/model_resilience.py::ModelResilienceMiddleware.awrap_model_call`、`ModelResilienceSummarizationMiddleware.awrap_model_call` | 在清除 provider context 前提取最终安全细分类 |
| `.../middlewares/retry.py::RuntimeModelRetryMiddleware._raise` | 复用现有稳定 code，定向回归，不增加第二套 retry |
| `.../runtime/auth.py::verify_delegation_claims`、`VerifiedDelegation` | 新增受签 claim 与严格解析；旧无 claim 仍可正常执行 |
| `.../auth/platform.py::authenticate` | 将 verified origin 作为私有受信事实交给引擎 admission |
| `.../runtime/scheduled.py::scheduled_execution` | 保留现有执行授权和 report；定时来源在 admission/cron 分发时已验收 |
| `apps/runtime-service/langgraph.json`、引擎 Worker 启动配置、`apps/runtime-service/deploy/` | 装配全局 projector 与固定 callback 目标；包括 Worker/reaper/API 各进程 |
| `apps/runtime-service/pyproject.toml`、`apps/runtime-service/uv.lock` | 人工批准外部包后同步正式依赖来源和锁 |

`ModelErrorMiddleware._record` 可以继续做观测；本期不要求给它增加数据库写入。Runtime 自有 app schema 与引擎 schema 分离；推荐方案仅引擎 Outbox + API 收件箱，不再加 Runtime 第二份 Outbox/relay。

## 各 Agent 怎么接入

| Agent 类型 | 基础 completion | 细粒度原因 | 需改组合根吗 |
| --- | --- | --- | --- |
| Showcase / Reference / DearFlow | 共享 admission + 引擎终态自动覆盖 | 复用现有模型/Workspace middleware | 原则上不需要，为真实组合补定向验证 |
| 最小自定义 StateGraph | 同上 | 未知错误使用兜底码 | 不增加通知 Tool |
| 自定义 create_agent/create_deep_agent | 同上 | 选择现有错误/resilience middleware，最终使用安全异常 | 按现有 `agent.py` 唯一组合根显式装配 |
| schema/skills/catalog 查询 | 不产生 Run，不通知 | 不适用 | 不修改 |
| 未配置受管来源的裸 Runtime 调用 | 不进入平台私有通知 | 保留引擎状态/诊断 | 明确能力未启用，不能伪造平台 recipient |

验收必须证明：不开 Langfuse、不装 ModelErrorMiddleware、factory 前失败、Worker 重启/lease 过期时仍能产出基础 completion；通知基础能力不能退化成“这三个 Agent 接了才有”。

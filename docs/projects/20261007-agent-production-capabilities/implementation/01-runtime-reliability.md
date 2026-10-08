# Runtime 准备与重试能力

日期：2026-10-07；关联 T01—T09、T11/T12。用户已批准实施，前端不在本轮范围。进度以 [tasks.md](../tasks.md) 为准。

`apps/runtime-service/src/runtime_service/middlewares/run_prepare.py` 提供 `RunPrepareMiddleware`：授权校验和资源检查在 latch 外，可信 Run/scope/namespace/config/revision 生成 SHA-256；成功后写私有、最多 16 组件的映射。`PrivateStateAttr` 排在 reducer 前，符合当前 LangGraph 只读取最后一个 reducer 的约定。middleware 名称带组件名，允许同图多组件。此标记只避免已提交准备步骤重做，外部副作用仍要求幂等。

两个 workspace backend 的 `WorkspaceMiddleware` 继承公共能力，`is_prepared()` 检查根、必需目录和 Showcase marker；缺资源可幂等补齐，symlink/非预期文件类型拒绝。Showcase seed 继续使用独占创建，不覆盖用户文件。factory 仍每次解析授权、模型配置与凭据。

`middlewares/retry.py` 继承官方 `ModelRetryMiddleware`/`ToolRetryMiddleware`，使用 typed 瞬时错误白名单，最多首次加一次重试；callbacks 按调用 ContextVar 标记 content/reasoning/tool delta，出流后禁止重放。只读子任务由父 task 负责，子模型不叠预算。主模型和写子图仅重试当前模型请求。取消和图中断原样传播，provider 最终失败封装安全 `RuntimeExecutionError`，避免 Worker 将模型超时当基础设施重排。

DearFlow 只读角色是 `general-purpose`，Showcase 是 `research`；两组合根显式 SDK `max_retries=0`。DearFlow 记忆/技能需要辅助模型时单独保留既有 SDK 策略。Reference 沿用原接线。

`observability/diagnostics.py`/`query.py` 复用事件白名单和有界查询，新增准备/重试摘要；不增加 SSE 控制事件。`tools/errors.py` 只为已声明只读 task 的上下文错误提供安全反馈，写角色/未知/权限失败传播。

Platform `core/runtime_contract.py` 将 `runtime_prepare` 加入共享保留字段集合，`sdk_client.py` 公开投影剥离该字段，并保留正常 ToolMessage artifact。`application/diagnostics.py` 增加两个可选 DTO，使用 Literal/严格数值/长度上限，不新增查询或运行控制 endpoint；`tests/test_run_diagnostics.py` 覆盖旧响应、安全投影和数值边界。

`tests/fixtures/run_reliability.py` 和 `tests/e2e/test_run_reliability.py` 复用现有 Platform/Worker fixture。fixture 改用本机 PostgreSQL/Redis 可执行文件，自行创建临时数据目录和端口。故障注入仍使用真实生产工厂/Worker，合成 HTTP provider 精确计数，观测查询经真实 Langfuse SDK 访问受控 HTTP 端点。

已执行最小重试行为集及扩大回归，覆盖 typed 状态矩阵、sync/async、预算/取消、只读角色、真实 v3 三种 delta 首次及第二次失败。prepare 多组件测试暴露的 reducer 注解顺序问题已修正；SDK 参数改变影响 DearFlow 记忆/技能共享模型的问题通过独立辅助模型保留原策略解决。HTTP provider、两个 crash 窗口、真实 PG 故障、审批、取消、Run deadline 和旧新代码回退证据见 [verification.md](../verification.md)。

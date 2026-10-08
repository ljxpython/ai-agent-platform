# Runtime 执行边界与公开契约

## 改动时间与范围

2026-10-07；T01、T02、T10-T12、T20-T21。用户已批准，前端不在本轮实施范围。

## 代码变更

- `apps/runtime-service/src/runtime_service/workspace/execution.py:execute_in_workspace()`：单次 Docker 命令；仅 exit125 时一次只读 2 秒逻辑预算健康探测。读取/等待失败转稳定 Workspace 异常；创建与消费共用客户端 deadline；取消与故障清理只操作本次已知容器和 CLI 进程。创建中的任务有界收敛，迟到进程按原任务回收，目录/文件不删除。
- 同文件 `_cleanup()/_shield_cleanup()`：清理未确认标记结果未知；重复取消仍保留取消控制流；清理日志与观测失败不能替换主结果。
- 同文件 `_docker_control()`：健康探测要求退出码 0 且固定 ServerVersion 非空。真实 Docker CLI 在不可达 socket 上可能以 0 退出但模板为空，已修正只按退出码的误判；stdout 仅用于该判断，stderr 丢弃，不进入诊断或错误出口。
- `apps/runtime-service/src/runtime_service/runtime/errors.py:workspace_error_code()`：只接受实际 RuntimeWorkspaceError 和五个有限码；顶层仍是 RuntimeError，避免 Worker 的 OSError/TimeoutError 基础设施分类重调度整个 Run。
- `apps/runtime-service/src/runtime_service/observability/diagnostics.py:workspace_execution_fields()`：一个共享字段验证入口，供 callback 与 query 复用；禁止命令、路径、原始 stderr 与身份覆盖。
- `apps/runtime-service/src/runtime_service/observability/langfuse.py:_RuntimeDiagnosticsCallback`：接收固定 custom event，作用域来自自身 metadata；graph/tool 错误记录有限 Workspace code。
- `apps/runtime-service/src/runtime_service/observability/startup.py:StartupDiagnostics.phase()/finish()`：可信 Workspace factory 错误附加有限 code，不造命令执行次数。
- `apps/runtime-service/src/runtime_service/observability/query.py:_project()/empty_diagnostics()`：增 workspace_executions，上限20；保持查询预算、schema/event 与精确五元作用域。
- `apps/platform-api/src/platform_api/adapters/langgraph/sdk_client.py:project_execution_error()`：精确 Worker 类型/message 或已投影的安全形状；对象和字符串保持形状、幂等。通用码统一 runtime.execution_failed；HTTP Envelope 独立。
- `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py:_redact_sse_frame()`：tasks 与 lifecycle 复用既有错误槽位出口，保留正常工具内容、seq 和 namespace。
- `apps/platform-api/src/platform_api/modules/runtime_gateway/application/diagnostics.py`：WorkspaceExecution 与 ExecutionErrorCode；version1 增量可选数组，旧响应默认空数组，model_errors 保持模型专用。

## 关键前后差异

原来 Docker125 一律作为普通工具结果，读取故障可能以 OSError 到达 Worker，tasks.error 的私有异常可能透出。现在只有125且环境健康不可确认时停止并报告 unknown；read/wait 故障稳定传播；公开错误槽位精确白名单。普通 exit7/125（环境健康）和已确认超时保持原语义。

当前后端没有自动 transient retry。真实 CPython 子进程测试在 connect_read_pipe 接线阶段注入 EAGAIN，已经完成文件副作用后，公共 create_subprocess_exec 仍然抛同样异常；创建前 fork 失败无副作用。二者没有可供当前公共调用者可靠区分的来源类型，因此选择批准分支 B。测试为避免 CPython 失败接线的内部 wait 竞态，在失败接线返回前确认该测试子进程退出；生产没有依赖私有事件循环 API。

## 验证进展

- API 定向：53 passed、116 subtests passed；包含可选 v1、精确码/幂等、分片 ordinary/Protocol/v3、错误槽位与字段拒绝。
- Runtime 最小组合：45 passed、2 deselected；包含真实创建前/后副作用证据、callback/query/startup、Showcase 主/子图 Workspace fatal 与 HITL 后只执行一次。
- Docker 执行定向：2 passed、23 deselected；真实非零、超时、exit125、结果未知与取消保留文件/无迟到副作用。
- 创建 deadline/有界收敛、重复取消、探测零退出码假健康已补验证：执行定向32 passed、3 deselected；真实不可达 daemon1 passed，目录与原文件保留、无宿主执行。
- HTTP/Worker fixture 首轮因双参数工厂违反 GraphHarbor factory 签名失败，已改 keyword-only；次轮证明 Dear execute 本身也需要 HITL，不以 ultra 绕过，测试已改为真实 approve/resume。后续结果在 verification.md 记录。

本记录只说明实现细节，进度以 tasks.md 为准；综合证据和最终结论分别见 implementation/03-chain-validation.md 与 verification.md。

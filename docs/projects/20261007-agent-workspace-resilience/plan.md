# 整体方案

> 2026-10-07 用户已批准，按 G0 与 G1 分支 B 实施。本轮非前端本地与 Docker 范围 done；整体 partial 仅对应前端 T23 移交。自动 retry 按批准 G1 分支 B deferred，当前命令单次执行。进度见 [任务](tasks.md) 和 [验证](verification.md)。

> 最新授权的 T32/T33 已完成：真实容器、HTTP/Worker、性能测量和资源回收已验，Docker Desktop 已关闭。此前的本地 Final 保留为独立历史阶段；真实副作用证据复核后仍维持 G1 分支 B，不将 Docker 可用解释为可安全重试。

## 目标与验收底线

保证副作用命令不会因本能力被重复执行；可信启动失败可以有界恢复；Workspace 不可用或执行结果未知时停止当前 Run，并让用户看到安全说明。所有具备 Workspace execute 的 Agent 复用同一执行边界，权限和 HITL 保持现有事实来源。

必须同时满足：未启动的可靠 transient 才能重试；已启动/未知最多提交一次；控制流异常不被吞；不重新创建或替换执行中的工作区；诊断服务不可用仍可正常报告失败；公开输出无异常正文、凭据、宿主路径；原生 Run 状态不被改为 success。

## 三层职责与调用链

```text
Web：官方 SDK / 原生 Run 状态 + 安全提示 + RunDiagnostics 展示
  -> API：授权、精确错误投影、DTO 校验、原流事件结构
    -> Runtime：现有 WorkspaceMiddleware 校验可信 scope
      -> 所属 Agent backend.aexecute()
        -> shared workspace.execute_in_workspace()
          -> 可靠启动边界 / 有界诊断探测 / 一次命令 / 清理
      -> RuntimeWorkspaceError -> GraphHarbor 原生失败终态
      -> 既有 diagnostics callback / startup -> 安全日志与 Langfuse
  <- 既有 SSE error/lifecycle/tasks 与授权 diagnostics GET
```

| 工作 | Runtime | API | 前端 |
| --- | --- | --- | --- |
| transient 类型与命令阶段判定 | 负责 | 不猜测 | 不猜测 |
| 退避、取消与副作用保护 | 负责 | 不重发 Run | 不重发命令/Run |
| Run 终态 | 异常传播给原生 Runtime/Worker | 保留原状态 | 官方 SDK 为事实 |
| 错误解释 | 产生有限机器码 | 精确白名单投影 | 本地固定文案映射 |
| 诊断 | 安全采集 | 授权与 DTO 白名单 | 既有面板展示 |
| 权限 | 可信 Delegation + scope | 项目/Thread/Run ACL | 复用既有作用域清理 |

不加新表、Graph 注册、API route、JWT operation 或浏览器执行配置。既有 PTY/文件管理 HTTP 不纳入命令重放范围。

## Phase 0：实施前基线与可靠启动证据

### G0：安全出口与通用错误码

API worktree 基线存在 `tasks.error` 脱敏问题，以及测试/工具容错文档和代码的通用失败码差异。2026-10-07 用户批准本方案后，在该 worktree 补齐 tasks 安全投影，并按已有工具容错测试/交接统一为 `runtime.execution_failed`。对象保留固定 `Runtime execution failed` message，字符串使用稳定码；HTTP Envelope 不变。批准与实施证据见 implementation/01-review-and-start-boundary.md。

G0 之后必须有 ordinary/Protocol/v3 的真实安全样例，覆盖生命周期、原生 tasks、debug task_result、Thread/Run/state/history。已有控制流、正常工具正文、event/id/seq 保持保真。这是新 Workspace 投影的前置任务。

### G1：EAGAIN 是否真的发生在命令启动前

候选只有 POSIX fork/exec 创建失败的 `errno.EAGAIN`，不是任意 await 阶段的 EAGAIN。`asyncio.create_subprocess_exec()` 在内部可能先创建进程再接线输出管道；函数抛错或还没返回 process 不能单独证明命令未运行。

实施前做小规模证据检查，核对部署 Python/OS 的 CPython `subprocess`、`asyncio` 实际路径：

1. 错误来源能否限定为 fork/exec 未成功的创建阶段；是否可能来自创建后的输出管道/异步传输阶段。
2. 使用可计数副作用测试，区分“创建前失败”“已创建但管道接线失败”“进程已启动后等待失败”。只 monkeypatch 整个 create_subprocess 函数返回 EAGAIN 不足以证明真实边界。
3. 证明取消清理能回收创建中的进程，错误保持类型化来源且不依赖 traceback/错误文字分类。

**分支 A：证据成立且最小改动可捕获来源。** 仅在这一可靠创建边界实现窄重试。最多 4 次总尝试，最多等待 3 次，具体实现与证据附在 implementation 记录中。

**分支 B：现有 asyncio 接口不能可靠区分。** Docker/local 继续 1 次命令尝试；本期完成失败报告、不可达诊断与观测，将“当前后端启动 transient retry”标为 deferred。不能为追求 4 次重试重写 subprocess 框架或引入私有事件循环 API；未来真实云 SDK 提供“execute frame 未发送”信号时再实现 provider 重试。

2026-10-07 用户批准后执行真实子进程证据检查，选择分支 B：当前后端单次命令执行，自动 transient retry deferred。接线 EAGAIN 已能发生在副作用写入之后，不引入私有事件循环 API 来识别来源。

## 执行分类与重试策略

| 失败来源/阶段 | 能否重试命令 | 处置 |
| --- | --- | --- |
| G1 证明的创建前 EAGAIN | 仅 G1 通过时可以 | 窄边界最多 4 次总尝试；耗尽后稳定失败 |
| EACCES/EPERM、ENOENT、ENOSPC、ENOMEM、文件锁 | 不可以 | 单次失败，不当作权限“瞬时”异常，不换环境 |
| 根目录不存在/符号链接/作用域不符 | 不可以 | 现有 Workspace/Auth 异常；停止、保留原文件，不执行中 prepare |
| Docker CLI 创建成功、返回普通非零值 | 不可以 | 正常 ExecuteResponse，不对返回值做整工具重试 |
| Docker exit 125，环境探测正常 | 不可以 | 保留 ExecuteResponse125，可能是用户命令主动返回 |
| Docker exit 125，环境探测失败/超时 | 不可以 | 结果未知、清理已知容器、稳定异常停止 Run；不能声称命令没开始 |
| stdout/read/wait 的执行期 OS/连接错误 | 不可以 | 结果未知，最佳努力清理，RuntimeWorkspaceError 顶层传播 |
| timeout 124/137 或客户端等待超时且清理确认完成 | 不可以 | 保留既有 ExecuteResponse/超时语义，不重跑 |
| 超时且清理未确认完成 | 不可以 | 结果未知并停止；不宣称执行已成功停止 |
| 用户取消、GraphBubbleUp/HITL、服务 drain | 不可以 | 保留原控制流，诊断不能替换它 |
| 未知编程错误、混合 ExceptionGroup | 不可以 | 保持现有异常传播和通用安全出口；不递归搜 cause 猜 transient |

仅分支 A 才采用标准库 `asyncio.sleep()`、`random.uniform()` 和固定常量：总尝试 4、base 0.5 秒、jitter ±20%、cap 8 秒。当前选择分支 B，不实现等待与重试抽象。

分支 A 后续实施时，成功路径不 sleep，最后失败不 sleep，等待时取消不得启动下一次；计划等待最多 4.2 秒，实际调度耗时另记。当前分支 B 没有退避等待。命令创建与消费共用客户端 deadline，外层 Run deadline 仍有效。

## Docker 不可达与结果未知

基线 Docker daemon 不可达会作为 ExecuteResponse125 返回。本期仅在 exit 125 路径增加固定、只读、最多一次的 Docker 可用性探测：`docker info --format '{{.ServerVersion}}'`。

- 使用与执行相同的可信 Docker 上下文；参数固定，不包含用户 command、路径或模型输入，不启用自动 local fallback。
- 只读取固定 ServerVersion 模板的 stdout，要求退出码为 0 且值非空；不记录或公开该值，stderr 丢弃，不按错误文本识别。Docker CLI 在 daemon 不可达时该模板可能仍返回 0，因此不能只检查退出码。探测逻辑预算 2 秒，结束或取消后有界回收进程，清理额外耗时独立，不承诺整个故障处理仅 2 秒。
- 探测成功：原命令结果保留。探测不能证明前一命令的历史结果，不补造“未启动”。
- 探测失败、启动失败或超时：当前环境可用性不可确认，前一命令结果标为 unknown；按已知容器名做有界最佳努力清理，停止 Run。
- 不对所有命令预检，不做循环健康检查或全局熔断，不通过探测重新执行原命令。
- 其他非零退出码不改写为基础设施故障；未来 provider 的明确基础设施错误可以另行精确接入。

该方案有明确边界：环境恰好在用户命令主动 exit125 后失效，也会被保守报告 unknown；Docker CLI 使用其他退出码报告基础设施故障时，本期不会从文本猜测。这是比自动重放更可控的选择，必须在评审和验证中保留这一限制。

## 异常与清理

复用 `runtime/errors.py:RuntimeWorkspaceError(RuntimeError)`。稳定 `code` 仍是异常公开字符串，cause/原始 stderr 只供受控本地排障，不进入公开错误或新增诊断字段。

| 稳定码 | 来源 | 拟议固定说明 |
| --- | --- | --- |
| `runtime.workspace.unavailable` | 现有，根/资源不可用 | 工作区暂不可用，本次运行已停止。 |
| `runtime.workspace.execution_unavailable` | 现有，执行器不可用 | 执行环境暂不可用，本次运行已停止。 |
| `runtime.workspace.backend_invalid` | 现有，后端配置不合法 | 工作区执行配置不可用。 |
| `runtime.workspace.image_invalid` | 现有，镜像参数不合法 | 工作区执行配置不可用。 |
| `runtime.workspace.execution_outcome_unknown` | 新增，执行结果/清理不确定 | 命令执行结果尚不确定，本次运行已停止，请先核对工作区结果。 |

`RuntimeAuthError("runtime.workspace.scope_mismatch")`、Showcase 的 `runtime.workspace.invalid_backend` 等既有权限/构造策略仍走原错误链路，不混入自动重试白名单。参数 ValueError 与普通工具错误也不扩大处理集合。

执行期仅将已识别 OS/连接故障转成稳定 Workspace 顶层异常，避免 GraphHarbor 将其当作 infrastructure 重调度整次 Run。不遍历 `__cause__` 做通用重试。G1 前无法证明未启动的创建错误，也不得使用“命令未开始”文案。

保留既有取消/超时清理：docker rm、进程 kill/wait、shield。补齐 reader 失败和 exit125 探测失败路径，确保只有已经创建的进程才进入清理。清理失败不能覆盖原 CancelledError/GraphBubbleUp；超时未确认回收时用 outcome_unknown，不返回令人误以为已停止的确定超时结果。清理观测失败也不替换主异常。

本期只清理该次执行创建的容器/进程，不删除挂载目录、产物、skills 或其他 Thread 的资源。

## API 错误槽位投影

使用 `sdk_client.py:project_execution_error()` 一个共享出口扩精确映射，保持字符串/对象的既有形状。

- 原生 Worker 对象通常为 `{"type":"RuntimeWorkspaceError","message":"<稳定码>"}`，不保证携带 `code`。必须覆盖这个真实来源。
- 字符串只接受与白名单稳定码完全相等的值；对象接受严格验证的类型与稳定码，或已经投影的安全形状。不得 substring、regex 抽码或把任意 exception message 当公开说明。
- 投影须幂等：重复经过 Run/Thread/stream 的公共出口不丢失已经验证的 Workspace 码。
- Workspace 对象仅保留 `code`、固定 `message` 与经过白名单处理的 `type/error`；字符串保持字符串，输出稳定码供 Web 精确映射。
- 未知错误继续通用安全 fallback；批准后的对象 code/字符串统一 `runtime.execution_failed`，对象 message 为固定 `Runtime execution failed`。

覆盖 `_redact_sse_frame()` 的普通 error/lifecycle、Protocol/v3 lifecycle、原生 tasks、debug.task_result 及 resource/state/history 的 `tasks[].error`。不改 event/id/seq/namespace、不把 Run 失败改成 HTTP 500、不修改正常消息/工具 output，不把工具报错当整次 Run 失败。

已开启 SSE 的失败由原生事件表达，不能在流末追加 HTTP Envelope；握手前 HTTP、文件/PTY 接口仍遵守现有 error-envelope，新增 HTTP 码不在本期范围。

## 安全诊断：复用 RunDiagnostics v1

失败码由真实 RuntimeWorkspaceError 获取；graph 终态与 workspace 重试记录都是观测，不能覆盖原生 Run 状态。

1. `StartupDiagnostics.phase()/finish()` 为可信 Workspace 故障附加有限 `error_code`，覆盖 factory.workspace 阶段；初始化根失败不伪造执行次数。
2. `_RuntimeDiagnosticsCallback.on_chain_error()/_finish()` 和 `on_tool_error()` 记录白名单 Workspace 码，清理按回调 run_id 的局部数据，避免串 Run。
3. 共享 execution 在发生重试恢复、致命 Workspace 故障或清理异常时发出一次安全汇总 `runtime.workspace.execution_completed`。正常无重试成功不新增 observation；这不是完整命令审计。
4. 使用官方 `adispatch_custom_event` 与既有 callback 的 `on_custom_event`，只处理内部固定事件名/字段；callback 以自身可信 metadata 合并 scope，事件 payload 不能覆盖 tenant/project/thread/run。没有回调或导出失败时保持原执行结果。
5. Runtime `query.py:_project()/empty_diagnostics()` 扩展投影，API `application/diagnostics.py` 扩 DTO，前端扩 Zod。保持 version 1 的增量可选字段。

已实施 `workspace_executions` 最多 20 条，旧响应缺字段视为 `[]`；新增结果中无 Workspace 的 Agent 也为 `[]`：

| 字段 | 类型/限制 | 含义 |
| --- | --- | --- |
| `observation_id` | 既有 Identifier | 观测标识，不是命令幂等键 |
| `backend` | 固定 `docker` | 本期真实覆盖后端；不伪造 local/cloud 记录 |
| `phase` | `start/execute/cleanup` | 发生容错或故障的阶段 |
| `outcome` | `recovered/failed/cancelled` | recovered 仅指启动重试恢复，不等于 Run 成功 |
| `code` | 上述 Workspace 码或 null | 固定安全原因 |
| `command_state` | `not_started/started/unknown` | not_started 仅允许经过 G1 证明；started 不承诺命令成功 |
| `attempts` | 严格整数 1-4 | 命令启动尝试，不含只读诊断探测 |
| `retry_wait_ms` | 有限非负数 | 已发生的退避等待，不用 null/0 混淆 |
| `duration_ms` | 既有 Duration/null | 本次受影响调用耗时 |

`graph_executions[].error_code`、`startup.phases[].error_code` 扩为独立 ExecutionErrorCode = ModelErrorCode 或 WorkspaceErrorCode。`model_errors[].code` 仍只接受 ModelErrorCode；不将 Workspace 伪装成 provider/model 故障。额外 `command/container_id/path/stderr/exception/headers/env` 不进入 DTO。

保留 2 秒查询预算、100 observations、50 traces、既有各列表上限、truncated 和精确 scope/run 核验。没有新存储、缓存、查询 endpoint 或 operation。`availability=disabled/unavailable` 不阻止 SSE 安全错误提示。

## 通用 Agent 接入

### 已有 Agent

- Showcase `DockerWorkspaceBackend.aexecute()` 和 Dear `DearWorkspaceBackend.aexecute()` 已进入 shared execute：默认继承本能力，避免分别复制重试逻辑。
- Showcase 的 general-purpose 子 Agent 可执行，需通过真实子图契约证明 Workspace 异常穿过 task 通道到父 Run；research 只读、chart-agent 的 MCP 边界维持原能力。
- Dear `subagents/researcher.py:researcher()` 返回的角色名为 general-purpose，但它是只读角色。不能为了“通用适配”向该子图新增 execute。
- Reference/Workflow 没有同样的 Workspace execute，保持正常链路，只做“不被该能力污染”的回归。
- local 官方 LocalShellBackend 会把一些异常转为 ExecuteResponse 字符串，外围不能恢复可靠启动证据；本期不加 local 自动重试、不复制官方 local shell。

### 新 Agent 的最短接入契约

在所属服务 `agent.py` 显式装配现有 WorkspaceMiddleware、官方 ToolErrorMiddleware 与诊断 wrapper；backend 的 `aexecute()` 调 shared execution，超时沿用既有边界；声明真实工具 allowlist/HITL。WorkspaceError 必须继续传播，不改成 ToolMessage 或成功响应。

新 Agent 有独立 provider 时，在所属 backend 内使用 provider 类型化的“尚未提交/开始”证据，补副作用测试后再复用固定有界退避原则。当前不创建只有一个实现的 provider ABC、registry/factory 或通用装饰器。

## 逐文件改动计划

| 文件 | 关键符号与改动 |
| --- | --- |
| `apps/runtime-service/src/runtime_service/workspace/execution.py` | `execute_in_workspace()` 保持公开签名；新增内部健康探测、失败转换/清理；G1 通过才加可靠启动重试局部 helper/常量；发布安全诊断汇总 |
| `apps/runtime-service/src/runtime_service/runtime/errors.py` | 复用 `RuntimeWorkspaceError`；列出有限 Workspace 码，作为 Runtime 观测白名单；不改继承为 OSError/TimeoutError |
| `apps/runtime-service/src/runtime_service/tools/errors.py` | `tool_error_content()/on_tool_error()` 以回归确认 Workspace 不降级；通常无需修改 |
| `apps/runtime-service/src/runtime_service/observability/diagnostics.py` | `safe_fields()` 增加必要数值/阶段白名单；拒绝 payload 覆盖可信身份 |
| `apps/runtime-service/src/runtime_service/observability/langfuse.py` | `_RuntimeDiagnosticsCallback.on_custom_event()`、`on_chain_error()`、`on_tool_error()`、`_finish()` 增 Workspace 安全字段；复用 `record_diagnostic_event()` |
| `apps/runtime-service/src/runtime_service/observability/startup.py` | `StartupDiagnostics.phase()/finish()` 增有限 Workspace `error_code` |
| `apps/runtime-service/src/runtime_service/observability/query.py` | `_project()/empty_diagnostics()` 增可选 Workspace 记录与有限执行错误枚举，维持预算/限额 |
| `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/backend.py` | `DockerWorkspaceBackend.aexecute()`、`WorkspaceMiddleware.abefore_agent()` 验证公共能力与异常传播；只改确有契约缺口的部分 |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/workspace/backend.py` | `DearWorkspaceBackend.aexecute()`、`WorkspaceMiddleware.abefore_agent()` 同上；不改变 protected mount/skills 策略 |
| `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/agent.py` 与 `subagents.py` | `middleware()/build_subagents()` 核对主/子图顺序、scope、fatal 传播；优先测试，保持显式装配 |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py` 与 `subagents/researcher.py` | `middleware()/researcher()` 回归只读边界，不新增子 Agent/工具权限 |
| `apps/platform-api/src/platform_api/adapters/langgraph/sdk_client.py` | `project_execution_error()/redact_execution_fields()/redact_runtime_private_fields()` 扩精确、幂等 Workspace 安全投影 |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py` | `_redact_sse_frame()` 先完成 G0，再覆盖原生 tasks 等槽位；保留流格式 |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/application/diagnostics.py` | `GraphExecution/StartupPhase/RuntimeDiagnostics` 扩执行码与 Workspace DTO，旧字段默认兼容 |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py` | `get_thread_run_diagnostics()` 保持 ACL/Run 绑定；主要测试，不增加重复业务用例 |
| `apps/platform-web/src/modules/chat/diagnostics/types.ts`、`view-model.ts` | 同事补可选 schema、固定文案与 Workspace view-model |
| `apps/platform-web/src/modules/chat/components/trajectory/RunDiagnostics.vue` | 同事扩现有面板，显示安全阶段、次数与等待 |
| `apps/platform-web/src/modules/chat/composables/useChatSession.ts` | 同事在既有 Run 错误展示出口接精确映射，不独立维护运行状态 |
| `apps/platform-web/src/modules/chat/composables/useRunDiagnostics.ts`、`src/services/threads/diagnostics.service.ts` | 同事回归授权、ID匹配、abort/epoch；通常无需新请求逻辑 |

测试新增位置与用例见 [verification.md](verification.md)，不凭规划给每个源文件都造测试文件。前端交接独立见 [frontend-handoff.md](frontend-handoff.md)。

## 实施顺序与发布

1. 人工评审 G0、G1 分支、exit125 探测、公开字段和前端接入。
2. 收敛 API 基线与启动证据；根据 G1 决定是否实施窄重试。
3. Runtime 执行/清理与诊断、API 投影/DTO；每阶段跑对应最小测试。
4. 同事接前端，使用批准后的合成 fixture 开发；Runtime/API 提供真实样例后联合验证。
5. Final 在隔离环境执行关键主/子图、Worker、SSE、历史、权限、取消、性能、安全和回退。

先部署可选 DTO/安全投影，再部署 Runtime，再接前端展示；具体部署不在本轮授权。旧 Web 可以忽略新增诊断字段；新 Web 应接受旧 v1 缺字段。不能用混装部署代替批准版本的 Final 验证。

回退先移除/禁用本次候选重试和特殊探测代码，再回退 Workspace 诊断生产者；公共 DTO 的可选字段可保留。保留 G0 安全修复、既有隔离/取消清理，不回滚成原文透传，不重建或清空 `.runtime`、不调整 DB。回退仅针对本项目变更，不使用 git reset 清理同事工作。

## 评审清单

- [x] G0：用户批准 tasks 脱敏与通用失败码；code/字符串为 `runtime.execution_failed`，对象固定说明。
- [x] G1：用户接受证据分支；真实接线副作用证据决定采用 B，启动 retry deferred。
- [x] exit125 一次有界只读探测与保守 unknown 语义获批。
- [x] 五个 Workspace 白名单码、形状保真、原生终态与控制流获批。
- [x] 可选 RunDiagnostics v1、上限与可信 scope 获批。
- [x] 用户指定前端交同事；worktree 与合入基线差异在交接中注明。
- [x] 用户已启动 Docker，批准非前端隔离链路与回退验证；使用独占 PG/Redis/SQLite 和确定性模型。

人工批准原文见 implementation/01-review-and-start-boundary.md。前端收到交接后的实施和浏览器验收仍是 T23；用户授权不等同前端已完成。

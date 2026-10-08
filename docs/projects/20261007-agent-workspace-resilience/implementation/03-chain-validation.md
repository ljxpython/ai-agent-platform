# 非前端综合验证证据

日期：2026-10-07。关联 T12、T22、T30、T31；任务进度以 [tasks.md](../tasks.md) 为准，最终判定以 [verification.md](../verification.md) 为准。

> 历史阶段记录：本篇保留用户当时调整为本地验收的证据与后延状态；后续 Docker 后延项已由 T32/T33 补齐，见 [Docker 恢复验收](04-docker-final.md)。

## 版本与资源边界

候选代码在独立 worktree，基线 `bf47991b7592b19cbda1051c6a674623450318ae`，未提交或部署。借用主目录已有虚拟环境，在各 worktree 服务目录显式设置 `PYTHONPATH=src`；导入检查确认候选模块来自本 worktree。

Python 3.13.9；Runtime 实际依赖为 GraphHarbor 0.13.0.post41、LangGraph 1.2.11、LangChain 1.3.17、DeepAgents 0.7.8、Langfuse 4.15.1、pytest 9.0.2。按用户最新指示，本轮最终验收使用已有 Python、原生 `initdb/postgres/redis-server` 和 `RUNTIME_BACKEND=local`，复用 GraphHarbor 参考仓库已有 `scripts/run_isolated_tests.py`，不安装依赖或修改现役数据库。

原生 runner 提供独占 PG/Redis 临时目录和端口；HTTP 夹具启动 Runtime API、真实 Worker、Platform API，使用临时 SQLite 平台数据和合成模型。local 命令、文件副作用、Worker 领取、持久状态和 HTTP 出口都是真实执行；云模型和公网 Langfuse 不属于此验证。原生模式只改测试接线，没有改生产 local backend 或 Docker 默认配置。

此前使用既有 `python:3.13-slim`、`postgres:16`、`redis:7-alpine` 取得的 Docker Phase 证据仍保留；真实 Docker 生命周期、取消/清理与性能 Final 按用户要求后延，不用本地结果代替。

## 本轮本地真实 Worker 链路

- `test_http_main_child_errors_and_restart_replay`：1 passed，188.12 秒。主/子图工具错误恢复、致命 unknown 错误全出口 canary 屏蔽、approve/edit/reject/clarification/cancel 原生控制流通过；三角色服务实际重启后 checkpoint 回放及 keep 文件保留；恢复 HEAD 源码后主/子图新 Run 成功。
- `test_native_workspace_execute_and_root_failure`：1 passed，45.04 秒。Dear/Showcase 实际 local 命令退出7后 Run success，counter=once；Dear execute 经过审批；根符号链接被拒绝为 `runtime.workspace.unavailable`，Run error，PG reason=business_error、retry_count=1，原链接/文件保留且私有路径不透出。
- GraphHarbor 首次 claim 就将 retry_count 加到 1，因此断言 1 表示本轮没有再次调度，不能误读为重试了一次。
- 回退使用临时 `git archive HEAD` 源码与相同隔离数据库/工作区，重启各服务后继续验证，没有修改真实 worktree HEAD。
- 两项原生测试退出后，专属服务和原生 PG/Redis 进程已归零；未停止同事服务。日志位于 `/tmp/workspace-native-http-20261007/test_http_main_child_errors_an0/` 与 `/tmp/workspace-native-roots-20261007/test_native_workspace_execute_0/`；ready/spec 含测试凭据，不作为公开样例。

本地真实 thread/run ID、原生状态见 [前端报告](../frontend-report.md)。本轮正常 local 命令没有 Docker Workspace 观测，空数组不能证明命令未执行。

## 历史 Docker Workspace Phase 链路

`tests/services/dearflow_agent/test_tool_error_platform.py::test_workspace_failure_worker_no_requeue_and_safe_replay` 已在隔离栈通过。真实同 Run ID、诊断响应见 [前端报告](../frontend-report.md)。

- Dear 主图、Showcase 主图和可执行子图：原生 Run error，PG reason=business_error，counter=once，retry_count=1仅为首次claim。
- Dear execute 实际经过 HITL approve/resume；不以 execution_mode=ultra 绕过审批。执行取消终态 interrupted，counter=once，无迟到文件。
- 根符号链接被拒为 workspace.unavailable；原链接和 keep 文件保留，不建替换工作区。
- live SSE、原生 Run、Thread、state/history 和 Protocol 回放使用安全错误投影，私有 canary 不透出；diagnostics disabled 仍不遮蔽运行错误。
- 回退通过临时 `git archive HEAD` 源码，在同一个隔离数据库与工作区重启 Runtime/Worker；4 个工作区及历史状态保持，新 Run 经审批后成功且副作用一次。

## 历史诊断与真实权限

真实 callback 输出经合成 `httpx.MockTransport` 模拟 Langfuse observations，随后调用实际 Runtime HTTP 查询与 Platform API DTO。每个失败 Run 一条 workspace_executions，attempts=1、retry_wait_ms=0、command_state=unknown，20 条上限和字段白名单在组合测试覆盖。注入 DIAGNOSTIC_CANARY 额外字段被剥离。

真实登录与项目授权验证 owner、shared-read、撤销共享、跨项目、错误 run/thread；合法共享可读，撤权/跨项目拒绝，错误 Run 不泄露其它记录。该证据不冒充公网 Langfuse 的采集与存储验收。

## 回归与发现的实际问题

- API 全仓：355 passed、23 skipped、601 subtests passed，491.38 秒。定向76 passed、122 subtests passed。完整回归发现 artifact/result 的业务字典被错误当作执行错误，已在共享 `redact_runtime_private_fields()` 修复，私有字段仍递归剥离。
- Runtime 非外部扩大回归：708 passed、39 skipped、55 deselected，1032.83 秒。使用 `-m "not integration and not e2e and not durable"`，显式排除未标记的 `tests/services/test_message_inbox_postgres.py` 外部 PG 专项；不能称无条件全仓通过。
- 最新执行与诊断定向：59 passed、5 deselected，16.21 秒；覆盖共享执行器、Dear 执行、Showcase backend 与 RunDiagnostics，包括 ServerVersion 补修。上述扩大回归加载早于该补修，因此以本定向结果覆盖最新执行器。
- MCP/图工具治理测试 mock 缺少当前工具字段与 with_config，修正测试夹具后4项定向通过；生产代码未为这类回归改契约。冷启动期间 MCP 与媒体取消受本机负载影响，后续扩大回归通过。既有 SWIG、Starlette、Pydantic 与 v3 beta 警告如实保留。
- Docker CLI 真实不可达用例发现 `docker info --format '{{.ServerVersion}}'` 可能返回0却没有 ServerVersion。共享探测改为退出码0且模板非空；只读固定参数、2秒逻辑预算与单次命令规则保持。执行定向32 passed、3 deselected，真实不可达 daemon1 passed；不读原始 stderr、不猜错误文本、不切宿主 shell。

## HTTP 夹具修正

只修测试接线，未修改 GraphHarbor 依赖或生产租约：

- API ready 文件先于 socket listen 写出：初始启动和重启都等实际 `/_system/health` HTTP200。
- 源码回退后 `_docker_control` 不存在：切换前移除仅供候选源码的探测/查询注入环境。
- 冷 Agent 导入超过默认60秒 Run 租约：Worker 在进入领取循环前完成模块导入。
- API就绪不代表Worker就绪：夹具在 `ProductionWorker.run_forever()` 开始时写入当前PID，父测试核对PID后才提交Run；启动阶段错误不会被误当执行失败。

原生模式新增外部 PG/Redis 与 local backend 接线；去掉 Docker 探测注入，回退时兼容 HEAD 不含 `_docker_control`。Worker 就绪检查和冷模块预加载落实后，上述本地工具恢复/三角色重启用例已通过。

历史 Docker 综合工具用例的一轮失败只返回 metadata/heartbeat，Worker 当时停在 schema_setup 的 PG advisory lock；另一轮返回 state503，其原因尚未证实，不能仅凭停机日志归因容器回收。失败轮次不记为通过；本地同用例的最终成功结果单独记录。

## 执行入口

以下命令在相应 worktree 服务目录执行；`RUNTIME_TEST_PYTHON`/`PLATFORM_API_TEST_PYTHON` 指已有虚拟环境的 Python，`GRAPHHARBOR_REFERENCE_DIR` 指现有参考仓库。先核对导入来自 worktree；命令中的变量只是记录执行入口，不新增产品配置。

```bash
# apps/platform-api
PYTHONPATH=src "$PLATFORM_API_TEST_PYTHON" -m pytest -q
# apps/runtime-service，显式外部依赖边界
PYTHONPATH=src PLATFORM_API_TEST_PYTHON="$PLATFORM_API_TEST_PYTHON" "$RUNTIME_TEST_PYTHON" -m pytest -q -m "not integration and not e2e and not durable" --ignore=tests/services/test_message_inbox_postgres.py
# 最新执行与诊断定向
PYTHONPATH=src "$RUNTIME_TEST_PYTHON" -m pytest -q -m "not integration and not e2e and not durable" tests/workspace/test_execution.py tests/services/dearflow_agent/test_execution.py tests/services/showcase_demo/test_backend.py tests/observability/test_run_diagnostics.py
# 两条真实本地HTTP链路，独立临时目录
PYTHONPATH=src TOOL_ERROR_PLATFORM_NATIVE=1 PLATFORM_API_TEST_PYTHON="$PLATFORM_API_TEST_PYTHON" "$RUNTIME_TEST_PYTHON" "$GRAPHHARBOR_REFERENCE_DIR/scripts/run_isolated_tests.py" "$RUNTIME_TEST_PYTHON" -m pytest -x -s -q --basetemp=/tmp/workspace-native-http-20261007 tests/services/dearflow_agent/test_tool_error_platform.py::test_http_main_child_errors_and_restart_replay
PYTHONPATH=src TOOL_ERROR_PLATFORM_NATIVE=1 PLATFORM_API_TEST_PYTHON="$PLATFORM_API_TEST_PYTHON" "$RUNTIME_TEST_PYTHON" "$GRAPHHARBOR_REFERENCE_DIR/scripts/run_isolated_tests.py" "$RUNTIME_TEST_PYTHON" -m pytest -x -s -q --basetemp=/tmp/workspace-native-roots-20261007 tests/services/dearflow_agent/test_tool_error_platform.py::test_native_workspace_execute_and_root_failure
# 仓库根
uvx ruff check apps/platform-api apps/runtime-service
uvx ruff format --check apps/platform-api apps/runtime-service
git diff --check
```

## 范围声明

非前端开发和用户指定的本地验收已完成；自动启动 retry 采用批准分支 B，明确 deferred；没有 retry耗尽/recovered/not_started 的真实样例。Docker 相关 Final 后延，历史结果不宣称性能达标。本轮前端 T23 与浏览器 F01-F10 移交同事，不记为已完成，不构成非前端 Block。现役部署、真实云 provider 与公网观测后端不在本轮范围。

## 经验提案（待用户确认）

建议在 Runtime 经验库记录：公共 asyncio 创建异常不能证明命令未启动，必须用真实副作用检查重试边界；Docker 固定模板探测需同时确认退出码与非空结果；Worker 首次 claim 计数和领取循环就绪应按实际源码/进程证据验收。当前仅提出建议，未经用户确认不写入 `docs/lessons/`。

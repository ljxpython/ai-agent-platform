# Terminal 非前端实现

日期：2026-09-17。用户授权实施第二阶段 Terminal，前端仅交接设计。对应任务：[06](../06-terminal-backend.md)。

## Runtime

| 文件/函数 | 改动与理由 |
| --- | --- |
| `apps/runtime-service/src/runtime_service/workspace/terminal.py:41` `TerminalSession` | 新增 POSIX PTY；固定 shell、受控环境、owner 工作区；输入单调序号与最近一次回执去重；输出有界 byte buffer、offset 重放；resize/close |
| 同文件 `TerminalManager:366` | create/get/list/sweep/shutdown；用户线程配额、进程总量、TTL、实例 ID；没有新数据库或分布式 broker |
| `apps/runtime-service/src/runtime_service/workspace/terminal_child.py:1` | 子进程获取 controlling tty 后 exec，避免多线程父进程使用 preexec_fn |
| `apps/runtime-service/src/runtime_service/http/terminal.py:19` | 三个请求模型；`_owner:39` 校验 read/write scope、线程/graph、execute 权限及工具；六个路由通过 to_thread 调用管理器 |
| `apps/runtime-service/src/runtime_service/workspace/execution.py:16` `docker_workspace_args` | 原命令执行内联参数提取复用；Terminal 和原 Execute 共享只读/挂载/网络/资源策略 |
| `apps/runtime-service/src/runtime_service/webapp.py` | 注册 router；lifespan finally 清理 PTY/容器 |
| `apps/runtime-service/src/runtime_service/runtime/auth.py`、`auth/platform.py` | 新 terminal-read/write delegation，禁止该 scope 调用 native Graph 操作 |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/capabilities.py` | graph_capabilities 增加开关控制的 terminal 声明，能力声明不替代权限 |

关键前后变化：原 Docker args 仅用于 `execute_in_workspace` → `docker_workspace_args` 被一次命令和交互终端共同调用；原 Runtime 无手动终端端点 → `create/list/output/input/resize/close`，不增添 Agent tool 或改变 Agent HITL。

关闭流程先清理 PTY 前台进程组，再 SIGHUP Shell，超时才强制 kill；Docker `rm -f` 有界，失败告警且容器内部 timeout 兜底。local 对主动脱离会话的后台进程不承诺隔离/回收。

## Platform API 与启动脚本

| 文件/函数 | 改动与理由 |
| --- | --- |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py:1113` `thread_terminal` | 每次先 `_load_thread(write=True)` 和 catalog 校验，再服务端签 delegation；read 也不能绕过写权限 |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/application/ports.py` | 原 upstream protocol 增加 terminal_request，无新 interface |
| `apps/platform-api/src/platform_api/adapters/langgraph/runtime_gateway_upstream.py:70` `terminal_request` | 六个固定 action 映射 HTTP/path；转义 thread/session ID，复用 JSON transport/error mapping |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py:580` | 请求校验、六类公开路由、no-store、沿用私有字段脱敏 |
| `apps/platform-api/src/platform_api/core/security/tokens.py` | 与 Runtime 同步 terminal-read/write operation 白名单 |
| `apps/platform-api/src/platform_api/modules/audit/http_resolution.py:358` | 六种语义审计 action，target 为 thread，不记录终端输入输出正文 |
| `scripts/local-stack.sh` | `RUNTIME_TERMINAL_ENABLED` 默认 1；独立 Runtime 默认 0；调用环境覆盖 dotenv，仅接受 0/1 |

## 测试与交接

- 新增 `apps/runtime-service/tests/test_terminal.py`、`tests/test_terminal_http.py`：真实 local/Docker PTY、权限/参数、重放/输入冲突、TTL/清理、DearFlow readonly。
- 扩展 `apps/platform-api/tests/test_runtime_gateway_workspace.py`：真实两服务链路与重启旧 ID；`test_runtime_gateway_http_matrix.py`：六路由授权；`test_audit_http_resolution.py`：动作与不记录正文。
- 扩展 `scripts/test_local_stack_backend.py`：默认/覆盖/非法开关。
- Runtime 33 passed；网关49、审计7、脚本2 tests OK；Ruff/语法/diff 检查见 [验证记录](../verification.md#terminal-第二阶段验证2026-09-17)。
- [05](../05-frontend-handoff.md) 新增 Vue/composable/service 文件落点、六类 API、DTO、字节处理、串行重试、detach/close、安全提示与验收清单。没有新增或修改前端功能文件。

本阶段非前端 **done**；前端实现/浏览器验收 **deferred**。没有提交或部署，生产多 worker 需会话粘性路由；没有持久 PTY 恢复或命令全文审计。

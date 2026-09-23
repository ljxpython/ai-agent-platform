# 统一本地执行后端

时间：2026-09-23。对应 Task 1.1、1.2。

## 改动

- `apps/runtime-service/src/runtime_service/workspace/execution.py:runtime_backend()`：统一解析 `RUNTIME_BACKEND`，只允许 `local|docker`，默认 `docker`。
- `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/backend.py:create_workspace()`：改用统一选择值；原有 Docker/LocalShell 实现继续复用。
- `apps/runtime-service/src/runtime_service/services/dearflow_agent/workspace/backend.py:DearWorkspaceBackend.aexecute()`：local 使用官方 `LocalShellBackend`，只传最小 PATH、线程 HOME/工作区/技能目录，不继承 Runtime 凭据；Docker 分支仍调用原有受限容器执行器。
- `apps/runtime-service/src/runtime_service/workspace/terminal.py:TerminalSession.__init__()`：终端遵循同一开关。
- `apps/runtime-service/src/runtime_service/services/dearflow_agent/prompts.py` 与 data-analysis/PPT Skills：Shell 使用环境变量提供的真实目录；文件工具继续使用虚拟路径。两个技能脚本的路径校验支持该真实目录。
- `apps/runtime-service/pyproject.toml`、`uv.lock`、`scripts/local-stack.sh`：补齐本地脚本依赖；本地栈默认 local，独立 Runtime 默认 Docker。

之前 `RUNTIME_SHOWCASE_BACKEND=local` 只覆盖 Showcase，Dear Agent 的 `execute()` 固定调用 Docker。现在 `RUNTIME_BACKEND=local` 统一控制两个有 execute 能力的图和交互终端。参考图与工作流图没有 execute 工具。

## 验证

本地脚本、Dear Agent 审批后执行与发布、Showcase、终端和网关定向测试通过；详细结果见 [验证记录](../verification.md)。

## 边界与回退

LocalShellBackend 在宿主机运行，文件工具权限不限制 Shell，且不提供 Docker 的断网、只读挂载或 CPU/内存限制。需要容器隔离时设置 `RUNTIME_BACKEND=docker` 并重启 Runtime API/Worker。

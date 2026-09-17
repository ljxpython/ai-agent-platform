# 双执行后端与本地栈切换

## 改动时间
2026-09-17

## 相关任务
- Phase 1：新增 LocalShellBackend、后端选择和测试
- Phase 2：本地栈切换与文档

## 改动文件
- `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/backend.py`
- `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/agent.py`
- `apps/runtime-service/tests/services/showcase_demo/test_backend.py`
- `scripts/local-stack.sh`
- `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/README.md`

## 具体改动

- 抽取共享线程工作区初始化逻辑，保留 `DockerWorkspaceBackend`。
- 新增 `LocalWorkspaceBackend`，内部使用官方 `LocalShellBackend`，只注入最小 PATH、线程 HOME 和 Git 配置路径，不继承父进程凭据。
- `create_workspace` 的 `RUNTIME_SHOWCASE_BACKEND` 默认值为 `docker`；只有本地栈默认 `local`，均仅接受 `local` 或 `docker`。
- 本地栈脚本导出该配置，Docker 可通过 `RUNTIME_SHOWCASE_BACKEND=docker` 显式启用。
- `prompts.py` 和包内 `skills/showcase-notes/SKILL.md` 指导 shell 使用相对路径；文件工具仍使用 `/workspace/...`。
- 新增 `scripts/test_local_stack_backend.py` 覆盖配置优先级和子进程环境；`test_agent.py:test_local_execute_requires_approval` 覆盖真实执行的审批允许/拒绝。

关键替换：`agent.py` 的 `DockerWorkspaceBackend(...)` 改为 `create_workspace(...)`；Docker 执行器本身不变。59 项 Showcase 回归与脚本测试通过，剩余验证见 verification.md。

## 影响

- Docker 模式行为保持不变。
- local 模式是受信任开发机上的宿主执行，不具备 Docker 级隔离。

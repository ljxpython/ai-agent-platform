# Showcase Demo 本地执行模式 - 整体方案

## 背景

showcase_demo 当前所有 Shell 命令都通过 DockerWorkspaceBackend 执行。本地开发需要 Docker daemon 和镜像，调试成本较高；Open SWE 提供了 LocalShellBackend，可在本机工作区直接执行命令。

## 方案设计

### 后端选择

在 showcase_demo 内保留两个明确的 Backend：

- `DockerWorkspaceBackend`：现有正式后端，提供容器网络、资源、只读根文件系统和工作区挂载限制。
- `LocalWorkspaceBackend`：基于官方 `LocalShellBackend`，使用相同的线程工作区和虚拟文件路径；关闭环境继承，仅注入最小 PATH。

通过 `RUNTIME_SHOWCASE_BACKEND` 选择，允许值为 `docker` 和 `local`，默认 `docker`。未知值直接失败。

### 本地模式边界

LocalShellBackend 的 shell 执行不受 `virtual_mode` 限制，因此本地模式只适用于受信任的个人开发环境，不能部署到多租户或生产环境。HITL 审批仍保持开启，模型和工具权限不放宽。

### 本地栈切换

`scripts/local-stack.sh` 读取 `RUNTIME_SHOWCASE_BACKEND`，默认 local，启动 Runtime API/Worker 时传递该变量。调用环境优先于 `.env`。切换已有进程需要 restart。

## 关键改动点

1. `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/backend.py`
   - 抽取共享线程工作区初始化逻辑。
   - 新增 LocalShellBackend 实现。
   - 增加后端选择函数。
2. `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/agent.py`
   - 根据可信服务配置选择后端。
3. `apps/runtime-service/tests/services/showcase_demo/test_backend.py`
   - 覆盖本地后端工作区、环境隔离、真实退出码和选择逻辑。
4. `scripts/local-stack.sh`
   - 增加本地/Docker 模式切换。
5. showcase_demo README、`docs/FEATURES.md`
   - 说明模式差异和默认值。

## 风险和回滚

- 本地模式可访问宿主机任意路径，风险通过配置默认 Docker、HITL 和文档警告控制。
- 回滚方式：本地栈用 `RUNTIME_SHOWCASE_BACKEND=docker bash scripts/local-stack.sh restart`；独立 Runtime 取消 local 配置并重启 API/Worker 即恢复 Docker 默认。

## 实施状态

用户已评审批准。当前 partial：实现与本地验证完成，Docker 和完整部署 E2E 待验，具体证据见 verification.md。

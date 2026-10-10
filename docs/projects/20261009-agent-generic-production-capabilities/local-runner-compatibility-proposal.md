# 架构讨论提案：非 Docker / 本地与异构云端环境下的后台长任务兼容方案

> **文件状态：** 讨论与技术预研备忘录 (Discussion RFC)
> **提出日期：** 2026-10-10
> **发起人：** 老王（技术流）与团队协同
> **关联专项：** `docs/projects/20261009-agent-generic-production-capabilities/`

---

## 1. 背景与核心问题

### 1.1 现状与痛点
在当前已实施的后台长任务架构中，后端代码在 `start_task` 处设置了强制硬检查：
```python
if runtime_backend() != "docker":
    raise RuntimeWorkspaceError("background_task_not_supported")
```
当系统运行于以下环境时，大模型一旦接收到用户“在后台执行/耗时任务”的意图，便会尝试调用 `background_execute` 工具，随后触发该硬异常，导致整个对话 Run 直接中断并报出 `runtime.execution_failed`：
1. **开发者本地无 Docker 调试环境**：开发者未运行 Docker Desktop 或处于受限轻量环境；
2. **无 Docker-in-Docker 权限的云端环境**：如 Kubernetes Pod（无特权模式 / 无 `/var/run/docker.sock` 挂载）、AWS Fargate、Google Cloud Run 等轻量 Serverless 容器运行时；
3. **只读或纯沙箱部署节点**。

### 1.2 讨论目标
如何让 Agent 平台在非 Docker 环境下避免生硬崩溃，具备优雅降级或本地兼容能力，同时不削弱生产环境的严格安全隔离？

---

## 2. 三种演进方案对比与权衡

### 方案 A：能力感知与动态工具门禁 (Capability-Aware Tool Gating) ——【推荐优先采纳】

#### 核心设计：
- **按需暴露工具**：在 Agent 工厂（`build_background_tools`）装配工具时，检查当前宿主是否满足 `runtime_backend() == "docker"` 且 `RUNTIME_BACKGROUND_TASKS_ENABLED == "1"`；
- **若不满足**：动态**不向大模型注册** `background_execute`、`background_task`、`cancel_background_task` 这三个工具；
- **前端联动**：`capabilities.background_tasks` 自动返回 `false`，工作区自动隐藏「任务」Tab。

#### 优势（Pros）：
- **零安全漏洞**：不在宿主机暴露任何不受控的长命令能力；
- **大模型零幻觉**：模型看不到后台工具，接收到执行需求时会自动选用普通的 `execute` 工具在前台同步执行；
- **实现极其轻量**：仅需在 Agent 组合根中增加条件判断（3-5 行代码），无需引入新的进程管理复杂度。

#### 劣势（Cons）：
- 在非 Docker 环境下无法体验“异步非阻塞”效果（只能前台同步等）。

---

### 方案 B：工具内部友好降级与自愈 (Graceful Fallback / ReAct Self-Correction)

#### 核心设计：
- 工具保持对大模型可见；
- 当 `background_execute` 检测到当前为 `local` 或无容器环境时，**不抛出 Fatal 异常**（不打断整轮对话），而是返回一段具备自愈导向的结构化文本：
  ```json
  {
    "status": "unsupported_environment",
    "message": "当前运行时环境未启用 Docker 容器沙箱，无法执行后台非阻塞任务。请直接使用前台普通 execute 工具同步执行该命令。"
  }
  ```
- 大模型收到 Tool 结果后，ReAct 循环触发自我纠偏（Self-Correction），自动切换为调用 `execute` 工具完成任务，并向用户解释原因。

#### 优势（Pros）：
- 用户体验极佳，彻底消灭生硬的 `runtime.execution_failed` 顶栏红条；
- 大模型对环境限制具备感知与解释能力。

#### 劣势（Cons）：
- 多消耗一轮大模型思考 Token。

---

### 方案 C：实现轻量级 `LocalBackgroundRunner` (完全功能平替)

#### 核心设计：
- 类似前台的 `LocalWorkspaceBackend`，为后台任务实现专职的 `LocalBackgroundRunner`；
- **子进程脱钩**：使用 `asyncio.create_subprocess_exec` 配合 `start_new_session=True`（生成独立的进程组 Session）；
- **日志管道有界落盘**：将 stdout/stderr 重定向至宿主机的工作区隐藏目录（如 `.local-stack/workspaces/bg_logs/{task_id}.log`），通过读取文件偏移量模拟 `docker logs`；
- **状态与终止**：通过保存 PID，使用 `os.kill(pid, signal.SIGTERM)` 实现 `cancel` 动作；
- **对账**：通过检查 `kill(pid, 0)` 确认进程存活状态，并回写 PostgreSQL。

#### 优势（Pros）：
- 在本地无 Docker 或受限云端 Pod 中，依然能获得 100% 完整的“后台非阻塞、工作区任务卡片、实时查看日志、手动取消”全套体验；
- 极大改善开发者单机调试体验（DX）。

#### 劣势（Cons）：
- **安全性挑战**：长达 3600 秒的本地子进程缺乏 cgroups 资源配额限制（存在 CPU/内存打满宿主机风险）；
- **跨机器重启孤儿进程**：若宿主机突然断电或容器重启，无 Docker Daemon 帮助恢复孤儿进程，需要依赖启动时的 PID 对账清理逻辑；
- **工程量适中**：需编写约 150-200 行本地进程管理代码并补齐回归测试。

---

## 3. 落地建议（演进路线图）

1. **短期（P0，立即可落地）**：
   - 采纳 **方案 A + 方案 B 组合拳**：环境不支持时，工具返回友好错误引导模型自愈，杜绝前台直接崩红条；同时在 catalog capabilities 层面准确透传开关。
2. **中期（P1，供同事评审讨论）**：
   - 若团队确认在本地单机开发或特定私有化云端环境（无 Docker 特权）必须支持后台长任务，则基于 **方案 C** 实施 `LocalBackgroundRunner`，并在配置中增加安全提示与超时上限（如 local 模式下最大 timeout 限制为 300 秒）。

---

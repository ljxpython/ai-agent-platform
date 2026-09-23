# Dear Agent 本地 execute

- **目标：** 统一 `RUNTIME_BACKEND`，本地开发中所有智能体的 `execute` 和交互终端不依赖 Docker daemon。
- **范围：** runtime-service 与本地栈脚本；正式 Runtime 默认仍为 Docker。
- **级别：** 治理改动（命令执行隔离边界）。
- **状态：** 部分完成：本地执行与运行中本地栈已验证；Docker daemon 未运行，容器回归和浏览器手工验收未执行。
- **人工决策：** 用户于 2026-09-23 明确要求以 `RUNTIME_BACKEND=local` 控制所有智能体的本地执行，并要求修改代码。本地模式只能用于受信任开发机，保留执行审批。

[方案](plan.md) · [任务](tasks.md) · [验证](verification.md)

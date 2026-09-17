# Showcase Demo 本地执行模式

## 项目概述
- **时间：** 2026-09-17
- **目标：** 为 showcase_demo 增加仅本地开发使用的 LocalShellBackend，并保留 DockerWorkspaceBackend 作为正式模式。
- **状态：** partial（实现及本地回归完成；Docker 与完整部署 E2E 待验）
- **人工评审：** 用户已在会话中确认方案并授权实施，补充要求 `scripts/local-stack.sh` 默认 LocalShellBackend；Runtime 独立启动仍默认 Docker。

## 快速导航
- [整体方案](plan.md)
- [任务拆分](tasks.md)
- [验证记录](verification.md)

## 改动范围
- **影响服务：** runtime-service、本地栈脚本
- **改动级别：** 治理改动（命令执行隔离边界）

## 关键决策
1. DockerWorkspaceBackend 保留并继续作为默认正式后端。
2. 本地栈默认 LocalShellBackend，独立启动需显式配置 `RUNTIME_SHOWCASE_BACKEND=local`。
3. 本地模式明确是受信任开发机上的宿主执行，不能宣称具备 Docker 级安全隔离。

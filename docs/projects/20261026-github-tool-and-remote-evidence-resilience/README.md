# GitHub 调研工具与远程沙箱证据元组契约韧性治理

## 项目概述
- **时间：** 2026-10-26 至 2026-10-26
- **目标：** 解决 GitHub API 匿名 403 限流击穿问题，并彻底根除远端 Docker 沙箱 RPC 反序列化将二元组退化为 List 导致 LangChain 崩溃抛出 `runtime.execution_failed` 的系统缺陷。
- **负责人：** @老王
- **模板类型：** 标准模板
- **状态：** `done`

## 快速导航
- [整体方案](plan.md)
- [任务拆分](tasks.md)
- [验证记录](verification.md)

## 改动范围
- **影响服务：** `runtime-service`
- **改动级别：** 链路改动（涉及 Remote Sandbox RPC 跨进程传输契约、LangChain 工具执行契约、环境变量规范）
- **预计工作量：** 0.5 人天

## 关键决策
1. **借鉴 deer-flow GitHub API 鉴权模型**：支持可选的 `GITHUB_TOKEN` 环境变量，在发起 `api.github.com` 请求时以 `Bearer` 凭据注入，将公网出口 IP 的 60 次/小时限制平滑提升至 5,000 次/小时；未配置 Token 时保留匿名调用与现存优雅降级。
2. **修复 Remote RPC 证据留存契约退化**：在 `_evidence` 接收 `RemoteWorkspace.call("research_evidence", ...)` 返回值时，严格校验并恢复为标准二元组 `tuple[str, dict]`，满足 LangChain `@tool(response_format="content_and_artifact")` 严格类型契约，阻断 `ValueError` 冒泡导致的整个 Agent 执行中断。

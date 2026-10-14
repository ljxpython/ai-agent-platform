# 知识库免隧道自治与单向架构治理 (Knowledge Zero-Tunnel Auth)

## 项目概述
- **时间：** 2026-10-14 至 2026-10-15
- **目标：** 彻底根除 RAG 异步 Worker 处理任务时对 Platform-API 反向 HTTP 回调（`KNOWLEDGE_AUTHORIZE_URL`）的强网络依赖，实现基于持久化凭证的本地自验与自治启动，永久关闭 SSH 反向隧道，将远端 RAG 彻底收敛为单向纯入站服务（仅需 22/8000 端口）。
- **负责人：** 老王（laowang-engineer）
- **模板类型：** 标准模板
- **状态：** 已完成

## 快速导航
- [整体方案](plan.md)
- [任务拆分](tasks.md)
- [验证记录](verification.md)

## 改动范围
- **影响服务：** `research/rag-anything-use` (RAG 核心服务 / job_worker), `apps/platform-api` (配置兼容), 运维夹具/工具脚本
- **改动级别：** 链路改动 (架构通信拓扑优化，双向强耦合解耦为单向服务)
- **预计工作量：** 0.5 人天

## 关键决策
1. **彻底消除反向网络依赖**：任务在 `submit` 阶段已被平台签名并在 RAG 网关完成初次强验签，其授权凭据 `identity` 已安全持久化至 SQLite `jobs` 表。异步 Worker 执行时直接基于本地持久化凭证做本地自验闭环，严禁在异步管道中发起反向公网 HTTP 回调。
2. **双模兼容与渐进式解耦**：保留 `authorize_url` 外部回调开关；当 `KNOWLEDGE_AUTHORIZE_URL="local"` 或 `KNOWLEDGE_LOCAL_AUTHORIZE=true` 时自动启用本地自治验签模式。
3. **彻底退役开发期 SSH 反向隧道**：解除本地后台 `ssh -R` 守护进程，远端服务器入站端口严格收敛至 `22` (SSH) 与 `8000` (FastMCP/Uploads)。

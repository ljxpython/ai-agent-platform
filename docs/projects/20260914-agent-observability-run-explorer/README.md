# Agent 全链路可观测与 Run Explorer

## 项目概述
- **时间：** 2026-09-14 至待定
- **目标：** 建立跨服务 Trace 关联和前端 Run Explorer，让一次 Agent 运行可从请求、Run、SSE、节点、模型、工具、子 Agent、审计完整排查。
- **负责人：** @team
- **状态：** 规划中

## 快速导航
- [整体方案](plan.md)
- [任务拆分](tasks.md)
- [验证记录](verification.md)

## 改动范围
- **影响服务：** platform-web、platform-api、runtime-service、interaction-data-service、可观测基础设施
- **改动级别：** 治理改动（含跨服务链路改动）
- **预计工作量：** 10-15 人天（首期）

## 关键决策
1. Langfuse 继续负责 Agent/Model/Tool/Subagent 语义 Trace，不自建同类系统。
2. OpenTelemetry SDK + Collector 自托管，负责跨服务 HTTP/数据库链路。
3. Platform API 自建 Run Explorer 聚合查询和权限边界；前端不直接查询 Langfuse。
4. Durable Run、平台事件、Audit、Langfuse、OTel 各自保持事实源边界。

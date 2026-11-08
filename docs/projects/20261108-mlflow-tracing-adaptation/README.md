# MLflow 链路追踪与会话评测适配 (Traces & Sessions)

## 项目概述
- **时间：** 2026-11-08 至 2026-11-08
- **目标：** 为平台引入 MLflow 原生 GenAI Traces & Sessions 追踪适配能力，支持后端通过环境变量动态切换 Langfuse 与 MLflow，并在前端平台提供对应的会话链路诊断与大盘透视；同时完成远端 `mlflow-eval-platform` 跨域与嵌入解禁配置。
- **负责人：** @老王
- **模板类型：** 标准模板
- **状态：** 已完成

## 快速导航
- [方案设计](plan.md)
- [任务清单](tasks.md)
- [验证报告](verification.md)

## 核心背景与收益
1. **统一 LLM 可观测双轨制**：支持通过环境变量 `TRACING_PROVIDER=mlflow|langfuse|both|none` 零侵入热切换，Runtime Service、Platform API 与 Platform Web 全链路契约保持一致。
2. **多轮会话（Sessions）与单次调用（Traces）拓扑**：将平台的 `thread_id` 自动注入为 MLflow 的 `mlflow.session_id`，将 `platform_trace_id` 注入为 `client_request_id`，天然对齐平台与 MLflow 的多轮对话聚合视图。
3. **远端与本地 `mlflow-eval-platform` 协同**：解除 `X-Frame-Options` 与 CORS 跨域屏障，前端 `TraceDiagnosticsPage` 与诊断弹窗支持一键直达 MLflow 链路详情树。

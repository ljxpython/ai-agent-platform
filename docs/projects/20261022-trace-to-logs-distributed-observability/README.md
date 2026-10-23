# 分布式全链路追踪与日志关联可观测性工程 (Trace-to-Logs Distributed Observability)

## 项目概述
- **时间：** 2026-10-22 至 2026-10-23
- **目标：** 对标大厂（字节跳动可观测诊断、阿里 ARMS、美团 APM）分布式诊断体系，基于业界成熟的开放标准（W3C TraceContext + Grafana Loki/Tempo + Langfuse 深度对齐），实现“研发/SRE 输入一个 `trace_id`，一屏完整呈现微服务调用链瀑布流、RPC 耗时与故障节点，并联动秒级检索各微服务精确日志”的工业级闭环能力。
- **负责人：** @老王
- **模板类型：** 标准模板
- **状态：** 已完成（`done`；Phase 1~6 全栈交付，W3C 标准透传与结构化打标闭环，生产主机 sshmy1 成功部署 Loki+Promtail 四容器常驻仅 186.47MB；方案 A 自研轻量代理 API 毫秒级直出；彻底根治 Loki 自回声污染与 Langfuse 多租户 404 跨租户报错；大厂排障全景大盘、甘特瀑布流与双视角 Tab 对比全面实装并通过全量单测与端到端自动化验收）

## 快速导航
- [整体方案](plan.md)
- [任务拆分](tasks.md)
- [验证计划](verification.md)
- [现行链路追踪契约](../../standards/trace-propagation.md)

## 改动范围
- **影响服务：**
  - `platform-web`：全链路排障诊断中心组件、Trace-to-Logs 联动视图、审计日志一键穿透排障。
  - `platform-api`：日志结构化规范升级（注入标准 `trace_id` / `span_id` / `service` 标签）、W3C `traceparent` 协议生成与向下传播、新增按 `trace_id` 聚合微服务日志检索接口。
  - `runtime-service`：跨服务 `traceparent` 协议解析与延续、结构化日志对齐、Langfuse 深度执行树与微服务 Span 双向锚定。
  - `运维与部署（sshmy1）`：在生产主机 `sshmy1` 部署轻量级日志采集与检索组件（Grafana Loki + Promtail，总内存预算控制在 80MB 以内），在 Grafana 配置 Trace-to-Logs 黄金联动数据源。
- **改动级别：** 治理改动
- **预计工作量：** 2 人天

## 关键决策
1. **三位一体联动（Metrics + Tracing + Logging）**：
   - 告别孤立工具割裂，以 `trace_id` 为全局锚点，将 Prometheus 指标波动、Langfuse/Tempo 链路树、Loki 微服务日志彻底串联。
2. **轻量极致原则（No Heavy ES / No Fat OTel Collector）**：
   - 坚决拒绝动辄常驻 2G-4G 内存的 Elasticsearch 笨重方案；采用 Grafana Loki 现代日志流引擎（仅建标签索引，极度省内存省 CPU）。
3. **协议标准化（W3C TraceContext）**：
   - 服务间调用采用工业级 `traceparent: 00-{trace_id}-{span_id}-01` 标准头传输，与 OpenTelemetry 规范 100% 兼容。

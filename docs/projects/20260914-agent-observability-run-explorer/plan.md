# Agent 全链路可观测与 Run Explorer - 整体方案

## 背景
Runtime 已接入 Langfuse，但前端无法查看一次运行的完整链路；跨服务 Trace 传播、平台事件查询和 Langfuse 查询边界尚未形成闭环。

## 目标
用户或管理员可按项目权限查看 Run 列表、生命周期时间线、节点/工具/子 Agent 详情、错误归因及 Langfuse/审计关联入口，并支持 SSE 断线后的历史恢复。

## 方案设计

### 整体架构
```text
platform-web → platform-api → runtime-service → interaction-data-service
      │              │              │
      └──── Run Explorer 聚合查询 ───┘
                     │
       OTel SDK → OTel Collector → Jaeger/Tempo
       LangChain Callback → Langfuse
```

### 关键改动点

#### 1. 跨服务关联上下文
- **文件：** 各服务请求中间件、Runtime observability
- **改动：** 统一传播 W3C `traceparent`，保留 `request_id`、`platform_trace_id`、`durable_run_id`、`run_id`、`thread_id`；生成并持久化 `langfuse_trace_id` 关联字段。
- **理由：** 让 API 请求、Runtime Run、OTel Trace 和 Langfuse Trace 可互相定位。

#### 2. 平台 Run/Event 查询契约
- **文件：** `apps/platform-api` Run/Runtime Gateway 模块及数据库模型
- **改动：** 提供 `GET /api/runs`、`GET /api/runs/{id}`、`GET /api/runs/{id}/events`、`GET /api/runs/{id}/links`；按项目权限过滤，事件使用平台 `event_id + sequence`。
- **理由：** Langfuse和上游 SSE 都不能替代平台历史、权限和审计事实源。

#### 3. OTel 自托管链路
- **文件：** `deploy/`、环境契约、服务启动配置
- **改动：** 增加 Collector 配置和 Jaeger 或 Tempo 的首期部署 profile；采样、脱敏、队列和 exporter 故障均 fail-soft。
- **理由：** 用标准链路能力补齐服务间调用，不重复建设 Trace 后端。

#### 4. 前端 Run Explorer
- **文件：** `apps/platform-web/src/modules/` 新增 observability/run-explorer 模块
- **改动：** 列表、详情、时间线、节点详情、错误定位、SSE 历史加载、Langfuse/审计外链。
- **理由：** 提供产品级排障入口，保留 Langfuse 深度分析能力。

#### 5. 数据安全和权限
- **文件：** API 查询授权、事件序列化、Langfuse 配置
- **改动：** 默认只返回 metadata、状态、耗时、Token、资源 ID 和脱敏摘要；Prompt、响应和工具输入输出按配置受控；所有查询继承项目/租户权限。
- **理由：** 观测数据同样可能包含业务敏感信息。

## 技术选型
- **OpenTelemetry：** Apache 2.0，SDK + Collector 自托管。
- **Trace UI/存储：** 首期 Jaeger；规模明确后可切 Tempo + Grafana。
- **Agent 语义 Trace：** 延续现有 Langfuse，不让 OTel 替代它。
- **前端事件源：** Platform API 聚合 Durable Run/Event；不直连 Langfuse。

## 链路影响

### 受影响的调用链路
```text
浏览器操作 → platform-api → runtime-service → Agent graph → Model/Tool/Subagent
                                      ├→ Durable Run/SSE/Event
                                      ├→ Langfuse
                                      └→ OTel Collector → Trace backend
```

### 契约变更
- 请求上下文：增加/规范 `traceparent` 传播和关联 ID。
- Run 查询：新增列表、详情、事件、关联链接接口。
- 运行事件：统一生命周期、消息、工具、子 Agent、错误事件投影。
- 前端类型：增加 Run Explorer 查询和时间线类型。

## 风险和依赖
- **观测后端不可用：** 不得影响 Agent Run → SDK/Collector/exporter fail-soft。
- **数据泄露：** allowlist、脱敏、项目权限和响应大小限制。
- **事件与 Trace 不一致：** Run/Event 仍以平台事实源为准，Langfuse 只做关联和深挖。
- **部署复杂度：** 首期提供可选自托管 profile，不把 Jaeger/Tempo 强绑到核心启动链路。
- **依赖：** 现有 Durable Run/Event 持久化、Runtime SSE 契约、Langfuse 配置和服务部署环境。

## 实施计划
1. Phase 1：冻结关联字段、事件投影和 API 契约，补齐 OTel Collector 本地 profile。
2. Phase 2：实现 Platform API 聚合查询、权限过滤和 Langfuse/审计关联。
3. Phase 3：实现前端 Run Explorer 与 SSE 历史/实时合并。
4. Phase 4：集成、端到端、安全、故障降级和性能验证。

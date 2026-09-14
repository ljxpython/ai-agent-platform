# Agent 全链路可观测与 Run Explorer - 任务拆分

## Phase 1: 基础契约与基础设施

### Task 1.1: 冻结关联 ID 与事件字典
- **文件：** platform-api/runtime-service 相关契约文档与模型
- **改动：** 定义 `durable_run_id`、`run_id`、`thread_id`、`request_id`、`platform_trace_id`、`langfuse_trace_id` 及事件类型、序号规则。
- **状态：** 待开始

### Task 1.2: 接入 OTel SDK/Collector profile
- **文件：** `deploy/`、服务配置和启动入口
- **改动：** 跨服务 HTTP 链路、Collector 脱敏/采样/重试/fail-soft、Jaeger 首期后端。
- **状态：** 待开始

## Phase 2: 平台查询层

### Task 2.1: Run Explorer API
- **文件：** `apps/platform-api`
- **改动：** 列表、详情、事件、关联链接接口，分页、筛选、项目权限。
- **状态：** 待开始

### Task 2.2: 事件投影与 Langfuse 关联
- **文件：** Runtime Gateway/Run Coordinator、数据库迁移
- **改动：** 持久化事件和 Trace 关联；补充审计引用；控制摘要字段。
- **状态：** 待开始

## Phase 3: 前端

### Task 3.1: Run Explorer 列表和详情
- **文件：** `apps/platform-web/src/modules/observability`
- **改动：** 列表筛选、状态、耗时、项目和 Agent 维度；详情头部和时间线。
- **状态：** 待开始

### Task 3.2: 实时/历史事件合并
- **文件：** 前端 Run Explorer composables/services
- **改动：** 历史分页、SSE 订阅、`event_id` 去重、`sequence` 游标恢复。
- **状态：** 待开始

### Task 3.3: 外部关联入口
- **文件：** 前端详情组件
- **改动：** Langfuse Trace、审计记录和请求日志入口。
- **状态：** 待开始

## Phase 4: 验证与发布

### Task 4.1: 跨服务集成和端到端验证
- **状态：** 待开始

### Task 4.2: 故障、安全和性能验证
- **状态：** 待开始

## 进度追踪
- [ ] Phase 1 完成
- [ ] Phase 2 完成
- [ ] Phase 3 完成
- [ ] Phase 4 完成

# Phase 4 P2/P3 - 可观测性、安全与环境治理收口

这份文档把 `phase-4` 里已经真正落地的 `P2 可观测性与稳定性`、`P3 身份/安全/环境治理` 收成一份可验收说明。

## 1. 已落地能力

### 可观测性

- 已增加结构化日志输出：
  - `app/core/observability/logging.py`
  - API 与 worker 都可以打出带 `request_id / trace_id / actor / tenant / project` 的 JSON 日志
- 已增加请求指标注册表：
  - `app/core/observability/metrics.py`
  - 当前先提供进程内聚合视图，避免一上来就把 Prometheus、OTel、Collector 全塞进来搞成一锅粥
- 已增加 request chain：
  - `request_context` 中间件统一生成 `x-request-id` / `x-trace-id`
  - operation metadata 会保留 `_request_chain`
- 已增加 worker heartbeat：
  - worker 空闲、执行中、成功、失败、重试、取消都会更新 heartbeat
  - `/_system/probes/ready` 依赖 heartbeat 判断是否 ready

### 安全治理

- 已增加 service account / API key 第一版：
  - `GET /api/service-accounts`
  - `POST /api/service-accounts`
  - `PATCH /api/service-accounts/{id}`
  - `POST /api/service-accounts/{id}/tokens`
  - `DELETE /api/service-accounts/{id}/tokens/{token_id}`
- 已支持 API key 鉴权：
  - 默认 header：`x-platform-api-key`
  - actor 会标记为 `principal_type=service_account`
- 已明确 OIDC/SSO 边界：
  - 当前只保留边界和配置位
  - 不在 `phase-4` 里强行做半吊子接入

### 环境治理

- 已把环境口径纳入平台快照：
  - `local / dev / staging / prod`
- 已把生产环境保护写入配置校验：
  - `prod` 禁止 docs
  - `prod` 禁止 bootstrap admin
  - `prod` 必须覆盖 JWT secret

### 数据治理

- 已把 artifact retention / cleanup 策略纳入快照
- 已把导出/删除口径纳入治理说明
- 敏感配置只展示脱敏视图，不展示明文

## 2. 当前验证入口

### 系统探针

- `GET /_system/health`
- `GET /_system/probes/live`
- `GET /_system/probes/ready`
- `GET /_system/metrics`
- `GET /_system/platform-config`

### 前端治理页

- `apps/platform-web-vue`
- 页面：`/workspace/platform-config`

当前页面已经可以直接查看：

- requests 指标
- worker heartbeat 列表
- operations 执行统计
- service account 概览
- OIDC 边界
- 环境与数据治理快照
- feature flags 热治理
- `Service Accounts` 正式治理页
- `System Probes` 正式治理页

## 3. 为什么先这样做

这轮目标是把平台做成“最小可治理控制面”，不是为了看起来高级就先堆一堆中间件。

所以当前刻意采用了这条路线：

- 先把 request / worker / operation 三条链路打通
- 先把 probes、metrics、heartbeat、API key 做成真实可用能力
- 先把环境边界、敏感配置、数据治理口径钉死
- 然后再为下一阶段接 Prometheus / OTel / OIDC 真接入预留位置

这个顺序的好处是：

- 本地和演示环境能先跑通
- 前后端能先验收真实治理页
- 后面上 Redis、PG、SSO、监控平台时不需要推翻当前结构

## 4. 下一阶段建议

### 可观测性

- 接 Prometheus exporter
- 接 OpenTelemetry trace/span
- 增加 worker backlog / executor failure 分类指标

### 安全治理

- 增加 service account 最小权限模板
- 增加 token rotate / expire 提醒
- 按环境推进 OIDC 真接入

### 环境治理

- 增加配置源优先级说明
- 增加 staging/prod 部署清单和值班手册联动

## 5. 手动验收建议

1. 启动 `platform-api-v2` 和 `worker`
2. 访问 `/_system/probes/live`
3. 访问 `/_system/probes/ready`
4. 用管理员创建一个 service account 和 token
5. 用 token 访问 `/_system/metrics`
6. 打开前端 `Platform Config` 页面
7. 确认 requests / workers / security / environment / governance 都能看到快照

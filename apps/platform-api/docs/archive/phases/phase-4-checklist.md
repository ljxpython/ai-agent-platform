# Platform API V2 第四阶段执行清单

这份清单是 `phase-3` 之后的下一阶段规划。

它不和 `phase-3` 抢活，只有在 `phase-3` 的核心治理项收口后才正式进入执行。

phase-4 的目标不是再继续搭基础，而是把已经成型的控制面推进到“可交付、可维护、可扩展”的生产化阶段。

## P0 进入条件冻结

- [ ] `phase-3 / P1 policy overlay` 完成并经过前端验收
- [ ] `phase-3 / P2 operations 治理页` 完成并经过前端验收
- [ ] `phase-3 / P3 PostgreSQL 切主` 完成并成为默认开发口径
- [ ] `phase-3 / P4 平台配置治理入口` 完成并具备权限与审计
- [ ] `phase-3 / P5 release / harness 收口` 完成

## P1 operation 与异步能力生产化

- [x] 为 worker 增加并发 claim / 幂等防重 / retry 边界
- [x] 选型并接入正式 Redis queue backend
- [x] 为 export artifact 增加保留期、清理和对象存储外接策略
- [x] 为 operation 增加通知反馈通道（polling 优化、SSE 或 websocket 其一）
- [x] 为 operation 增加批量查询、筛选和归档策略

### P1 当前收口说明

- `worker` 已完成候选列表 + 条件 update 的 claim 语义，降低多 worker 双重消费风险。
- `worker` 已支持 `_retry_policy.max_attempts` 和 `_execution` 元数据写回，失败后可重试回队，不再一把打死。
- `operations` 已提供 `GET /api/operations/stream` SSE 通知通道，前端治理页已接入实时同步，并保留 polling 兜底。
- 审计中间件已适配流式响应，不再吞掉 `text/event-stream`。
- `operations` 已补齐批量取消、批量归档、归档恢复、归档视图切换，以及多状态 / 多 kind / 归档范围筛选。
- export artifact 已补齐：
  - `storage_backend / expires_at / retention_hours` 元数据
  - 本地 sidecar 元数据文件与过期拒绝下载
  - `POST /api/operations/artifacts/cleanup` 手动清理入口
  - `platform-config` 快照中的 artifact retention / cleanup 配置展示
  - 当前后端仍只落 `local` backend，但扩展点已明确，不需要重写治理层
- Redis queue backend 已补齐第一版：
  - `operations_queue_backend=redis_list`
  - `operations_redis_url`
  - `operations_redis_queue_name`
  - submit dispatch -> Redis list
  - worker dequeue -> 按 operation_id 条件 claim
  - retry requeue -> 重新 dispatch 入队
  - `db_polling` 仍保留为本地 / 演示默认口径

## P2 可观测性与稳定性

- [x] 为 `platform-api-v2` 增加结构化日志规范
- [x] 为 API / worker 增加核心指标（请求量、失败率、worker backlog、执行时长）
- [x] 为关键模块增加 tracing / request chain 追踪口径
- [x] 为 worker 增加心跳、存活探针和异常恢复策略
- [x] 输出平台故障排查与值班手册初版

## P3 身份、安全与环境治理增强

- [x] 评估并设计 OIDC / SSO 接入边界
- [x] 设计平台 API key / service account 能力
- [x] 补齐环境隔离策略（local / dev / staging / prod）
- [x] 补齐敏感配置脱敏、轮换与审计要求
- [x] 补齐数据导出、删除和留存的治理口径

## P4 交付与发布工程化

- [x] 补齐 Docker / compose / deploy 示例
- [x] 补齐数据库初始化、迁移、备份、恢复脚本规范
- [x] 建立最小 CI 流水线（lint / typecheck / smoke / build）
- [x] 建立 release note / tag / rollback 标准模板
- [x] 为前后端联调提供一份一键启动或最小启动脚本规范

## P5 Harness 与开发者范式沉淀

- [x] 把 phase-1 ~ phase-4 的关键文档压成开发者入口
- [x] 为新模块开发补齐“从 checklist 到验收”的模板
- [x] 为前端 `platform-web-vue` 补齐 control plane 模块接入范式
- [x] 为后端 `platform-api-v2` 补齐模块脚手架与用例样板
- [x] 为 AI 协作补齐 Harness 最佳实践、常见陷阱和验收门槛

## P2/P3/P4/P5 收口说明

- `P2` 已补齐：
  - 结构化日志
  - 进程内请求指标
  - `request_id / trace_id / request chain`
  - worker heartbeat
  - `/_system/probes/live`
  - `/_system/probes/ready`
  - `docs/delivery/runbook.md`
- `P3` 已补齐：
  - service account / API key 第一版
  - OIDC/SSO 边界快照
  - 环境分层与生产保护校验
  - 敏感配置脱敏视图
  - 数据治理快照
  - `platform-web-vue` 的 `Service Accounts` 正式治理页
  - `Service Accounts` 的描述编辑、角色切换、token 搜索、撤销确认
- `P2` 前端治理展示已补齐：
  - `Control Plane` 统一组合页
  - `System Probes` 页面
  - `System Probes` 值班风险面板、趋势图、worker heartbeat 详情
  - `Platform Config` 页面中的 observability / workers / security / governance 快照
- `P4` 已补齐：
  - `Dockerfile`
  - `deploy/docker-compose.example.yml`
  - `scripts/init_db.py`
  - `scripts/backup_db.sh`
  - `scripts/restore_db.sh`
  - `.github/workflows/ci.yml`
  - `docs/delivery/release-template.md`
- `P5` 已补齐：
  - `docs/README.md` 开发者入口
  - `docs/archive/phases/phase-4-p5-harness-and-templates.md`
  - `docs/handbook/development-playbook.md`
  - 前端 `platform-config` 正式治理展示

## 当前建议执行顺序

1. 先把 `phase-3` 做完整，不要跳着做
2. `phase-4` 进入后先做 `P1 operation 与异步能力生产化`
3. 再做 `P2 可观测性与稳定性`
4. 然后推进 `P3 身份、安全与环境治理增强`
5. 最后用 `P4/P5` 收交付与开发范式

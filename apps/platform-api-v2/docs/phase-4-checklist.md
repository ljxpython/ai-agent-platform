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

- [ ] 为 worker 增加并发 claim / 幂等防重 / retry 边界
- [ ] 选型并接入正式 Redis queue backend
- [ ] 为 export artifact 增加保留期、清理和对象存储外接策略
- [ ] 为 operation 增加通知反馈通道（polling 优化、SSE 或 websocket 其一）
- [ ] 为 operation 增加批量查询、筛选和归档策略

## P2 可观测性与稳定性

- [ ] 为 `platform-api-v2` 增加结构化日志规范
- [ ] 为 API / worker 增加核心指标（请求量、失败率、worker backlog、执行时长）
- [ ] 为关键模块增加 tracing / request chain 追踪口径
- [ ] 为 worker 增加心跳、存活探针和异常恢复策略
- [ ] 输出平台故障排查与值班手册初版

## P3 身份、安全与环境治理增强

- [ ] 评估并设计 OIDC / SSO 接入边界
- [ ] 设计平台 API key / service account 能力
- [ ] 补齐环境隔离策略（local / dev / staging / prod）
- [ ] 补齐敏感配置脱敏、轮换与审计要求
- [ ] 补齐数据导出、删除和留存的治理口径

## P4 交付与发布工程化

- [ ] 补齐 Docker / compose / deploy 示例
- [ ] 补齐数据库初始化、迁移、备份、恢复脚本规范
- [ ] 建立最小 CI 流水线（lint / typecheck / smoke / build）
- [ ] 建立 release note / tag / rollback 标准模板
- [ ] 为前后端联调提供一份一键启动或最小启动脚本规范

## P5 Harness 与开发者范式沉淀

- [ ] 把 phase-1 ~ phase-4 的关键文档压成开发者入口
- [ ] 为新模块开发补齐“从 checklist 到验收”的模板
- [ ] 为前端 `platform-web-vue` 补齐 control plane 模块接入范式
- [ ] 为后端 `platform-api-v2` 补齐模块脚手架与用例样板
- [ ] 为 AI 协作补齐 Harness 最佳实践、常见陷阱和验收门槛

## 当前建议执行顺序

1. 先把 `phase-3` 做完整，不要跳着做
2. `phase-4` 进入后先做 `P1 operation 与异步能力生产化`
3. 再做 `P2 可观测性与稳定性`
4. 然后推进 `P3 身份、安全与环境治理增强`
5. 最后用 `P4/P5` 收交付与开发范式

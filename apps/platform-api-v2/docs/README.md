# Platform API V2 文档导航

当前 `apps/platform-api-v2` 以“先定规则，再写业务”为原则推进。

优先阅读顺序：

1. `architecture-v2.md`
   - 目标服务边界、目录骨架、模块划分和长期形态
2. `engineering-standards.md`
   - 平台后端开发规范、权限/审计标准和 AI Harness 工作流
3. `permission-standard.md`
   - 平台级 / 项目级授权模型、策略判定和测试基线
4. `audit-standard.md`
   - 审计事件模型、命名、分页和脱敏规则
5. `operations-standard.md`
   - 长任务、operation/job、worker / queue 接入方式
6. `harness-playbook.md`
   - 人和 AI 代理在 `platform-api-v2` 中的统一工作流
7. `first-batch-module-map.md`
   - 第一批模块迁移顺序、旧接口映射和前后端协同顺序
8. `frontend-switch-strategy.md`
   - `platform-web-vue` 如何逐步切换到新的控制面
9. `phase-1-checklist.md`
   - 第一阶段可执行任务清单
10. `phase-2-checklist.md`
   - 第二阶段执行清单、优先级和进展维护规则
11. `phase-2-p1-runtime-workspace.md`
   - 运行工作台稳定化的共享基座、改造点和验证结果
12. `phase-2-governance-baseline.md`
   - operations、platform-config、PostgreSQL/Redis 边界和前端 service 收口
13. `phase-2-smoke-checklist.md`
   - 第二阶段演示与验收 smoke 清单
14. `phase-2-completion.md`
   - 第二阶段完成记录
15. `phase-2-release-draft.md`
   - 第二阶段 release / tag / changelog 草案
16. `phase-3-checklist.md`
   - 第三阶段执行清单
17. `phase-3-p0-operations-worker.md`
   - operations worker、queue 方案、手动启动和验收路径
18. `phase-3-p1-runtime-policies.md`
   - runtime policy overlay 的存储、接口和前端治理页收口
19. `phase-3-p2-operations-center.md`
   - operations 正式治理页、统一异步反馈流与 artifact 下载收口
20. `phase-3-p4-platform-config.md`
   - platform-config 治理入口、feature flags、权限与审计收口
21. `phase-3-completion.md`
   - 第三阶段完成说明、验证结果和 phase-4 入口
22. `phase-3-chat-acceptance-checklist.md`
   - chat 页面前端手动验收清单
23. `phase-4-checklist.md`
   - phase-3 之后的生产化、交付化与 Harness 收口规划
24. `postgres-baseline.md`
   - PostgreSQL 开发基线、Alembic 命令和数据库切换规则

常用启动入口：

- 仓库根目录：`bash "./scripts/platform-web-vue-demo-up.sh"`
- 健康检查：`bash "./scripts/platform-web-vue-demo-health.sh"`
- 停止：`bash "./scripts/platform-web-vue-demo-down.sh"`

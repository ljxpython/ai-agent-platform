# Platform API V2

`apps/platform-api-v2` 是新的平台控制面后端主战场。

它不是对 `apps/platform-api` 的小修小补，也不是兼容层，而是一套按最佳范式重建的控制面：

- 只负责平台治理、权限、审计、资源目录、操作中心和受控网关
- 不承接 `runtime-service` 的 agent 执行业务逻辑
- 不以兼容旧目录结构为目标
- 以后平台前端 `apps/platform-web-vue` 将逐步切到这一套控制面

## 当前目标

当前阶段先完成 3 件事：

1. 搭建模块化单体控制面的干净骨架
2. 沉淀平台后端的开发范式、规范、标准和 AI Harness
3. 为后续权限、审计、operation/job、adapter、worker 重构准备落点

当前已落地的样板模块：

- `identity`
- `projects`
- `users`
- `announcements`
- `audit`
- `operations`
- `assistants`
- `runtime_catalog`
- `runtime_gateway`
- `testcase`

当前 `testcase` 模块已经不只是只读样板，而是完整的 control-plane 聚合样板：

- `overview / role / batches / batch detail`
- `cases list / detail / create / update / delete / export`
- `documents list / detail / relations / export / preview / download`
- 真实数据仍由 `interaction-data-service` 持有，`platform-api-v2` 只负责项目权限、协议整形、导出与前端协同契约

当前开发数据库策略：

- 开发与烟测阶段继续允许使用 SQLite
- PostgreSQL 基线和 Alembic 迁移规范已经预埋
- 等控制面主模块稳定后，再切正式 PG 环境

当前 `operations` 已进入 phase-3 的第一批真实落地：

- `dispatcher / executor / worker` 已经具备正式代码落点
- 当前本地与演示环境默认走 `db_polling` queue
- `runtime refresh / assistant resync / testcase export` 已接入真实异步执行
- export operation 已支持 artifact 持久化与下载
- worker 与 lifecycle audit 已经可独立启动验证

## 设计原则

- 平台控制面和运行时执行面严格分离
- Route 变薄，use case 明确，repository 按模块拆分
- 权限分为平台级与项目级两层，不混用
- 审计必须可检索、可追责、可统计
- 所有外部依赖统一走 adapter
- 长耗时动作统一进入 `operations`
- 从第一天开始为分布式和 worker 演进预留结构

## 目录骨架

```text
apps/platform-api-v2/
├── app/
│   ├── adapters/
│   ├── bootstrap/
│   ├── core/
│   ├── entrypoints/
│   └── modules/
├── docs/
├── main.py
└── pyproject.toml
```

## 文档入口

优先阅读：

1. `docs/architecture-v2.md`
2. `docs/engineering-standards.md`
3. `docs/permission-standard.md`
4. `docs/audit-standard.md`
5. `docs/operations-standard.md`
6. `docs/harness-playbook.md`
7. `docs/frontend-switch-strategy.md`
8. `docs/phase-1-checklist.md`
9. `docs/phase-2-checklist.md`
10. `docs/phase-2-p1-runtime-workspace.md`
11. `docs/phase-2-governance-baseline.md`
12. `docs/phase-2-smoke-checklist.md`
13. `docs/phase-2-completion.md`
14. `docs/phase-2-release-draft.md`
15. `docs/phase-3-checklist.md`
16. `docs/phase-3-p0-operations-worker.md`
17. `docs/phase-3-p1-runtime-policies.md`
18. `docs/phase-3-p2-operations-center.md`
19. `docs/phase-3-p4-platform-config.md`
20. `docs/phase-3-completion.md`
21. `docs/phase-3-chat-acceptance-checklist.md`
22. `docs/phase-4-checklist.md`

## 和旧平台后端的关系

- `apps/platform-api`：旧控制面，保留用于参考与回退
- `apps/platform-api-v2`：新的正式重构目标

当前不做的事情：

- 不复制旧实现继续堆功能
- 不迁入 `runtime-service` 的 graph/tool/modeling 逻辑
- 不为了旧接口兼容而破坏新的控制面结构

## 当前最小启动目标

当前最小可演示口径：

- `platform-api-v2` 能独立启动
- `worker.py` 能独立启动
- `admin / admin123456` 能登录
- `test / test123456` 能登录
- runtime refresh 能通过 operation 真实异步执行
- 文档与目录结构可继续作为后续开发标准

具体开发约束、Harness 思想和启动口径见：

- `docs/engineering-standards.md`
- `docs/harness-playbook.md`
- `docs/phase-3-p0-operations-worker.md`
- `docs/phase-3-completion.md`

## 一键启动

推荐直接在仓库根目录执行：

```bash
bash "./scripts/platform-web-vue-demo-up.sh"
```

健康检查：

```bash
bash "./scripts/platform-web-vue-demo-health.sh"
```

停止：

```bash
bash "./scripts/platform-web-vue-demo-down.sh"
```

启动成功后访问：

- 前端：`http://127.0.0.1:3000`
- 平台后端 V2：`http://127.0.0.1:2142/docs`

演示账号：

- 管理员：`admin / admin123456`
- 普通账号：`test / test123456`

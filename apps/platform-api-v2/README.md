# Platform API V2

`apps/platform-api-v2` 是当前正式平台控制面后端。

它按当前仓库的 control-plane 范式组织：

- 只负责平台治理、权限、审计、资源目录、操作中心和受控网关
- 不承接 `runtime-service` 的 agent 执行业务逻辑
- 不把运行时建模、tool、graph 逻辑拉回控制面
- 为 `apps/platform-web-vue` 提供正式平台 API

当前阶段状态：

- `Phase B: Control Plane Freeze` 已完成
- `Phase C: Data & Delivery Freeze` 已完成
- `Phase D: Final Standard Freeze` 已完成

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

## Runtime Contract 投影原则

`platform-api-v2` 对 `runtime-service` 的参数认知，统一按新 contract 投影：

- `context`：公共业务运行时，直接对应 `RuntimeContext`
- `config`：执行控制字段，不再承接业务运行参数
- `config.configurable`：线程 / 平台 / 鉴权 / 服务私有字段

明确不再做的事情：

- 不再解析 `AppRuntimeConfig`
- 不再把 `model_id / system_prompt / enable_tools / tools` 当成 `config.configurable` 主入口
- 不再把 `runtime_service/runtime/options.py` 这类已删除入口当真源

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

1. `docs/README.md`
2. `docs/handbook/project-handbook.md`
3. `docs/handbook/architecture.md`
4. `docs/handbook/development-playbook.md`
5. `docs/standards/permission-standard.md`
6. `docs/standards/audit-standard.md`
7. `docs/standards/operations-standard.md`
8. `docs/delivery/change-delivery-checklist.md`
9. `docs/delivery/module-delivery-template.md`
10. `docs/delivery/runbook.md`

## 当前定位

- `apps/platform-api-v2` 是当前唯一正式控制面宿主
- `apps/platform-web-vue` 通过这一套 control plane 使用平台治理能力
- 运行时执行仍由 `runtime-service` 负责

当前不做的事情：

- 不把控制面做成万能后端
- 不迁入 `runtime-service` 的 graph/tool/modeling 逻辑
- 不新增第二套正式 control plane 宿主

## 当前最小启动目标

当前最小可演示口径：

- `platform-api-v2` 能独立启动
- `worker.py` 能独立启动
- `admin / admin123456` 能登录
- `test / test123456` 能登录
- runtime refresh 能通过 operation 真实异步执行
- 文档与目录结构可继续作为后续开发标准

具体开发约束、Harness 思想和启动口径见：

- `docs/handbook/project-handbook.md`
- `docs/handbook/development-playbook.md`
- `docs/handbook/architecture.md`

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

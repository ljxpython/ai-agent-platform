# Phase 2 治理与部署基线

这份文档承接 `phase-2-checklist.md` 中的 `P2 + P3 + P4` 关键结论。

## 1. operations 首版

本轮已落地：

- 模块目录：
  - `app/modules/operations/domain`
  - `app/modules/operations/application`
  - `app/modules/operations/infra`
  - `app/modules/operations/presentation`
- 路由：
  - `POST /api/operations`
  - `GET /api/operations`
  - `GET /api/operations/{id}`
  - `POST /api/operations/{id}/cancel`
- 数据库表：
  - `operations`
- 前端服务层：
  - `src/services/operations/operations.service.ts`

当前状态机固定为：

- `submitted`
- `running`
- `succeeded`
- `failed`
- `cancelled`

当前 phase-2 首版只先承担：

- 提交
- 查询详情
- 列表
- 取消

它先解决“长任务有正式治理落点”这个问题，不在当前阶段硬塞 worker 进来。

## 2. 哪些动作纳入 operations

第二阶段已经明确，后续优先接入：

- `runtime.models.refresh`
- `runtime.tools.refresh`
- `runtime.graphs.refresh`
- `assistant.resync`
- `testcase.cases.export`
- `testcase.documents.export`
- `runtime_gateway.thread.resync`

当前处理策略：

- 协议先统一
- 前端先走正式 service
- 真正异步执行和 worker 编排放到 phase-3

## 3. 平台配置入口

本轮新增：

- `GET /_system/platform-config`
- 前端对应 service：
  - `src/services/system/platform-config.service.ts`

当前返回：

- service 基本信息
- 数据库运行口径
- auth 口径
- runtime 上游接入状态
- feature flags

这个入口当前解决两个问题：

1. 平台演示和 smoke 不再靠人脑记配置
2. 前端后续做治理页、环境页、功能开关页时有固定入口

## 4. policy overlay 当前落点

phase-2 明确结论：

- `policy overlay` 仍归 `runtime_catalog` 负责
- 当前阶段只冻结落点和接入方向，不把它仓促做成散装 JSON 配置页

推荐结构：

```text
project
  -> runtime policy overlay
       -> models allowlist / denylist
       -> tools allowlist / denylist
       -> graph exposure flags
       -> future safety / quota knobs
```

phase-2 先做这三件事：

- 把文档和模块边界定死
- 不让页面层自己发明 policy 结构
- 在 `platform-config` 里给 future feature flags 留出口

phase-3 再做真正的：

- 写库模型
- 项目级读写 API
- 前端配置页

## 5. 权限与审计命名

本轮新增权限码：

- `platform.operation.read`
- `platform.operation.write`
- `platform.config.read`
- `project.operation.read`
- `project.operation.write`

对应代码落点：

- `app/modules/iam/application/policies.py`

本轮新增审计动作命名：

- `system.config.read`
- `operation.item.submitted`
- `operation.collection.listed`
- `operation.item.read`
- `operation.item.cancelled`

对应落点：

- `app/entrypoints/http/middleware/audit_log.py`

## 6. PostgreSQL / Alembic / Redis 边界

phase-2 已冻结的结论：

- 正式 schema 变更统一走 Alembic
- `operations` 新增 revision：
  - `20260406_0002_add_operations_table.py`
- SQLite 仍允许做轻量 smoke
- PostgreSQL 仍是正式开发 / 验收基线

Redis / queue 当前不强行接入，但边界已经定死：

- HTTP 只负责提交 operation
- operation 状态独立存储
- 真正执行器未来走 dispatcher / worker
- 切 Redis 只替换 dispatch 和 execution，不回改 handler 协议

## 7. 前端 phase-2 收口结论

`platform-web-vue` 当前正式新增的 phase-2 前端收口内容：

- runtime 工作台统一 service：
  - `src/services/runtime-gateway/workspace.service.ts`
- operations 正式 service：
  - `src/services/operations/operations.service.ts`
- platform config 正式 service：
  - `src/services/system/platform-config.service.ts`
- `control-plane` 模块枚举新增：
  - `system`
  - `operations`

这意味着后续页面如果要接：

- 操作中心
- 平台配置页
- 运行治理页

都不需要再从页面里硬拼 URL。

## 8. 本地 / 演示 / 未来生产三套口径

### 本地开发

- `platform-api-v2` 允许 SQLite smoke
- `platform-web-vue` 允许直接联本机服务
- bootstrap admin 允许开启

### 演示环境

- 必须开启平台数据库
- 推荐固定 demo 账号
- `platform-config` 可用于确认当前服务版本、环境和关键开关

### 未来生产

- PostgreSQL + Alembic
- bootstrap admin 关闭
- docs 关闭
- operation 执行切到真正 worker / queue

## 9. phase-2 的定位

phase-2 到这里的目标不是“平台已经分布式化”，而是：

- 控制面结构不再是临时脚手架
- 运行工作台稳定
- operation / config / migration / deployment 都有正式落点
- phase-3 可以在这套基线下继续往前推，不需要推翻重来

# Runtime 数据库仓储模式重构与 Schema 契约治理专项

## 项目概述
- **时间：** 2026-09-30 至 2026-10-15
- **目标：** 消除当前 `runtime-service`“幽灵数据层”（无实体定义，以迁移脚本为唯一事实源）与“原生 SQL 散落各个深层业务目录”的架构反模式，建立 `db/schema.py` 强类型契约层与 `db/repositories/` 轻量仓储层，在零 ORM 性能开销的前提下实现业务层与数据持久化的清晰解耦。
- **负责人：** @laowang
- **模板类型：** 标准模板
- **状态：** 规划中（待方案评审）

## 快速导航
- [整体方案](plan.md)
- [任务拆分](tasks.md)
- [验证记录](verification.md)

## 改动范围
- **影响服务：** `apps/runtime-service`
- **改动级别：** 治理改动（涉及执行层数据访问架构重构）
- **预计工作量：** 3 人天

## 关键决策
1. **坚决不用重型 ORM**：放弃引入 SQLAlchemy ORM 复杂的 Session 与脏检查机制，继续以 `psycopg` (v3) 为底层引擎，保留原生微秒级吞吐与原生咨询锁支持。
2. **三层骨肉分离**：将 `runtime_service/db/` 重构为 `schema.py`（纯类型契约事实源）+ `repositories/`（收敛原生 SQL）+ `migrations/`（纯版本演进历史）。
3. **渐进式防腐平替**：先建仓储层并补齐单元测试，再自底向上替换 `inbox.py`、`memory.py`、`skill_governance.py` 和 `external_task_storage.py` 中的硬编码 SQL，确保既有图执行与单测 100% 绿色兼容。

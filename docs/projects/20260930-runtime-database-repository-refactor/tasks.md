# Runtime 数据库访问边界收敛与类型补全 - 任务

## 当前进度

- [x] 依据源码修订精简方案及验证计划。
- [x] 用户确认精简方案，2026-10-01 开始实施。

## T1：必要类型

- **改动内容：** 新增实际使用的 `Scope` 类型别名；数据库连接使用 psycopg `Connection` 类型，不复制四表实体。
- **代码位置：** `apps/runtime-service/src/runtime_service/db/schema.py`；`apps/runtime-service/src/runtime_service/db/repositories/`。
- **预期结果：** 类型提示不改变运行时行为。
- **验证项：** `uvx ruff check src tests` 与 `uvx ruff format --check src tests` 通过；仓库未配置独立类型检查器。Python 编译检查通过。
- **状态：** [x] 已完成 2026-10-01。
- **合规检查：** [x] 实现完成；[x] 验证已执行；[x] 进度已更新；CONTEXT/FEATURES 在 T4 统一同步；CHANGELOG 跳过（refactor）。

## T2：抽取 Memory SQL

- **改动内容：** 将查询和 upsert 提取为接收外层连接的函数；默认文档、revision、epoch、咨询锁和取消回滚保留在存储类。
- **代码位置：** `apps/runtime-service/src/runtime_service/db/repositories/memory.py`；`apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py`。
- **预期结果：** 现有 API、SQL 参数、事务语义兼容。
- **验证项：** Memory 契约、治理与 Skills 重启定向联合测试 43 passed（显式配置 PostgreSQL DSN，无跳过）。
- **状态：** [x] 已完成 2026-10-01，见 [实施记录](implementation/01-memory-skills-sql.md)。
- **合规检查：** [x] 实现完成；[x] 验证已执行；[x] 进度已更新；CONTEXT/FEATURES 在 T4 统一同步；CHANGELOG 跳过（refactor）。

## T3：抽取 Skills SQL

- **改动内容：** 提取单文档读取、文档/slug 列表、插入、更新和删除；业务规则留在 SkillStorage。
- **代码位置：** `apps/runtime-service/src/runtime_service/db/repositories/skills.py`；`apps/runtime-service/src/runtime_service/services/dearflow_agent/skill_governance.py`。
- **预期结果：** 保留包安全检查、容量限制、scope 隔离、同事务 revision 检查及执行快照恢复。
- **验证项：** 同 T2 的 43 项定向测试，包含真实 PostgreSQL 并发与独立进程重启。
- **状态：** [x] 已完成 2026-10-01，见 [实施记录](implementation/01-memory-skills-sql.md)。
- **合规检查：** [x] 实现完成；[x] 验证已执行；[x] 进度已更新；CONTEXT/FEATURES 在 T4 统一同步；CHANGELOG 跳过（refactor）。

## T4：回归与交付

- **改动内容：** 执行 Runtime 全量回归、质量检查并同步最终状态。
- **代码位置：** `apps/runtime-service/tests/`；本项目文档；`docs/CONTEXT.md`、`docs/FEATURES.md`。
- **预期结果：** 必验 PostgreSQL 场景通过，全量回归结果如实记录；无迁移、Inbox/Tasks 或外部契约变更。
- **验证项：** Runtime 全量 564 passed / 61 skipped / 2 failed；两项失败使用改动前 Memory/Skills 代码复现，详见 verification.md；全量 Ruff check/format check 通过。
- **状态：** [x] 已完成 2026-10-01（本期验收；不代表全仓测试全绿）。
- **合规检查：** [x] 实现完成；[x] 验证已执行；[x] 进度已更新；[x] CONTEXT/FEATURES 已同步；CHANGELOG 跳过（refactor）。

本次未取得代码修改前的测试基线；以下结论仅来自修改后的实际执行，不宣称前后性能对比。最终结果见 verification.md。

# Memory/Skills SQL 抽取

日期：2026-10-01；关联任务：T1—T4。

## 文件与职责

- `apps/runtime-service/src/runtime_service/db/schema.py`：仅新增实际使用的 Scope 类型别名。
- `apps/runtime-service/src/runtime_service/db/repositories/__init__.py`：包入口。
- `apps/runtime-service/src/runtime_service/db/repositories/memory.py`：load_document/save_document，接收外层 psycopg Connection。
- `apps/runtime-service/src/runtime_service/db/repositories/skills.py`：get_document/list_documents/list_slugs/insert_document/update_document/delete_document。
- `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py`：_load/_write 改调函数；原咨询锁和所有业务规则保留。
- `apps/runtime-service/src/runtime_service/services/dearflow_agent/skill_governance.py`：_get/_save/create/documents/delete 替换 SQL；错误映射、revision、容量和包检查保留。

## 关键变化

原 `_load()`：加锁后直接 execute/fetchone。
现 `_load()`：加锁后调用 load_document(db, scope)，只有返回 None 才构造默认文档，避免将空字典当作没有记录。

原 `SkillStorage.create()`：在当前事务中查询 slug 行并检查名称/数量。
现 `SkillStorage.create()`：同一位置调用 list_slugs(db, scope)，业务类仍负责名称和容量判断，再调用 insert_document(db, scope, doc)。

抽取保留 SQL、参数化绑定、查询排序、连接数量及事务范围；SQL 函数没有连接创建/提交/回滚方法，不反向导入业务模块。没有 ORM、通用基类、四表实体或闲置类型。

## 测试与限制

复用现有行为测试，未新建只检查 SQL 调用形式的 Mock 测试。43 项定向测试在真实 PostgreSQL 隔离 schema 中通过，覆盖 Memory CAS/epoch/取消回滚及 Skills 容量竞争、隔离与进程恢复。全量结果见 verification.md。

初次未配置 DSN 导致 24 项跳过，后续显式配置后定向测试全部通过；Ruff 通过 uvx 执行，无须修改项目依赖。

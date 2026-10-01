# Runtime 数据库访问边界收敛与类型补全 - 方案

## 现状与收益

`apps/runtime-service/src/runtime_service/db/__init__.py` 已提供 `connect()`、`normalize_dsn()` 和 `upgrade()`；当前连接由 psycopg 直接创建，并没有连接池或独立的公共 transaction 函数。Alembic 迁移入口已使用 SQLAlchemy，本方案不改变该用途。

`MessageInbox`、`MemoryStorage`、`SkillStorage`、`ExternalTaskStorage` 已承担存储职责。问题集中在 Memory/Skills 将业务规则与 SQL 放在同一个文件，而非完全缺少数据访问层。抽取少量 SQL 可以让业务规则更容易阅读和单独验证，但不会自动提高性能或加强安全性；若只增加无意义转发，则不值得继续扩展。

数据库实际结构以已应用迁移后的数据库为准，迁移脚本描述版本演进和建库约束。Python 类型只描述代码使用的数据，不替代数据库的主键、唯一约束、默认值和字段类型。

## 代码落点

以下均位于 `apps/runtime-service/src/runtime_service/`：

| 文件 | 计划改动与职责 |
|---|---|
| `db/schema.py`（新增） | 定义 Memory/Skills 实际共用的 scope 类型及必要查询结果 TypedDict；每个类型必须有消费者 |
| `db/repositories/__init__.py`（新增） | 最小包入口，不构建注册器或统一导出框架 |
| `db/repositories/memory.py`（新增） | `load_document(db, scope)`、`save_document(db, scope, document)`：查询与 upsert |
| `db/repositories/skills.py`（新增） | 查询单份文档、列出 slug/文档、插入、更新、删除；仅封装现有 SQL |
| `services/dearflow_agent/memory.py` | `_load()`、`_write()` 调用 SQL 函数；保留默认文档、revision、epoch、候选记忆、墓碑和提取状态规则 |
| `services/dearflow_agent/skill_governance.py` | SQL 调用替换；保留包检查、容量、名称、安全检查、revision 校验和摘要生成 |
| `services/dearflow_agent/governance_storage.py` | 复用现有 `lock_scope()` 和 scope 校验，不改锁键编码 |
| `db/__init__.py`、`db/migrations/` | 复用连接与迁移基础设施 |
| `messaging/inbox.py`、`services/dearflow_agent/external_task_storage.py` | 本期不拆分、不新增对应 Repository |

## 类型边界

先补实际使用的稳定类型，保留字典式返回和现有数据处理方式。不要为四张表复制完整 dataclass，也不为本期未改动的 Inbox/Tasks 新建未使用类型。

Memory/Skills 的 JSON 文档包含可选字段和历史兼容路径；本期不全量强类型化文档内容，不增加严格反序列化校验。TypedDict 只提供静态提示，不执行运行时校验；frozen dataclass 也不能冻结其内部字典，因此不以“不可变记录”作为本期目标。

类型应对齐实际查询结果：PostgreSQL UUID/timestamptz 与业务层字符串并不等价，不能直接复制面向 HTTP 的字段类型。SQL 模块不反向导入业务模块。

## 事务与业务边界

调用关系：现有 HTTP/工具/中间件 → MemoryStorage 或 SkillStorage → SQL 函数 → 同一 psycopg 连接。

- 外层存储方法继续使用 `with connect(self.dsn) as db` 控制事务。
- SQL 函数显式接收该连接，不自行 connect、commit、rollback 或关闭连接。
- 咨询锁的获取位置、锁键、持有时间保持原有语义。特别是 Memory `_load()` 当前包含加锁，不能拆成一个独立提交的读取操作。
- 读取、revision 检查、业务修改、写入必须位于同一事务。Skills 当前依赖咨询锁保护读改写，并非 SQL 自带 revision 条件更新。
- Memory 的 `_save()` 保留容量检查和 revision 递增；`_write()` 仍允许更新提取元数据而不递增用户 revision。
- SQL 层读取不存在记录时返回 None；默认文档或 `DocumentError` 由现有业务层处理。
- 参数绑定、tenant/project/user 过滤、排序和返回值保持一致。Skills 写入只更新指定 slug。
- Memory 写入后的取消异常必须继续触发整个事务回滚。

## 不纳入本期

不建立 BaseRepository、通用 CRUD、Unit of Work 或仓储工厂；不增加 ORM、连接池、异步数据库访问、索引或迁移；不搬迁 Inbox/Tasks；不调整锁粒度、租约、fencing、安全检查或错误契约。

不承诺“微秒级吞吐”“1ms 以内”或“零性能衰退”。当前收益是可读性与职责边界；SQL 数量和连接次数应保持一致，性能优化须由后续测量驱动。

## 实施顺序与复评

1. 用户重新评估并确认实施范围。
2. 记录当前测试基线，补实际使用的类型；不创建闲置骨架。
3. 先抽 Memory SQL 并跑相关测试，再抽 Skills SQL 并跑相关测试。
4. 执行 Runtime 回归与质量检查，记录实际通过、失败和跳过项。

若抽取导致更多层间转换、无法保留事务语义，或发现必须调整数据库/安全行为，先明确差异并重新评估，不把这些变化夹带进内部重构。只有出现具体复用需求或可维护性问题，才另行评估 Inbox/Tasks 的拆分。

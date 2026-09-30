# Runtime 数据库仓储模式重构与 Schema 契约治理专项 - 整体方案

## 背景

当前 `runtime-service` 采用双轨制存储（引擎链由 LangGraph 官方托管，应用链由自建表托管）。然而在应用链的代码组织上，存在明显的架构反模式：
1. **“幽灵数据层”**：`apps/runtime-service/src/runtime_service/db/` 根目录下无任何数据结构定义文件，仅有空壳 `__init__.py` 与 `migrations/` 目录。开发者必须去翻 `0001_application.py` 的原始 SQL 字符串才能获知有哪些表和字段，迁移脚本反客为主变成了静态契约事实源。
2. **“原生 SQL 到处裸奔”**：应用链管理的 4 张表（`runtime_message_inbox`、`dear_memory`、`dear_skills`、`dear_external_tasks`），其读写 SQL 散落在 `messaging/inbox.py`、`services/dearflow_agent/memory.py`、`services/dearflow_agent/skill_governance.py` 和 `services/dearflow_agent/external_task_storage.py` 各自业务文件中，难以统一事务、连接治理与防腐审计。

## 目标

1. 在 `apps/runtime-service/src/runtime_service/db/` 下建立纯类型契约层 `schema.py`，使用不可变 `dataclass` 或 `TypedDict` 清晰定义 4 张表的结构，作为系统静态契约的唯一事实源。
2. 建立轻量仓储层 `apps/runtime-service/src/runtime_service/db/repositories/`，收敛上述 4 张表的所有原生 SQL 与咨询锁操作。
3. 重构现有业务模块，将散落在外的硬编码 SQL 替换为仓储接口调用，实现业务逻辑与持久化解耦。
4. 保持微秒级高性能与原生 `psycopg` 架构，坚决不引入庞大低效的重型 ORM。

## 方案设计

### 整体架构

```text
apps/runtime-service/src/runtime_service/db/
├── __init__.py               # 连接池与事务基础设施 (connect, transaction, normalize_dsn)
├── __main__.py              # CLI 升级入口 (python -m runtime_service.db)
│
├── schema.py                # 【第一层：强类型契约事实源】
│                            # 声明 InboxRecord, MemoryDocument, SkillDocument, ExternalTaskRecord
│
├── repositories/            # 【第二层：轻量仓储层 (收敛原生 SQL)】
│   ├── base.py              # 仓储基类与事务上下文绑定
│   ├── inbox_repo.py        # 负责 runtime_message_inbox 的入队、抢占与冲销
│   ├── memory_repo.py       # 负责 dear_memory 的租户隔离读写
│   ├── skills_repo.py       # 负责 dear_skills 的热加载与乐观锁保存
│   └── tasks_repo.py        # 负责 dear_external_tasks 的租约与状态流转
│
└── migrations/              # 【第三层：纯版本演进历史】
    ├── env.py
    └── versions/
        └── 0001_application.py
```

### 关键改动点

#### 1. 建立强类型契约层 `schema.py`
- **文件：** `apps/runtime-service/src/runtime_service/db/schema.py`
- **改动：** 定义 `InboxMessageRecord`、`DearMemoryRecord`、`DearSkillRecord`、`DearExternalTaskRecord` 等强类型只读数据类。
- **理由：** 确立数据库事实源，让代码可读、IDE 智能补全，杜绝手写拼写错误。

#### 2. 实现轻量仓储模块 `db/repositories/`
- **文件：**
  - `db/repositories/inbox_repo.py`
  - `db/repositories/memory_repo.py`
  - `db/repositories/skills_repo.py`
  - `db/repositories/tasks_repo.py`
- **改动：** 将各自的原生 SQL 移植并封装为清晰的函数/方法接口（如 `enqueue_message()`, `claim_messages()`, `get_memory()`, `save_memory()` 等）。
- **理由：** 关注点分离，集中管理 SQL 语句与参数化绑定，消除注入风险，便于统一单测与 Mock。

#### 3. 平替业务模块中的原生 SQL 散落代码
- **文件：**
  - `messaging/inbox.py`
  - `services/dearflow_agent/memory.py`
  - `services/dearflow_agent/skill_governance.py`
  - `services/dearflow_agent/external_task_storage.py`
- **改动：** 业务层初始化对应 Repository 实例，调用其纯方法完成交互。
- **理由：** 业务代码专注 Agent 编排，不再污染任何数据表 DDL 与查询字符串。

### 技术选型
- **选型 1：继续使用 `psycopg` (v3) + 原生 SQL**：绝不使用 SQLAlchemy ORM，保障毫秒级推理吞吐与极低内存开销。
- **选型 2：不可变数据结构 (`dataclass(frozen=True)`)**：仓储层查询结果返回只读不可变记录，防止业务层就地篡改。

## 链路影响

### 受影响的调用链路
```text
HTTP Request / Agent Step
    ──► 业务模块 (inbox.py / memory.py)
    ──► db.repositories (收敛的仓储方法)
    ──► db.connect() (psycopg 原生连接)
    ──► PostgreSQL
```

### 契约变更
- **对外 HTTP / Agent 契约：** 完全零变更（向下兼容）。
- **内部 Python 契约：** 数据库访问统一通过 `runtime_service.db.repositories` 模块导出。

## 风险和依赖
- **风险 1：SQL 移植过程中参数绑定疏漏** → **应对：** 为每个 Repository 编写 100% 覆盖的单元测试与集成测试，验证参数化绑定的严格正确性。
- **风险 2：并发事务与咨询锁释放失效** → **应对：** 仓储层继承原有的事务上下文管理器，确保连接与锁原子归还连接池。

## 实施计划
1. **Phase 1: 基础设施与契约定义**：创建 `db/schema.py` 与各 Repository 骨架及单测。
2. **Phase 2: 渐进式业务平替**：按 `inbox` -> `memory` -> `skills` -> `tasks` 顺序逐个替换现有硬编码 SQL。
3. **Phase 3: 架构验收与全量回归**：执行原有全部 534 项单测并验证脱机运行兼容性。

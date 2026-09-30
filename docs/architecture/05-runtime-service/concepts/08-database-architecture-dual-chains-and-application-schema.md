# 08-Runtime 数据库双轨制架构与应用表全景透析 (Runtime Database Architecture: Dual Chains & Application Schemas)

> **所属模块**：`apps/runtime-service/src/runtime_service/db/`
> **核心概念**：双轨制存储（Engine Chain vs Application Chain）、无 ORM 原生 SQL 设计、Alembic 原子迁移 (`0001_application.py`)、四大约束表 (`inbox`, `memory`, `skills`, `external_tasks`)
> **涉及文件**：
> - 数据库入口与原子热升级：[`db/__init__.py`](../../../apps/runtime-service/src/runtime_service/db/__init__.py)
> - 命令行迁移入口：[`db/__main__.py`](../../../apps/runtime-service/src/runtime_service/db/__main__.py)
> - 权威应用表 DDL 定义：[`db/migrations/versions/0001_application.py`](../../../apps/runtime-service/src/runtime_service/db/migrations/versions/0001_application.py)

---

## 零、老王说人话：代码少不等于不存东西！（30秒极速通透）

很多从传统 Web 开发（Django、FastAPI、Spring Boot）转过来的同学，点开 [`apps/runtime-service/src/runtime_service/db/`](../../../apps/runtime-service/src/runtime_service/db/) 目录时，第一眼往往是懵逼的：
*“艹？怎么这个目录光秃秃的？没有十几个 `models.py`？没有庞大的 ORM 类定义？难道整个底座是个不需要存数据的无状态玩具？”*

**老王痛骂：谁告诉你没有 ORM 就是不存东西了？！这恰恰体现了世界级 Agent 架构的高明之处——双轨制存储（Dual-Chain Storage）！**

底座把数据库彻底切成了**两条井水不犯河水的独立链条**：

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                       【Runtime 数据库双轨制存储全景】                         │
│                                                                             │
│  【轨道 1：引擎链 (Engine Chain)】            【轨道 2：应用链 (Application Chain)】   │
│   由 LangGraph / GraphHarbor 官方接管          由 runtime_service/db 显式接管       │
│                                                                             │
│   ├── checkpoints (增量状态快照)               ├── runtime_message_inbox (消息收件箱) │
│   ├── checkpoint_blobs (大对象/消息体)        ├── dear_memory (长期记忆文档)         │
│   ├── checkpoint_writes (节点写入缓冲)         ├── dear_skills (动态自定义技能)       │
│   └── checkpoint_migrations (引擎版本表)      └── dear_external_tasks (外部长任务)   │
│                                                                             │
│   特点：官方底座黑盒驱动，开箱即用，             特点：底座业务专属表，轻量 psycopg 原生 │
│         业务代码坚决不重复造轮子！                    SQL 驱动，Alembic 原子迁移防漂移！│
└─────────────────────────────────────────────────────────────────────────────┘
```

1. **引擎链（不需要写代码）**：LangGraph 原生负责图执行的状态机，官方的 `PostgresSaver` 自身就带有一整套建表与增量持久化逻辑。你跑去手写一套 ORM 映射它，除了给自己找麻烦就是纯纯的脱裤子放屁！
2. **应用链（由 `db/` 掌管）**：底座为了支撑**高并发追加消息防丢**、**长期记忆闭环**、**动态技能热加载**与**外部长任务租约**，专门用 Alembic 管理了 **4 张核心应用表**！

---

## 一、轨道一：引擎链（Engine Chain）为什么不需要在 `db/` 写代码？

打开任何一个运行中的 PostgreSQL 实例，你会发现库里有大量的以 `checkpoint_` 开头的表。但你在 `runtime-service` 的源码里搜遍了也找不到它们的 `CREATE TABLE` 语句。

### 官方托管的 4 张引擎表

| 引擎表名 | 官方存储职责 | 为什么底座坚决不写 ORM？ |
| :--- | :--- | :--- |
| `checkpoints` | 记录每个 Thread 在每个 Super-step 产生的状态元数据与版本号。 | LangGraph 官方自带版本演进逻辑，表结构随官方包升级而变更。手写 ORM 会直接焊死官方升级路线。 |
| `checkpoint_blobs` | 存储序列化后的二进制/大文本数据（如大模型输出的 Message、ToolMessage 内容）。 | 纯二进制流读写，ORM 的对象映射开销极大，直接走驱动层字节流才是性能最优解。 |
| `checkpoint_writes` | 存储图节点并行写入同一个通道（Channel）时的待合并缓冲区。 | 复杂的冲突合并数学逻辑在 Pregel 执行核内完成，数据库只负责暂存脏数据。 |
| `checkpoint_migrations` | 记录 LangGraph 官方引擎的迁移版本号。 | 与底座应用迁移彻底解耦，防止官方迁移与业务迁移互相锁死。 |

> **切斯特顿栅栏法则**：
> **不要去封装你不需要修改的东西！** 官方既然已经提供了健壮、高并发安全的 `PostgresSaver`，底座只要在服务启动时传入连接字符串，剩下的完全交给官方引擎。

---

## 二、轨道二：应用链（Application Chain）的四大镇国之宝

打开 [`db/migrations/versions/0001_application.py`](../../../apps/runtime-service/src/runtime_service/db/migrations/versions/0001_application.py)，底座的应用链精准建立了 **4 张企业级核心表**。

每一张表都是为了解决特定的分布式高可用难题而生的：

```sql
-- 1. 外部追加消息保序收件箱 (Message Inbox)
CREATE TABLE IF NOT EXISTS runtime_message_inbox (
    message_id uuid PRIMARY KEY,
    thread_id text NOT NULL,
    target_run_id text NOT NULL,
    sender_id text NOT NULL,
    authorization_ref text,
    idem_key text NOT NULL,
    payload jsonb NOT NULL,
    digest text NOT NULL,
    sequence bigint NOT NULL,
    status text NOT NULL DEFAULT 'queued',
    reason text,
    claim_token uuid,
    claim_until timestamptz,
    consumed_checkpoint_id text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(thread_id, sender_id, idem_key),
    UNIQUE(thread_id, sequence)
);

-- 2. 长期记忆闭环文档表 (Long-term Memory)
CREATE TABLE IF NOT EXISTS dear_memory (
    tenant_id text NOT NULL,
    project_id text NOT NULL,
    user_id text NOT NULL,
    document jsonb NOT NULL,
    PRIMARY KEY (tenant_id, project_id, user_id)
);

-- 3. 自定义技能热加载资产表 (Dynamic Skills)
CREATE TABLE IF NOT EXISTS dear_skills (
    tenant_id text NOT NULL,
    project_id text NOT NULL,
    user_id text NOT NULL,
    slug text NOT NULL,
    document jsonb NOT NULL,
    PRIMARY KEY (tenant_id, project_id, user_id, slug)
);

-- 4. 外部异步长任务状态机账本 (External Tasks)
CREATE TABLE IF NOT EXISTS dear_external_tasks (
    id uuid PRIMARY KEY,
    tenant_id text NOT NULL, project_id text NOT NULL, user_id text NOT NULL,
    graph_id text NOT NULL DEFAULT 'dearflow_agent' CHECK (graph_id='dearflow_agent'),
    thread_id text NOT NULL, origin_run_id text NOT NULL, approval_ref text NOT NULL,
    idem_key text NOT NULL, operation text NOT NULL, request jsonb NOT NULL,
    digest text NOT NULL, status text NOT NULL DEFAULT 'intent',
    result jsonb NOT NULL DEFAULT '{}', error_code text,
    fence bigint NOT NULL DEFAULT 0, lease_until timestamptz,
    attempts integer NOT NULL DEFAULT 0,
    deadline_at timestamptz NOT NULL DEFAULT now()+interval '24 hours',
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(tenant_id,project_id,user_id,thread_id,idem_key),
    CHECK (status IN ('intent','succeeded','unknown'))
);
```

### 四大核心表的作用与死穴解析

| 表名 | 解决的业务痛点 | 关键字段与硬核防御机制 |
| :--- | :--- | :--- |
| **`runtime_message_inbox`** | 用户在 Agent 长时间推理时追加插队消息，防止掉电丢失与乱序并发。 | `UNIQUE(thread_id, sequence)` 强制保证单会话序列号严格单调递增；`claim_token` 与 `claim_until` 保证 Worker 崩溃后 30s 租约超时自愈。 |
| **`dear_memory`** | Agent 跨会话记住用户偏好与关键业务事实（Profile/Session 记忆）。 | 复合主键 `(tenant_id, project_id, user_id)` 形成天然多租户数据绝缘；`document jsonb` 允许动态拓展树形知识拓扑，免去频繁改表结构。 |
| **`dear_skills`** | 用户或 Agent 编写的专用技能（Skills代码与配置）需要持久化并在多 Worker 间同步。 | 主键带 `slug` 唯一技能标识；结合 ZIP 打包与乐观锁，实现执行前毫秒级秒级热加载入沙箱。 |
| **`dear_external_tasks`** | 触发耗时数小时的外部长任务（如长视频渲染、外部部署），支持中断与结果回调。 | `fence bigint` 防脑裂击穿；`deadline_at` 设定 24 小时硬淘汰周期；`idem_key` 杜绝重复下发。 |

---

## 三、为什么坚决不用臃肿的 ORM？（无 ORM 设计哲学）

打开 [`apps/runtime-service/src/runtime_service/db/__init__.py`](../../../apps/runtime-service/src/runtime_service/db/__init__.py)，代码极其干净洗练：

```python
import psycopg
from psycopg.rows import dict_row

def connect(dsn: str | None = None, *, row_factory=dict_row):
    return psycopg.connect(normalize_dsn(dsn), row_factory=row_factory)

def upgrade(dsn: str | None = None) -> None:
    # 核心死穴防护：利用咨询锁防范多节点并发启动时的迁移冲突！
    with engine.begin() as connection:
        connection.exec_driver_sql("SELECT pg_advisory_xact_lock(746183209)")
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
```

### 老王的三大技术选型批判：

1. **毫秒级性能，零反射开销**：
   在 Agent 执行链路中，消息入队、租约抢占是极高频的操作。`psycopg` (v3) 底层是 C/Rust 驱动，直接走二进制网络协议解析 `JSONB` 和 `UUID`。比起 SQLAlchemy ORM 复杂的 Session 管理、对象状态追踪（Identity Map）、脏检查（Dirty Checking），性能提升了整整一个数量级！
2. **PostgreSQL 咨询锁的天然亲和度**：
   `SELECT pg_advisory_xact_lock(746183209)`。如果用传统 ORM，这种会话级/事务级的底层锁操作会与连接池机制发生剧烈冲突。用轻量原生的 `connect()`，锁的生命周期随着事务提交（`commit`）或回滚（`rollback`）自动原子释放，干净利落。
3. **彻底杜绝“跨进程漂移与死锁”**：
   底座是双进程架构（API Server + Worker）。如果双方都维护一套复杂的 ORM 缓存，数据在数据库变了但进程缓存没变，直接发生经典缓存不一致。原生 SQL + `dict_row` 强迫所有节点都以“数据库为唯一的绝对事实源（Single Source of Truth）”。

---

## 四、控制面（Platform-API）与执行面（Runtime）的数据边界划分

很多刚接手项目的同学最容易搞混：**这个数据到底归谁存？**

老王直接给你一张微服务边界裁判表，以后谁乱放数据，直接把这张表甩他脸上：

```text
┌───────────────────────────────────────┬───────────────────────────────────────┐
│     控制面 (platform-api 数据库)       │      执行面 (runtime-service 数据库)   │
│       【管理全局业务关系与治理】        │          【管理执行状态机与资产】      │
├───────────────────────────────────────┼───────────────────────────────────────┤
│ • 用户账号、密码哈希、OAuth 凭据       │ ❌ 绝对不存！只认临时事实小票         │
│ • 企业租户、项目团队、双层 RBAC 权限  │ ❌ 绝对不存！权限在网关处收敛         │
│ • 模型目录、BYOK 密文保险箱 (AES-GCM) │ ❌ 绝对不存！只凭短命票据动态兑换 Key │
│ • 充值计费、Token 配额、审计日志       │ ❌ 绝对不存！交给 Langfuse 与控制面   │
│ • 对话 Thread 元数据 (标题、创建时间) │ ❌ 只由控制面展示，底座只认 thread_id │
├───────────────────────────────────────┼───────────────────────────────────────┤
│ ❌ 不碰底层图状态机与增量快照        │ • LangGraph checkpoints 完整拓扑快照  │
│ ❌ 不管单会话内微秒级消息插队保序     │ • runtime_message_inbox 顺序收件箱    │
│ ❌ 不管 Agent 的动态三层记忆图谱      │ • dear_memory 专属持久化文档          │
│ ❌ 不管沙箱代码里动态挂载的 Skill 代码│ • dear_skills 技能资产与源码          │
│ ❌ 不管外部异步执行租约与防脑裂状态机 │ • dear_external_tasks 异步长任务账本  │
└───────────────────────────────────────┴───────────────────────────────────────┘
```

---

## 五、切斯特顿栅栏对比（Naive 传统架构 vs 生产双轨制）

| 维度 | 传统 Naive 方案 (单体混杂) | 本平台生产级方案 (双轨隔离) | 演进代价与架构收益 |
| :--- | :--- | :--- | :--- |
| **表结构管理** | 所有用户表、业务表、图状态表混在一个大库里，用一套 Alembic 统一维护。 | **双轨制彻底解耦**：官方引擎表由框架包托管，业务应用表由 `0001_application.py` 单独维护。 | **收益**：升级 LangGraph 框架版本绝不污染业务表，迁移互不阻塞；**代价**：需要理解双轨概念。 |
| **持久化开销** | 每次单测执行都必须启动 PostgreSQL 容器，执行全部建表脚本，跑完删库。 | **计算与存储解耦**：本地开发挂载 `InMemorySaver` 零库运行，服务启动才连 Postgres。 | **收益**：单测 0.05 秒搞定，CI 极速反馈；**代价**：要求图逻辑不直接绑定 DB API。 |
| **并发迁移保护** | 多个 Worker Pod 同时启动时，并发执行 `alembic upgrade` 导致锁表冲突死锁。 | 在 `db.upgrade()` 中强行加入 `SELECT pg_advisory_xact_lock(746183209)`。 | **收益**：集群无序滚动部署时，只有一个节点执行迁移，其他节点排队等待，平滑启动。 |
| **表结构强校验** | 迁移脚本只管 `CREATE TABLE`，如果生产环境字段类型被运维手抖改错则不管不问。 | `0001_application.py` 在末尾强制调用 `inspector.get_columns` 逐字段校验类型。 | **收益**：发现历史脏库或类型不兼容当场拒绝启动，杜绝隐性运行态数据破坏。 |

## 六、批判式审视：幽灵数据层与轻量仓储演进方案 (Architectural Critique & Future Evolution)

虽然双轨制成功把官方引擎表与专属应用表彻底解耦，但在目前的工程实现细节上，**代码组织犯了一个极其别扭的架构反模式（Anti-Pattern）**！

### 1. 现状痛点审视：两大架构死穴

1. **罪状一：把迁移脚本（Migration）当成了唯一的事实源（The Ghost Data Layer）**
   - 当前在 `apps/runtime-service/src/runtime_service/db/` 根目录下，**没有任何一个声明表结构的 `.py` 文件**！
   - 任何新开发者想要了解底座管了哪些表、字段类型是什么、约束是什么，必须人肉去翻 `db/migrations/versions/0001_application.py` 这个迁移脚本里的一大坨原始 SQL 字符串。
   - **Alembic 的天职是记录版本变更的差量历史（Delta / Historical Diff），它绝不能作为系统当前静态契约的唯一事实源！**
2. **罪状二：原生 SQL 硬编码“占山为王”，散落在各个深层业务目录**
   - 当前 4 张表的读写逻辑完全没有统一收敛：
     - `runtime_message_inbox` 的 SQL 硬编码在 [`messaging/inbox.py`](../../../apps/runtime-service/src/runtime_service/messaging/inbox.py)；
     - `dear_memory` 的 SQL 硬编码在 [`services/dearflow_agent/memory.py`](../../../apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py)；
     - `dear_skills` 的 SQL 硬编码在 [`services/dearflow_agent/skill_governance.py`](../../../apps/runtime-service/src/runtime_service/services/dearflow_agent/skill_governance.py)；
     - `dear_external_tasks` 的 SQL 硬编码在 [`services/dearflow_agent/external_task_storage.py`](../../../apps/runtime-service/src/runtime_service/services/dearflow_agent/external_task_storage.py)！
   - 一旦未来修改表结构字段名，必须跨越 4 个深层目录人肉全局搜索替换，漏改一个直接引发生产运行时异常。

---

### 2. 演进方案：现代化轻量仓储模式（Lightweight Repository Pattern）

为了彻底治愈上述死穴，且**坚决不退回使用性能低下、概念臃肿的传统 ORM**，平台规划将 `db/` 模块重构成清晰的三层骨肉：

```text
apps/runtime-service/src/runtime_service/db/
├── __init__.py               # 连接池与事务基础设施 (connect, transaction, normalize_dsn)
├── __main__.py              # CLI 升级入口 (python -m runtime_service.db)
│
├── schema.py                # 【第一层：强类型契约事实源】
│                            # 用不可变 dataclass 或 TypedDict 显式声明 4 张表的结构
│                            # (让所有人一眼看懂数据库里存什么，无需去翻迁移脚本！)
│
├── repositories/            # 【第二层：轻量仓储层 (收敛所有原生 SQL)】
│   ├── inbox_repo.py        # 专门负责 runtime_message_inbox 的入队、抢占与冲销
│   ├── memory_repo.py       # 专门负责 dear_memory 的租户隔离读写
│   ├── skills_repo.py       # 专门负责 dear_skills 的热加载与乐观锁保存
│   └── tasks_repo.py        # 专门负责 dear_external_tasks 的租约与状态流转
│
└── migrations/              # 【第三层：纯粹的版本演进历史】
    ├── env.py
    └── versions/
        └── 0001_application.py  # 仅作为落盘版本记录，不再承担设计门面！
```

#### 演进改造收益：
- **事实源清晰明了**：新开发者打开 `db/schema.py` 即可纵览底座全部数据模型；
- **业务代码零 SQL 污染**：业务模块（如 `memory.py`、`inbox.py`）只面向仓储接口编程，脱机单测只需 1 行 Mock 仓储接口，无需手写复杂 SQL 拦截；
- **微秒级性能坚守**：仓储层继续使用原生 `psycopg`，零 ORM 反射与脏检查开销。

> 📌 **重构立项专项**：
> 本重构已正式立项，详见治理改动专项文档：[`docs/projects/20260930-runtime-database-repository-refactor/`](../../../docs/projects/20260930-runtime-database-repository-refactor/README.md)。

---

## 七、架构不变量清单（Invariants）

1. **迁移互斥不变量**：任何节点执行数据库迁移，必须先获取 `pg_advisory_xact_lock(746183209)` 专用咨询锁，严禁在无全局锁的情况下并发变更表结构。
2. **破坏性回滚禁止不变量**：`0001_application.py` 的 `downgrade()` 必须直接 `raise RuntimeError`，生产环境严禁通过自动降级脚本物理删除用户生产数据。
3. **数据主权隔离不变量**：`dear_memory` 与 `dear_skills` 必须以 `(tenant_id, project_id, user_id)` 作为主键前缀，底座 SQL 查询必须严格带入三元组条件，严禁跨租户全表扫描。
4. **单调自增保序不变量**：`runtime_message_inbox` 表必须维持 `UNIQUE(thread_id, sequence)` 约束，单会话内绝对不允许出现重复或跳跃乱序的序号。
5. **仓储收敛不变量**：底层业务代码严禁在 `db/repositories/` 之外自行手写 `psycopg.connect()` 执行裸 SQL，所有数据库交互必须收敛在仓储层内。

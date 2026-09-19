# 子专题05：runtime-service 数据库结构设计问题

> 实施更新：后端已完成，当前状态以 [README](README.md)、实际契约以 [07](07-frontend-handoff.md)、验证以 [08第9节](08-backend-development-and-validation.md#9-2026-09-19-实际验证记录) 为准。本文保留当时讨论与决策过程；历史“规划中/暂未实施/暂未决定”不作为当前实施状态。

## 当前批准与实施进度

| 工作 | 状态 | 内容 |
|---|---|---|
| 数据库归属与迁移选型规划 | **最高** | 用户已同意 Runtime 自有 Alembic、`src/runtime_service/db/migrations/`、独立 `runtime_app_alembic_version`、`python -m runtime_service.db upgrade`；不再待选型 |
| 应用迁移、连接模块及资源打包 | **暂未实施** | 08 的 P1 负责，未编写代码 |
| 初始化、重复执行、并发迁移与失败验证 | **暂未实施** | 08 的 V08/V12 负责，无执行结果 |
| 旧技能数据转换、双写、旧模型回切 | **不做** | 用户已明确不考虑存量兼容 |
| 根级启动脚本自动接入 | **延后** | 当前实现仅两服务，先交付服务内命令/部署说明 |

“最高”按用户指定表示已完成。下方保留方案演进背景，较早的“工具和目录暂未决定”已由本次批准取代，不能据此重新请求批准。完整进度以 [README](README.md) 和 [08](08-backend-development-and-validation.md) 为准。

> **Q1/Q7 最新结论：** 技能持久化与应用迁移归 runtime-service，不为此扩展 GraphHarbor。官方 Agent Server 文档和本地 `graphharbor==0.13.0.post30` 迁移源码已核对，证据见 [08 第 3.4 节](08-backend-development-and-validation.md)。不做旧技能版本/绑定的数据兼容转换，原先 active 迁入、双写、旧模型回切方案不再要求。schema 版本管理与记忆/外部任务/inbox 保留边界仍需验证。具体建议是 Runtime 自有 Alembic、包内迁移资源和独立版本表，工具及路径细节尚未最终确认。

> **最新批准：** 用户已同意 E：保留 PostgreSQL，统一服务自有迁移/连接入口，业务存取归业务模块。具体工具、目录、迁移旧数据和根级部署脚本范围仍暂未决定；文件级任务与验证见 [08](08-backend-development-and-validation.md)。本轮不编码、不操作数据库，下文较早的“整体方向未批准”不再适用。

> 本文讨论 runtime-service 的数据库操作应如何组织，以及当前 migrations 目录的位置是否合理。

## 本轮建议与决策状态（2026-09-19）

**已决定：本次只讨论和维护文档，不迁移文件、不建表、不修改数据库或代码。** 用户提出重新审视数据库维护结构；具体方案、工具、目录、排期及是否单独立项均 **暂未决定**。早期“整改已决定、独立立项已决定”的表述不应当作实施批准。

### 真正需要解决的问题

SQL 放在业务包内并非天然错误，随 wheel 发布也完全合理。当前问题是**迁移责任、执行入口与版本记录没有覆盖所有服务自有表**，只搬目录不能解决。

- GraphHarbor 自有表：已有 `graphharbor migrate upgrade`，由 `scripts/local-stack.sh::migrate()` 及 Runtime Compose 的 migration 服务调用。其表结构由依赖包维护，不应把本项目业务表随意塞入上游迁移链。
- Runtime 自有表：Dear Agent 的两份 SQL 由两个 Python 模块入口执行；`runtime_message_inbox` 还有独立 `MessageInbox.initialize()`，不能只盘点四张 Dear 表。
- platform-api 自有表：由该服务自己的 Alembic 管理；不因已有 Alembic 就接管 Runtime 表。
- interaction-data-service：继续负责结果域；外部任务收据、技能与记忆不会因为需要数据库就自动属于结果域。

### 推荐的维护位置（提案，暂未决定）

```text
apps/runtime-service/
├── migrations/                         # 服务自有表的版本迁移（目录方案之一）
│   └── versions/
├── src/runtime_service/
│   ├── db/
│   │   └── connection.py               # 已存在的重复 DSN/连接逻辑统一维护
│   ├── services/dearflow_agent/
│   │   ├── memory.py                   # 记忆业务及其 SQL 存取
│   │   ├── skill_governance.py          # 技能规则及其 SQL 存取；名称随最终方案决定
│   │   └── external_task_storage.py    # 外部任务专属存取
│   └── messaging/inbox.py              # 消息队列专属存取
└── docs/standards/                     # 数据库归属、迁移与发布维护规范
```

职责划分建议：

| 维护内容 | 建议位置 | 原因 |
|---|---|---|
| 新表、字段、索引、历史结构升级 | Runtime 服务统一迁移目录 | 能追踪版本并纳入部署 |
| DSN 归一与通用连接获取 | `src/runtime_service/db/connection.py` | 当前 governance、external tasks、inbox 存在重复逻辑 |
| 业务查询、写入与事务范围 | 现有业务 storage 模块 | 避免所有业务 SQL 堆入一个通用 db 文件 |
| 迁移执行顺序与失败阻断 | 现有本地栈、容器 migration 入口 | 服务启动前完成迁移；请求和 Agent 执行不隐式建表 |

不为目录整齐提前引入 ORM、通用 Repository、抽象基类或连接池。若后续存取复杂到需要拆 repository，再按实际模块拆；采用 Alembic 也不要求业务查询全部改写为 SQLAlchemy。

### 迁移机制备选（暂未决定）

1. **GraphHarbor 能力边界已明确且完成本轮核对**：已检查 CLI/runner 固定使用自身迁移资源，未发现应用链注册入口；不为技能新增扩展，应用自行维护。
2. 推荐 Runtime 自有 Alembic revision 链；部署入口依次执行 GraphHarbor 和应用迁移，任一失败则阻止启动。同库时使用独立应用版本记录（拟 `runtime_app_alembic_version`），不污染 GraphHarbor 或 platform-api 版本表。
3. 仅集中现有 SQL 可作为初始化过渡，但如果没有已执行版本记录、并发保护及失败恢复，就不能称为完整迁移方案；不建议为替代成熟工具自造一套复杂迁移框架。

`apps/runtime-service/migrations/` 是易发现的源目录建议；若交付物是 wheel，放在 `src/runtime_service/db/migrations/` 并作为包资源发布同样合理。最终位置取决于部署产物如何包含、定位迁移资源，不是“SQL 不应该打进 Python 包”。

### 需要先定与后续验证

- **暂未决定：** 技能治理精简后保留哪些表/字段；先明确目标能力，再设计迁移，避免搬完又删。
- **暂未决定：** 老环境已建表的基线接管方案；不能未经结构核对直接 stamp，也不能靠 `CREATE TABLE IF NOT EXISTS` 认为旧结构已升级。
- **暂未决定：** 是否将消息收件箱一并纳入；建议纳入盘点，实施批次另定。
- **暂未决定：** 备份、旧数据兼容与回滚策略。撤掉技能治理不能连带清空记忆、外部任务或历史会话数据。
- 实施前需人工评审，因为涉及迁移、部署和可能的鉴权/数据语义变化。
- 后续至少验证空库初始化、已有库升级、重复执行、并发迁移保护、迁移失败阻断、包/镜像可定位资源及回滚兼容；本轮均未执行。

## 早期备选方案（历史背景，以上文为当前讨论依据）

---

## 现状：哪里愚蠢，愚蠢在哪儿？

当前的两个 SQL 文件放在了业务逻辑目录（`services/dearflow_agent/migrations/`）里：

```
apps/runtime-service/src/runtime_service/
├── services/
│   └── dearflow_agent/
│       ├── migrations/          ← ❌ 问题在这里
│       │   ├── 001_external_tasks.sql
│       │   └── 002_governance.sql
│       ├── governance_storage.py   ← __main__ 块里调用 002
│       └── external_task_storage.py ← __main__ 块里调用 001
```

**问题清单：**
1. **维护入口分散**：业务内聚放置迁移可以成立，但当前服务缺乏统一执行、版本记录与部署覆盖，需要解决碎片化问题。
2. **无版本管理**：没有任何框架跟踪"当前数据库是第几版"、"哪些 migration 已经跑过了"，新成员部署时不知道该跑哪个脚本、跑没跑过。
3. **执行方式原始**：靠 `if __name__ == "__main__"` 触发，没有统一的迁移命令，需要记忆具体的 Python 路径。
4. **无回滚机制**：`CREATE TABLE IF NOT EXISTS` 幂等但不能回滚结构变更，后续加字段/改索引全靠手写新 SQL 手动追加。

---

## 对比：platform-api 是怎么做的？

**platform-api 的结构（标准做法）：**

```
apps/platform-api/
├── alembic.ini                  ← Alembic 配置
├── migrations/                  ← 统一的 migration 目录（根级别）
│   ├── env.py                   ← Alembic 环境配置
│   ├── script.py.mako           ← migration 模板
│   └── versions/                ← 版本化的 migration 文件
│       ├── 001_xxxx.py
│       └── 002_xxxx.py
└── src/platform_api/
    └── core/
        └── db/
            ├── base.py          ← SQLAlchemy Base
            └── init_db.py       ← 模型导入（供 alembic 发现）
```

**platform-api 用的是 Alembic（SQLAlchemy 生态的标准迁移工具）**：
- `alembic upgrade head` → 跑所有未执行的 migration
- `alembic downgrade -1` → 回滚上一个 migration
- 每个版本文件都有 `revision`/`down_revision`，形成有向链
- 通过 `alembic_version` 表追踪当前数据库版本状态

---

## 建议的 runtime-service 数据库结构

### 方案一（推荐）：参照 platform-api，引入 Alembic

**改造后的目录结构：**

```
apps/runtime-service/
├── alembic.ini                       ← Alembic 配置（同 platform-api 风格）
├── migrations/                       ← 统一到 app 根级别
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── 001_dear_external_tasks.py    ← 001_external_tasks.sql 转换而来
│       └── 002_dear_governance.py        ← 002_governance.sql 转换而来
└── src/runtime_service/
    └── db/                          ← 新增数据库层（对标 platform-api/core/db/）
        ├── __init__.py
        ├── base.py                  ← SQLAlchemy Base 或 psycopg 连接管理
        └── connection.py            ← 统一的连接池/DSN 处理
```

**governance_storage.py / external_task_storage.py 里的连接逻辑**统一迁移到 `runtime_service.db` 模块，原文件只保留业务逻辑（不再负责连接管理和建表）。

**执行方式：**
```bash
# 跑所有未执行的 migration
uv run alembic upgrade head

# 新增 migration（表结构变更时用）
uv run alembic revision -m "add column xxx to dear_skill_versions"
```

### 方案二（最小改动）：不引入 Alembic，但把 SQL 挪到正确的位置

如果不想引入 Alembic 的复杂性（确实引入 Alembic 需要改 pyproject.toml、新建 db 层等），至少应该：

1. 把 `migrations/` 目录从 `services/dearflow_agent/` 挪到 `runtime-service/` 根级别
2. 新建一个统一的 `scripts/init_db.py` 或 Makefile target，执行所有 SQL
3. 在项目 README 里明确记录"部署前必须跑这个命令建表"

```
apps/runtime-service/
├── scripts/
│   └── init_db.py               ← 统一入口，顺序执行所有 SQL
├── migrations/                  ← 挪到根级别
│   ├── 001_dear_external_tasks.sql
│   └── 002_dear_governance.sql
└── src/runtime_service/
    └── db/                      ← 统一连接管理
        └── connection.py
```

### 老王的判断

platform-api 的 Alembic 是可借鉴的已有模式，不能据此宣布 Runtime 已决定采用。当前业务查询是 psycopg 原生 SQL，未建立 ORM metadata 时不能指望 autogenerate 自动生成准确结构。

**是否独立立项暂未决定。** 技能表的去留与本轮治理简化有关，应先确定数据目标；迁移实施须走治理评审。

---

## 决策记录

| 事项 | 状态 | 结论 |
|------|------|------|
| runtime-service 数据库维护结构 | **暂未决定** | 用户要求讨论设计；建议统一入口和版本记录，具体整改未批准 |
| 采用哪种方案 | ⏳ **暂未决定** | 方案一（引入 Alembic）vs 方案二（最小改动挪位置），需用户决策 |
| 本次是否实施 | **已决定** | 本次不实施；是否独立立项、依赖顺序暂未决定 |
| pyproject.toml 里 `migrations/*.sql` 的 package-data 条目 | **暂未决定** | 随最终资源位置和交付方式调整；包内携带 SQL 本身合理 |

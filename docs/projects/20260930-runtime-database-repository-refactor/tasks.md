# Runtime 数据库仓储模式重构与 Schema 契约治理专项 - 任务拆分

## Phase 1: 契约层与轻量仓储基建 (Infrastructure & Contracts)

### Task 1.1: 建立强类型契约层 `db/schema.py`
- **改动内容：** 使用不可变数据类定义 `InboxMessageRecord`、`DearMemoryRecord`、`DearSkillRecord`、`DearExternalTaskRecord`。
- **代码位置：** `apps/runtime-service/src/runtime_service/db/schema.py`
- **预期结果：** 具备明确的字段类型、默认值、不可变性 (`frozen=True, slots=True`)。
- **验证项：** 契约单元测试，验证类型映射与不可变性。
- **预计：** 0.5天
- **状态：** `[ ]` 待开始

### Task 1.2: 建立轻量仓储基础架构与 `InboxRepository`
- **改动内容：** 实现 `db/repositories/inbox_repo.py`，封装 `runtime_message_inbox` 的 `enqueue`, `claim`, `reconcile`, `reclaim` 原生 SQL。
- **代码位置：** `apps/runtime-service/src/runtime_service/db/repositories/inbox_repo.py`
- **预期结果：** 提供标准仓储方法，原生 SQL 参数化防注入，支持事务透传。
- **验证项：** 编写 `tests/db/test_inbox_repo.py`。
- **预计：** 0.5天
- **状态：** `[ ]` 待开始

### Task 1.3: 实现 `MemoryRepository`、`SkillsRepository` 与 `TasksRepository`
- **改动内容：**
  - `db/repositories/memory_repo.py`：负责 `dear_memory` 的租户级文档读写。
  - `db/repositories/skills_repo.py`：负责 `dear_skills` 的查询与更新。
  - `db/repositories/tasks_repo.py`：负责 `dear_external_tasks` 的状态流转与租约。
- **代码位置：** `apps/runtime-service/src/runtime_service/db/repositories/`
- **预期结果：** 全部完成原生 SQL 收敛。
- **验证项：** 对应单测 `tests/db/test_application_repos.py`。
- **预计：** 1天
- **状态：** `[ ]` 待开始

---

## Phase 2: 业务层渐进式平替 (Incremental Migration)

### Task 2.1: 平替 `messaging/inbox.py`
- **改动内容：** 将 `inbox.py` 中的原生 SQL 替换为调用 `InboxRepository`。
- **代码位置：** `apps/runtime-service/src/runtime_service/messaging/inbox.py`
- **预期结果：** 既有 `MessageInbox` 行为 100% 兼容，咨询锁与租约状态机正常工作。
- **验证项：** `pytest apps/runtime-service/tests/test_inbox.py` 全绿。
- **预计：** 0.5天
- **状态：** `[ ]` 待开始

### Task 2.2: 平替 `dearflow_agent` 相关存储文件
- **改动内容：**
  - `services/dearflow_agent/memory.py` -> 改用 `MemoryRepository`；
  - `services/dearflow_agent/skill_governance.py` -> 改用 `SkillsRepository`；
  - `services/dearflow_agent/external_task_storage.py` -> 改用 `TasksRepository`。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/`
- **预期结果：** 消除 3 个业务文件中的全部裸 SQL 字符串。
- **验证项：** `pytest apps/runtime-service/tests/services/dearflow_agent/` 全部通过。
- **预计：** 0.5天
- **状态：** `[ ]` 待开始

---

## Phase 3: 全面验证与架构归档 (Verification & Governance)

### Task 3.1: Final 全量回归与脱机自测验证
- **改动内容：** 运行 `runtime-service` 全量 534 项单测与脱机运行用例，确保零性能衰退、零功能倒退。
- **验证项：** 单元测试通过率 100%，无 ORM 性能开销，Ruff 0 诊断。
- **状态：** `[ ]` 待开始

---

## 进度追踪
- [ ] Phase 1 基础建设完成
- [ ] Phase 2 业务平替完成
- [ ] Phase 3 全量验证通过

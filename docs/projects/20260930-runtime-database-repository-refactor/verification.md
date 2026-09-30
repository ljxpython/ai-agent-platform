# Runtime 数据库仓储模式重构与 Schema 契约治理专项 - 验证计划和记录

## 验证计划

### 单元测试
- [ ] `test_schema_records_immutability()` - 验证 `db/schema.py` 各记录不可变性与插槽特性
- [ ] `test_inbox_repo_crud_and_locks()` - 验证 `InboxRepository` 的增删改查与咨询锁原子释放
- [ ] `test_memory_repo_tenant_isolation()` - 验证 `MemoryRepository` 严格遵循多租户主键隔离
- [ ] `test_skills_repo_optimistic_locking()` - 验证 `SkillsRepository` 动态技能乐观锁更新
- [ ] `test_tasks_repo_lease_fencing()` - 验证 `TasksRepository` 外部长任务状态流转与租约防脑裂

### 集成测试
- [ ] **场景 1：真实追加消息与对账全流程**
  - 步骤：调用平替后的 `inbox.py` 发起消息入队、Worker 认领与 Checkpoint 冲销
  - 预期：`runtime_message_inbox` 表状态机流转正常，严格单调保序
- [ ] **场景 2：DearFlowAgent 长期记忆闭环与技能加载**
  - 步骤：运行带记忆注入与自定义技能执行的 Agent 测试用例
  - 预期：底层通过 `MemoryRepository` 和 `SkillsRepository` 正常水合数据

### 性能与非功能测试
- [ ] **微秒级性能验证**：原生 `psycopg` 仓储方法开销在 1ms 以内，无 ORM 状态树追踪损耗。
- [ ] **全量回归基线**：`runtime-service` 现有 534 项单测全绿通过。

## 验证记录

### 2026-09-30 立项方案登记
**执行人：** @laowang
**状态：** 规划完成，待方案评审批准后实施。

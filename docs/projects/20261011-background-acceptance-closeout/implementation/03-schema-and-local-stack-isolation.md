# 迁移一致性与本地执行域

2026-10-11，实施目录 `~/.codex/worktrees/b01-closeout/ai-agent-platform`；对应 K02/K05/K06。前端源码和测试未修改。

## Platform 历史 SQLite 类型

`tests/integration/test_iam_migration.py` 的元数据核对发现三处历史完成回执 UUID 列以 PostgreSQL UUID 声明迁入 SQLite 后成为 NUMERIC，与当前通用 Uuid 模型不一致；另一个差异是模型遗漏已有唯一约束。

- 新增 `apps/platform-api/migrations/versions/20261011_0009_completion_sqlite_uuid.py`，父节点为 `20261011_0008`。PostgreSQL 无数据操作；SQLite 用 batch 迁移把 events.event_id、receipts.id/event_id 改为通用 UUID 存储，保留原记录和关联。
- 在改表前检查全部身份列：遇到已经被 SQLite 数值化的 UUID，拒绝继续，要求恢复原身份，不猜测或新造接受事实。downgrade 同样拒绝删除接受事实；旧 revision 不修改。
- `infra/sqlalchemy/models.py::RunCompletionOriginRecord` 补模型中的 `uq_run_completion_origins_run`，数据库已有此约束，没有新增权限或公开字段。
- 迁移测试覆盖 SQLite/PG 五起点、旧完成历史保留、损坏身份拒绝，以及完整模型零差异。

`phase-all-migrations-fixed.xml`：**13 passed，66.45 秒，0 skipped**。实际独立库已升级并查询确认 Platform `20261011_0009`；Runtime 应用 `0004_background_token_budget`、GraphHarbor `013_run_acceptance_receipts` 保持。早期 `0008` 证据是合并节点阶段，不能作为当前 head。

## 本地启动默认值与执行域

`scripts/local-stack.sh::start_managed_key()` 原来强制 `RUNTIME_BACKGROUND_TASKS_ENABLED=1`，API/Worker 共用字面量 `worktree-host`。这会绕过 A/B 开关，并破坏 Worktree 执行域隔离。

- 移除两处强制启用/共享 host，启动进程继承同一份已加载配置；缺省后台开关为 0，并在预检验证 0/1。
- `scripts/local_stack_worktree.py::initialize()` 不继承主环境开启状态，新环境固定默认 0；host 写入登记 ID，后台日志写入所属 `.local-stack/background-logs`。
- `export_environment()` 始终按登记派生 host 和日志目录，旧配置中的主环境路径/共享 host 不能覆盖；已有环境的显式后台开关仍保留。
- `check_install_directories()` 增加后台日志目录的归属检查，拒绝跨环境软链。
- 行为测试真实执行 API/Worker 启动命令的环境部分，验证缺省关闭、显式启用、非法配置拒绝；两环境初始化/重复初始化/继承配置/日志软链测试复用原测试。

存量 Worktree 若有旧 `worktree-host` 未结任务，须先用旧执行域按运行手册排空，再切换登记 host；不自动认领其他环境资源。新 b01-closeout 独立库没有旧域任务。此改动不更新其他 Worktree 私有配置，也不改变生产部署。

## 启停进程身份

`scripts/local_stack_processes.py::owned()` 原来会把路径引用 `.local-stack` 的 PostgreSQL 验收进程算入 Redis；真实 status 已复现，模拟安全自检再现会选中 PG。Redis 的初始扫描、端口、子进程和父进程选择均加 redis-server 身份约束；不只凭 cwd/状态路径决定。新增 `test_redis_management_excludes_disposable_postgres_in_state_directory`，与原两条真实进程/外目录保护一起 **3 passed（10.27s）**，`phase-process-identity.xml`。未停止其他环境进程。

## 验收夹具一致性

macOS Platform 的 uvloop 在实际完成验收中两次发生 native abort。`tests/fixtures/{run_reliability,tool_error_platform}.py` 仅把 Platform 夹具改为标准 asyncio，Runtime/Provider 与 Linux 镜像执行方式不变。修复轮两组合根真实模型验收 `phase-managed-asyncio.xml`：**1 passed，641.81 秒**；原 abort 失败报告保留，不能计为通过。

Platform `tests/test_run_completion.py` 的真实 PG 并发夹具改用显式 `ACCEPTANCE_TEST_PLATFORM_DATABASE_URL`，在所属库临时 schema 验证并回收，取消旧固定公共验证库地址。`phase-completion-concurrent-pg.xml`：**1 passed，31.80 秒**；6 个 callback 与 2 个回填并发，唯一 event 和原 run_id 保持。

本地脚本增量结果、剩余系统矩阵与最终交付以 tasks/verification 为准。本文件记录原因和补丁，不独立决定完成度。

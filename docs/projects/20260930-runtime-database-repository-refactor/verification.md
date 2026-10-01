# Runtime 数据库访问边界收敛与类型补全 - 验证

## 验收条件

- 现有 MemoryStorage / SkillStorage 的 import、方法参数、返回值和错误语义保持兼容。
- SQL 函数复用外层连接；同一业务操作的加锁、读取、校验和写入在同一事务内。
- tenant/project/user 隔离、Skills slug 条件、revision/epoch 和取消回滚不退化。
- 不修改 DDL、迁移、Inbox/Tasks 实现，不新增通用仓储框架。
- 定向用例与 Runtime 回归无新增失败；必验 PostgreSQL 场景实际执行，不能用 skip 代替通过。

## 验证计划

测试路径均相对于 `apps/runtime-service/`：

| 范围 | 现有测试 | 重点 |
|---|---|---|
| Memory 业务契约 | `tests/services/dearflow_agent/test_memory_contract.py` | 调用契约、上下文投影和中间件行为 |
| Memory/Skills PostgreSQL | `tests/services/dearflow_agent/test_p6_governance.py` | scope 隔离、并发 revision 冲突、epoch 失效、旧文档兼容、容量竞争、取消回滚 |
| Skills 恢复 | `tests/services/dearflow_agent/test_skill_restart.py` | 执行快照与重启恢复 |
| Inbox 回归 | `tests/services/test_message_inbox_postgres.py` | 共享连接基础设施和消息行为无意外变化 |
| 外部任务回归 | `tests/services/dearflow_agent/test_p5_media.py` | 幂等、租约与 fencing 无意外变化 |
| 实际环境补充验证 | `tests/e2e/test_dear_memory_real.py` | 按该测试依赖条件执行并单独记录，不用离线结果冒充真实链路 |

1. 实施前记录基线；实施中按 Memory、Skills 分别跑定向测试；最终跑 Runtime 全量回归。
2. PostgreSQL 测试使用隔离测试数据库/模式，按现有用例要求显式配置 `RUNTIME_MESSAGE_TEST_DSN`，不得指向生产数据。未配置或环境不可达时，记录未验证场景。
3. 复用现有测试，仅为缺失的事务/映射行为补最小用例；Mock SQL 调用不能证明 PostgreSQL 锁和事务正确。
4. 执行服务现有 Ruff check、format check 和类型检查（如已配置）。纯类型别名不以不可变性单测验收。
5. 核对 SQL 数量、连接次数、锁范围没有因抽取而增加或改变。没有性能基线与测量结果时，不作延迟或吞吐承诺。

## 文档修订记录

2026-10-01：根据源码核对与用户讨论更新本项目四份文档，收缩为必要类型补全和 Memory/Skills SQL 抽取。用户授权本轮修订文档，后续重新评估是否实施。代码与数据库测试尚未执行，不记录通过结论。

## Phase 验证记录

### 2026-10-01

工作目录：`apps/runtime-service`；Python 3.13，项目 uv 环境。

- 初次未配置 PostgreSQL DSN：Memory 契约 15 passed；治理/重启 4 passed、24 skipped。该结果不作为数据库验收。
- 显式配置本机测试库后，各测试使用随机隔离 schema：`env RUNTIME_MESSAGE_TEST_DSN=postgresql://lijiaxin@127.0.0.1:5432/graphharbor_web_refactor_20260910 uv run pytest -q tests/services/dearflow_agent/test_memory_contract.py tests/services/dearflow_agent/test_p6_governance.py tests/services/dearflow_agent/test_skill_restart.py` → **43 passed**，140.15 秒，无跳过。
- `uvx ruff check src tests` → All checks passed；`uvx ruff format --check src tests` → 235 files already formatted。直接调用 Ruff 不可用，使用 uvx 解决，无项目依赖变更。
- Python compileall 与 `git diff --check` 通过。仓库未配置独立类型检查器。

## Final 验证记录

2026-10-01：**本期内部重构验收完成（done），全仓测试不全绿。**

- 同一测试 DSN 下 `uv run pytest -q` → **564 passed、61 skipped、2 failed**，280.66 秒。
- 失败一：`tests/services/showcase_demo/test_agent.py::test_graph_approval_runs_real_python_and_preserves_exit_code`，Docker daemon 未运行，execute 返回 125。
- 失败二：`tests/test_terminal.py::test_dearflow_local_terminal_uses_shared_backend`，读取 `work/result.txt` 时 FileNotFoundError；单独重跑仍失败。
- 对照验证：在独立 Python 进程内用 `git show HEAD:<path>` 的原始 Memory/Skills 源码覆盖已导入模块，再运行这两个用例，仍然 2 failed。未修改工作区源码。证据支持这两个失败不由本次 SQL 抽取引入，作为范围外问题保留，不能宣称全仓回归通过。
- 61 项跳过不计为通过，包含需显式开启的真实服务/模型及环境相关用例；真实模型端到端测试本轮未开启。本期必验 Memory/Skills PostgreSQL 场景已通过独立 43 项定向测试全部执行。
- 最终人工差异检查：连接和锁仍在原业务类，SQL helpers 只执行已有查询；无迁移、Inbox/Tasks 实现或对外契约变化。无性能基线，不作性能承诺。

本期不扩展到 Docker/终端问题修复；如要求全仓所有环境用例全绿，需要另行准备 Docker/真实服务并处理上述终端问题。

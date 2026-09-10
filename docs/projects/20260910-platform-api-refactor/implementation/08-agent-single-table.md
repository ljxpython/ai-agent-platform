# Agent 单表与空库基线切片

日期：2026-09-10。总体状态：partial。

## 实现

- AgentRecord 直接保存 status/config/context/metadata 和创建者、更新者及更新时间；移除 AgentProfileRecord、关系和导出。
- 仓储原先 outer join 两表，现为 select(AgentRecord)；配置更新直接更新 Agent 行。创建在一次 INSERT 中写入完整配置和非空审计身份。
- 应用服务使用 update_assistant_configuration；删除未消费的 AssistantsRepositoryProtocol。
- 旧七段 Alembic 修订链替换为静态空库基线 20260910_0001。旧数据不迁移，不对既有开发数据库执行变更。
- runtime-service 实际仍锁定 post23，本切片补齐 post24 pyproject、锁文件和安装。

## 验证

- 新增 test_agent_single_table.py：真实临时 SQLite + Service/Repository，覆盖配置生命周期、项目隔离、重复 Graph 拒绝及未授权读取。
- test_iam_migration.py 改测空库升级、重复升级、与 ORM 的 schema 比较、降级与重新升级。
- 单表生命周期初版及空库迁移往返均通过；最终回归结果待追加。

## 尚未完成

本切片不代表 C4/C5 或全部数据库重构完成。Agent 仍有旧同步字段、URL 字段与配置结构；模型引用、执行启用策略、resync/Operations、旧路由、前端和网关还待调整。新基线当前保留 Operations/runtime_runs/runtime_run_interrupts，必须随后续退役同步收缩。真实 PostgreSQL/Runtime 联调与 Showcase 恢复仍未验收。

## 数据库与安装实测证据

- 独立 PostgreSQL 数据库 platform_refactor_c4e3952b08：upgrade head、重复 upgrade、compare_metadata 无差异、downgrade base、再次 upgrade 全部通过。该隔离库保留用于后续验证。
- SQLite 同样通过迁移往返与 ORM 一致性测试。
- runtime-service 的 uv sync --frozen 成功；通过 importlib.metadata 确认 graphharbor 和 graphharbor-runtime 均为 0.13.0.post24，安装后的 langhost.server 不含 _builtin_auth。
- Agent 生命周期最终针对性测试通过，含重复 Graph 拒绝和越权读取拒绝。
- 以上不等于真实 Graph/模型调用端到端验收。

## 最终回归

在 apps/platform-api 执行：

```bash
PLATFORM_RUNTIME_INTEGRATION=0 .venv/bin/python -m unittest discover -s tests -p 'test*.py' -q
```

结果：159 项，156 通过、3 跳过、0 失败，282.792 秒。迁移测试从旧版两个兼容测试替换为一个空库往返测试，因此总数比首轮少 1。跳过的是外部 HTTP 集成，不计通过。

修改范围的 Ruff、compileall 和 git diff --check 通过。测试仍报告原有短测试 JWT key 警告；不代表生产凭据检查结果。

判定：本切片已验证，整体工程 partial。尚未执行完整 Runtime 真实模型链路，Operations、网关与最终 schema 收缩未完成。

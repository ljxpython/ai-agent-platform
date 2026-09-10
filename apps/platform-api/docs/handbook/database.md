# 数据库

Platform使用同步SQLAlchemy，与Runtime执行数据库分离。[20260910_0001](../../migrations/versions/20260910_0001_platform_baseline.py)为空库基线，包括20张业务表，Alembic另维护 `alembic_version`。

| 分组 | 表 | 职责 |
| --- | --- | --- |
| 身份 | tenants、users、refresh_tokens | 租户、用户与可撤销会话 |
| 项目 | projects、project_members | 项目与成员角色 |
| 服务账号 | service_accounts、service_account_tokens、service_account_project_grants | 机器身份、令牌摘要与项目授权 |
| Agent | agents | 项目graph配置、启停、context默认值 |
| 目录 | runtime_catalog_graphs、runtime_catalog_tools、runtime_catalog_models | 能力快照与模型连接 |
| 策略 | project_graph_policies、project_tool_policies、project_model_policies | 项目执行限制 |
| 请求 | run_requests | 幂等摘要、授权/config快照、Run与父Run关联 |
| 公告 | announcements、announcement_reads | 公告与已读 |
| 治理 | audit_logs、platform_config_entries | 审计与配置 |

run_requests不保存消息、执行终态或明文密钥。执行事实属于GraphHarbor/Runtime。模型api_key由master key加密；refresh token与服务账号token保存摘要。

## 初始化

在 `apps/platform-api` 执行。先创建专用空PostgreSQL数据库，在环境或 `.env` 设置：

```dotenv
PLATFORM_API_PLATFORM_DB_ENABLED=true
PLATFORM_API_PLATFORM_DB_AUTO_CREATE=false
PLATFORM_API_DATABASE_URL=postgresql+psycopg://user:password@127.0.0.1:5432/platform
```

示例凭据自行替换，勿提交真实值。

```bash
uv run --frozen alembic upgrade head
uv run --frozen alembic current
```

不支持旧平台库直接升级，不能用stamp冒充迁移。启动时bootstrap按配置创建管理员，不将密码写入迁移文件。

本地SQLite可以使用示例自动建表或 `uv run --frozen python scripts/init_db.py`；这不是Alembic迁移或PG验收。确认目标库后执行，禁止用初始化工具修补真实数据。

## 表变更与事务

后续修改模型应增加Alembic修订，不重写已使用基线；审查约束、索引和删除操作，在隔离库验证升级、必要的回退及metadata一致性。不迁移旧平台不意味着未来可以丢弃新平台数据。

`session_scope(session_factory)` 使用原生 `sessionmaker.begin()`，成功提交、异常回滚并关闭。Session生命周期同线程，HTTP等待前结束事务，见[开发规范](development-playbook.md)。

备份需包含平台库、Runtime库和配套密钥；工具工作区、Redis队列不是PG dump内容。两个独立dump不是跨库原子快照，需停止写入与Worker，恢复到新库核验后切换，见[运维](runbook.md)。

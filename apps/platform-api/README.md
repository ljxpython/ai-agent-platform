# Platform API

Runtime的治理与受控网关：管理身份、项目、Agent、模型连接、策略和审计。GraphHarbor持有Thread/Run/Checkpoint执行事实，Runtime定义图和工具。

## 本地启动

要求Python 3.13和uv，以下在 `apps/platform-api` 执行：

```bash
uv sync --frozen
cp ".env.example" ".env"
```

仅在 `.env` 不存在时复制，已有环境保留自己的凭据。示例使用SQLite自动建表；实际联调与验收使用独立PostgreSQL。先按[配置说明](docs/handbook/configuration.md)设置登录密钥、管理员密码、Runtime地址与委托；模型配置需要有效Fernet master key。

```bash
uv run --frozen uvicorn platform_api.main:create_app --factory --host 127.0.0.1 --port 2142 --reload
```

本机API文档为 `http://127.0.0.1:2142/docs`。`/_system/probes/ready` 必须检查响应status是否为ready，不能只看HTTP 200。Platform数据库就绪不代表Runtime可用。

正式新库使用Alembic并关闭自动建表，见[数据库](docs/handbook/database.md)。当前基线不兼容旧库，不对旧库直接执行升级。

## 验证

仍在 `apps/platform-api` 执行：

```bash
uv run --frozen python -m compileall -q src tests
PLATFORM_RUNTIME_INTEGRATION=0 uv run --frozen python -m unittest discover -s tests -p 'test*.py' -q
```

外部集成未配置时skip不计通过。真实联调和恢复见[运维](docs/handbook/runbook.md)。

## 开发入口

- [文档导航](docs/README.md)：使用、架构、开发、配置与关键标准。
- [根AGENTS](../../AGENTS.md)：协作和变更分级。
- [后端验收](../../docs/projects/20260910-platform-api-refactor/implementation/13-backend-acceptance-closeout.md)：本阶段已完成，保留证据与限制。
- [前端交接](../../docs/projects/20260910-platform-api-refactor/05-frontend-handoff.md)：不把后端验收当作浏览器验收。

无平台Operations、Worker、队列或运行状态镜像。整套容器部署与完整LangGraph Server等价性继续后置。

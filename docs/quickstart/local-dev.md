# 本地开发与联调

2026-09-20 核对。新机安装、账号、配置和远程访问见[非 Docker 部署手册](deployment-guide.md)。

默认：platform-web:3000 → platform-api:2142 → runtime-api:8123 → runtime-worker。
PostgreSQL、Redis 必需；结果域 8081 按需单独启动，LightRAG 不在当前默认范围。
没有 Platform Worker，不沿用 SQLite 或 langgraph dev 的旧启动说明。

## 首次配置完成后

在仓库根目录：

```bash
source "apps/runtime-service/.venv/bin/activate"
bash "scripts/local-stack.sh" doctor
bash "scripts/local-stack.sh" start
bash "scripts/local-stack.sh" status
bash "scripts/local-stack.sh" stop
```

脚本加载 Runtime app-local .env，读取平台委托密钥，检查依赖、执行迁移并管理四个进程。
不安装 PG/Redis，不生成配置、不安装前端依赖。doctor 可能清理本仓库旧占用进程，不是纯只读。

- Runtime：apps/runtime-service/.env，API/Worker 共用。
- 平台：apps/platform-api/.env，PG 独立库，关闭自动建表。
- 前端：apps/platform-web/.env.local，脚本强制同源 API / 和本地代理。
- 根目录 .env 不是统一配置源，不整体 source。

migrate 包括平台 Alembic、GraphHarbor 和 Runtime 应用表，start 也先执行它们。
优先使用脚本；隔离排障才用单服务命令，并保持相同配置和环境。

## 验收

```bash
curl -fsS "http://127.0.0.1:8123/ready"
curl -fsS "http://127.0.0.1:2142/_system/health"
```

本机访问 http://localhost:3000；远程用 SSH 转发到本机 13000，见完整手册。
健康检查不替代登录、建项目、配模型和真实 Run。
模型连接在平台数据库；旧 Runtime settings.yaml/settings.local.yaml 不参与正式模型解析。

各应用独立 .venv/锁文件，不搬跨系统依赖目录。
另见[配置矩阵](env-matrix.md)、[数据库规范](../guides/database-operations.md)。

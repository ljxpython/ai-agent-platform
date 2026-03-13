# PostgreSQL 运行与操作

## 1. 目标

记录当前 `platform-api` 使用 PostgreSQL 时的实际运维口径：

- 启动容器
- 连接检查
- 备份与恢复
- 当前 schema 初始化方式

## 2. 一次性启动本地 PostgreSQL

```bash
export PG_CONTAINER=agent-postgres
export PG_PASSWORD='<set-a-strong-password>'

docker run -d \
  --name "$PG_CONTAINER" \
  -e POSTGRES_USER=agent \
  -e POSTGRES_PASSWORD="$PG_PASSWORD" \
  -e POSTGRES_DB=agent_platform \
  -p 5432:5432 \
  -v agent_platform_pgdata:/var/lib/postgresql/data \
  -v "$(pwd)/backups":/backups \
  postgres:16
```

## 3. 启停与检查

```bash
docker start "$PG_CONTAINER"
docker stop "$PG_CONTAINER"
docker restart "$PG_CONTAINER"
docker logs -f "$PG_CONTAINER"
docker exec -it "$PG_CONTAINER" psql -U agent -d agent_platform -c "SELECT version();"
```

## 4. 当前 schema 初始化口径

当前代码基线以 `app/bootstrap/lifespan.py` 为准：

- 当 `PLATFORM_DB_ENABLED=true`
- 且 `PLATFORM_DB_AUTO_CREATE=true`
- 启动时会调用 `create_core_tables()` 创建核心表

这意味着：

- 本地开发的当前真实基线是 `create_core_tables()`
- Alembic 不是当前日常启动必经路径

## 5. Alembic 当前状态

仓库已经安装 Alembic 相关依赖，但当前文档口径是：

- 本地日常运行：优先按 `create_core_tables()` 理解
- 如果后续团队正式切换到 Alembic 作为唯一 schema 入口，再单独更新本文件与 `docs/local-dev.md`

## 6. 备份

```bash
docker exec "$PG_CONTAINER" \
  pg_dump -U agent -d agent_platform -F c -f /backups/agent_platform_$(date +%F_%H%M%S).dump
```

## 7. 恢复

```bash
docker exec "$PG_CONTAINER" psql -U agent -d agent_platform -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
docker exec "$PG_CONTAINER" pg_restore -U agent -d agent_platform /backups/<your_dump_file>.dump
```

## 8. 本地 / 隧道 两种连接方式

- 本地 PostgreSQL：`127.0.0.1:5432`
- SSH 隧道 PostgreSQL：`127.0.0.1:15432`

两者区别只体现在 `DATABASE_URL`。

## 9. 历史 SQLite 导入

如果仍有历史 SQLite 数据，可按需执行：

```bash
PYTHONPATH=. uv run python scripts/migrate_sqlite_to_postgres.py --dry-run
PYTHONPATH=. uv run python scripts/migrate_sqlite_to_postgres.py
```

执行前先做 PostgreSQL 逻辑备份。

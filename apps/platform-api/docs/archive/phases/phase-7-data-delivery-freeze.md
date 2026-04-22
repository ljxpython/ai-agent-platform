# Platform API V2 Phase C: Data & Delivery Freeze

这份文档对应 `phase-5` 里定义的：

> `Phase C: Data & Delivery Freeze`

这一阶段不再碰控制面业务边界，目标是把数据库、异步、交付、环境治理的正式口径冻结下来。

---

## 1. 目标

Phase C 要完成五件事：

- 冻结 SQLite 开发基线
- 冻结 PostgreSQL 切主路径
- 冻结 Redis queue / worker 交付口径
- 冻结 backup / restore / release / rollback 模板
- 冻结 local / dev / staging / prod 环境分层

---

## 2. 当前正式口径

### 2.1 数据库

- `local` 默认继续使用 SQLite
- `dev / staging / prod` 默认使用 PostgreSQL
- PostgreSQL 场景下禁止继续依赖 `create_all`
- PostgreSQL schema 变更统一走 Alembic

### 2.2 异步与队列

- 默认开发队列后端：`db_polling`
- 推荐团队协作 / 预发 / 生产后端：`redis_list`
- worker 启动入口固定为 `python worker.py`
- queue backend 切换只允许改配置，不允许改模块代码

### 2.3 交付与环境

- 本地恢复与演示口径：`SQLite + db_polling`
- 预发 / 生产口径：`PostgreSQL + redis_list`
- 环境样板固定在：
  - `deploy/env/local.example.env`
  - `deploy/env/dev.example.env`
  - `deploy/env/staging.example.env`
  - `deploy/env/prod.example.env`

---

## 3. 本轮已完成

### P0 数据基线

- [x] `SQLite` 继续保留为默认开发库
- [x] `delivery/postgres-baseline.md` 明确了 PostgreSQL 切主路径
- [x] `docker-compose.example.yml` 增加了 PostgreSQL profile 示例

### P1 队列与 worker

- [x] `redis_list` 继续作为可选正式后端
- [x] compose 示例固定 `api + worker + redis`
- [x] 切 PostgreSQL / Redis 不要求改业务模块代码

### P2 备份恢复与发布模板

- [x] `backup_db.sh` 支持 `sqlite / postgres`
- [x] `restore_db.sh` 支持 `sqlite / postgres`
- [x] `delivery/release-template.md`、`delivery/runbook.md` 保持为正式模板入口

### P3 环境分层冻结

- [x] 新增 `local / dev / staging / prod` 环境样板
- [x] `prod` 强制 `docs=false`、`bootstrap_admin=false`
- [x] JWT secret 必须在非本地环境显式替换

---

## 4. 本轮验证

- [x] `bash -n scripts/backup_db.sh scripts/restore_db.sh`
- [x] `python3 -m compileall app`
- [x] `.venv/bin/python -m unittest discover -s tests`

当前验证结果：

- `backup / restore` 脚本语法校验通过
- API 代码可重新编译通过
- `34` 个单测通过
- 交付物入口已经固定到：
  - `deploy/env/*.example.env`
  - `deploy/docker-compose.example.yml`
  - `docs/delivery/runbook.md`
  - `docs/delivery/release-template.md`
  - `scripts/backup_db.sh`
  - `scripts/restore_db.sh`

---

## 5. 启动与操作口径

### 5.1 本地最小开发

```bash
cd apps/platform-api-v2
cp deploy/env/local.example.env .env
uv run uvicorn main:app --host 127.0.0.1 --port 2142
uv run python worker.py
```

### 5.2 PostgreSQL + Redis 验收

```bash
cd apps/platform-api-v2/deploy
docker compose --profile postgres up -d
```

然后把环境切到：

- `deploy/env/dev.example.env`
- 或 `deploy/env/staging.example.env`

### 5.3 备份恢复

SQLite：

```bash
bash "./scripts/backup_db.sh" sqlite ".data/platform-api-v2.db" ".backup/platform-api-v2.db"
bash "./scripts/restore_db.sh" sqlite ".backup/platform-api-v2.db" ".data/platform-api-v2.db"
```

PostgreSQL：

```bash
bash "./scripts/backup_db.sh" postgres "postgresql://platform:platform@127.0.0.1:5432/platform_api_v2" ".backup/platform-api-v2.dump"
bash "./scripts/restore_db.sh" postgres ".backup/platform-api-v2.dump" "postgresql://platform:platform@127.0.0.1:5432/platform_api_v2"
```

---

## 6. 验收标准

- 本地开发者不需要 PostgreSQL，也能启动 API + worker
- 切到 PostgreSQL / Redis 时，不需要改 `app/modules` 代码
- backup / restore 脚本能覆盖 SQLite 与 PostgreSQL 两条线
- 发布、回滚、值班排障文档都有固定入口
- 环境变量分层后，不再靠口口相传猜配置

---

## 7. Phase C 结论

`Phase C: Data & Delivery Freeze` 到这里视为完成。

从现在开始，数据与交付层必须遵守：

- `local` 默认 `SQLite + db_polling`
- `dev / staging / prod` 默认 `PostgreSQL + redis_list`
- 数据库备份恢复统一走脚本，不再临时手搓命令
- 发布、回滚、值班排障优先参考固定模板与 runbook
- 环境变量新增项必须补到对应的 `deploy/env/*.example.env`

---

## 8. 下一步

Phase C 冻结后，下一阶段进入：

- `Phase D: Final Standard Freeze`

重点是把 README、Harness、团队开发 checklist、前后端样板和 AI 协作流程完全收成正式标准。

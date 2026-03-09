# 启动与本地验证指南（当前可执行版本）

本文只记录当前 `agent-platform` 新结构下，已经在本机验证过的启动方式。

## 1. 当前目录结构

```text
agent-platform/
├── apps/platform-api
├── apps/platform-web
├── apps/runtime-service
└── apps/runtime-web
```

## 2. 当前已确认的本地依赖前提

### 2.1 本机 PostgreSQL

当前验证使用的是本机 PostgreSQL，连接信息已经写入：

- `apps/platform-api/.env`

当前有效库连接为：

```text
postgresql+psycopg://agent:AgentPg_2026!migrate@127.0.0.1:5432/agent_platform
```

### 2.2 runtime-service 上游地址

当前平台配置已指向：

```text
http://127.0.0.1:8123
```

即：

- `apps/runtime-service` 跑在 `8123`
- `apps/platform-api` 通过 `LANGGRAPH_UPSTREAM_URL=http://127.0.0.1:8123` 调它

## 3. 推荐启动顺序

推荐顺序：

1. `runtime-service`
2. `platform-api`
3. `platform-web`
4. `runtime-web`（按需）

## 4. 逐个启动命令

### 4.1 启动 runtime-service

```bash
cd apps/runtime-service
uv run langgraph dev --config graph_src_v2/langgraph.json --port 8123 --no-browser
```

启动后自检：

```bash
curl http://127.0.0.1:8123/info
curl http://127.0.0.1:8123/internal/capabilities/models
curl http://127.0.0.1:8123/internal/capabilities/tools
```

### 4.2 启动 platform-api

```bash
cd apps/platform-api
uv run uvicorn main:app --host 0.0.0.0 --port 2024 --reload
```

启动后自检：

```bash
curl http://127.0.0.1:2024/api/langgraph/info
```

## 5. 平台联调 runtime 的关键验证

确认 `runtime-service` 和 `platform-api` 都启动后，可以验证：

```bash
curl http://127.0.0.1:2024/api/langgraph/info
```

预期：返回 `200`

## 6. platform-web 启动

```bash
cd apps/platform-web
pnpm dev
```

默认访问：

```text
http://127.0.0.1:3000
```

当前 `.env` 已配置：

```text
NEXT_PUBLIC_API_URL=http://localhost:2024
```

## 7. runtime-web 启动

```bash
cd apps/runtime-web
PORT=3001 pnpm dev
```

默认访问：

```text
http://127.0.0.1:3001
```

当前 `.env` 已配置：

```text
NEXT_PUBLIC_API_URL=http://localhost:8124
NEXT_PUBLIC_ASSISTANT_ID=assistant_entrypoint
```

注意：

- 如果你当前 runtime 实际跑在 `8123`，那这里的 `.env` 需要改成 `8123`
- 否则 `runtime-web` 会连错端口

如果你想直接用当前已验证的端口，请改成：

```text
NEXT_PUBLIC_API_URL=http://localhost:8123
```

## 8. 当前已经验证通过的接口

以下接口已经在新目录结构下验证通过：

```bash
curl http://127.0.0.1:8123/info
curl http://127.0.0.1:8123/internal/capabilities/models
curl http://127.0.0.1:8123/internal/capabilities/tools
curl http://127.0.0.1:2024/api/langgraph/info
```

以及平台到 runtime 的管理链路：

- `POST /_management/catalog/models/refresh`
- `GET /_management/runtime/models`
- `POST /_management/catalog/tools/refresh`
- `GET /_management/runtime/tools`

## 9. 一键脚本（可选）

根目录已提供脚本：

```bash
scripts/dev-up.sh
scripts/dev-down.sh
scripts/check-health.sh
```

但当前最推荐你先按本文手工逐步启动，这样排查最直观。

## 10. 停止方式

如果你是手工在前台启动：

- 直接 `Ctrl + C`

如果你是通过根脚本启动：

```bash
scripts/dev-down.sh
```

## 11. 平台数据库怎么理解

当前 `apps/platform-api` 使用的是本机 PostgreSQL：

```text
host=127.0.0.1
port=5432
database=agent_platform
username=agent
password=AgentPg_2026!migrate
```

### 11.1 当前数据库里几类数据的语义

- `users`
  - 平台用户表
  - 第一次启动后，通常至少会有 1 个 bootstrap admin
- `projects`
  - 平台项目表
  - 当前本地库应至少有 1 个项目
- `agents`
  - 平台 assistant 主数据表
  - 如果你还没创建 assistant，这里为空是正常的
- `assistant_profiles`
  - assistant 的平台配置/治理信息
  - 如果没有 assistant，这里为空也是正常的
- `audit_logs`
  - 平台审计日志
  - 只要你调过管理接口，这里就会不断增长
- `runtime_catalog_models`
  - runtime models 的平台快照
- `runtime_catalog_tools`
  - runtime tools 的平台快照
- `runtime_catalog_graphs`
  - runtime graphs 的平台快照

### 11.2 当前本地库看到什么结果算正常

当前阶段如果你已经完成启动验证，比较正常的现象是：

- `users`：>= 1
- `projects`：>= 1
- `agents`：可能为 0
- `assistant_profiles`：可能为 0
- `audit_logs`：> 0
- `runtime_catalog_models`：> 0
- `runtime_catalog_tools`：> 0
- `runtime_catalog_graphs`：> 0

换句话说：

- assistant 相关表为空，通常表示“你还没在这个新本地平台库里创建 assistant”
- catalog 表非空，表示 runtime 同步已经成功

## 12. DBeaver 连接方式

在 DBeaver 中新建 PostgreSQL 连接，填：

```text
Host: 127.0.0.1
Port: 5432
Database: agent_platform
Username: agent
Password: AgentPg_2026!migrate
```

JDBC URL 也可以直接写：

```text
jdbc:postgresql://127.0.0.1:5432/agent_platform
```

## 13. 常用 SQL 检查清单

### 13.1 当前连接确认

```sql
select current_database(), current_user, version();
```

### 13.2 看所有业务表

```sql
select table_name
from information_schema.tables
where table_schema = 'public'
order by table_name;
```

### 13.3 看平台核心数据量

```sql
select 'users' as table_name, count(*) from users
union all
select 'projects', count(*) from projects
union all
select 'agents', count(*) from agents
union all
select 'assistant_profiles', count(*) from assistant_profiles
union all
select 'audit_logs', count(*) from audit_logs
order by table_name;
```

### 13.4 看新的 runtime catalog 表数据量

```sql
select 'runtime_catalog_models' as table_name, count(*) from runtime_catalog_models
union all
select 'runtime_catalog_tools', count(*) from runtime_catalog_tools
union all
select 'runtime_catalog_graphs', count(*) from runtime_catalog_graphs
union all
select 'project_model_policies', count(*) from project_model_policies
union all
select 'project_tool_policies', count(*) from project_tool_policies
union all
select 'project_graph_policies', count(*) from project_graph_policies
order by table_name;
```

### 13.5 看 assistant 主数据

```sql
select
  a.id,
  a.project_id,
  a.name,
  a.graph_id,
  a.langgraph_assistant_id,
  a.sync_status,
  a.last_synced_at
from agents a
order by a.created_at desc
limit 50;
```

### 13.6 看 assistant profile

```sql
select
  ap.agent_id,
  ap.status,
  ap.updated_at
from assistant_profiles ap
order by ap.updated_at desc
limit 50;
```

### 13.7 看项目列表

```sql
select
  id,
  name,
  code,
  status,
  created_at
from projects
order by created_at desc;
```

### 13.8 看 runtime models

```sql
select
  id,
  runtime_id,
  model_key,
  display_name,
  is_default_runtime,
  sync_status,
  last_synced_at,
  is_deleted
from runtime_catalog_models
order by is_default_runtime desc, model_key;
```

### 13.9 看 runtime tools

```sql
select
  id,
  runtime_id,
  tool_key,
  name,
  source,
  sync_status,
  last_synced_at,
  is_deleted
from runtime_catalog_tools
order by source, name;
```

### 13.10 看 runtime graphs

```sql
select
  id,
  runtime_id,
  graph_key,
  display_name,
  source_type,
  sync_status,
  last_synced_at,
  is_deleted
from runtime_catalog_graphs
order by graph_key;
```

### 13.11 看 models policy

```sql
select
  pmp.project_id,
  p.name as project_name,
  pmp.model_catalog_id,
  rcm.model_key,
  pmp.is_enabled,
  pmp.is_default_for_project,
  pmp.temperature_default,
  pmp.updated_at
from project_model_policies pmp
join projects p on p.id = pmp.project_id
join runtime_catalog_models rcm on rcm.id = pmp.model_catalog_id
order by p.name, rcm.model_key;
```

### 13.12 看 tools policy

```sql
select
  ptp.project_id,
  p.name as project_name,
  ptp.tool_catalog_id,
  rct.tool_key,
  ptp.is_enabled,
  ptp.display_order,
  ptp.updated_at
from project_tool_policies ptp
join projects p on p.id = ptp.project_id
join runtime_catalog_tools rct on rct.id = ptp.tool_catalog_id
order by p.name, rct.tool_key;
```

### 13.13 看 graphs policy

```sql
select
  pgp.project_id,
  p.name as project_name,
  pgp.graph_catalog_id,
  rcg.graph_key,
  pgp.is_enabled,
  pgp.display_order,
  pgp.updated_at
from project_graph_policies pgp
join projects p on p.id = pgp.project_id
join runtime_catalog_graphs rcg on rcg.id = pgp.graph_catalog_id
order by p.name, rcg.graph_key;
```

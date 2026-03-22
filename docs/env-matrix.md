# 环境变量矩阵

本文只做配置文件与关键变量索引。

默认本地部署的服务成员、启动顺序、端口和链路，以 `docs/local-deployment-contract.yaml` 为准。

本文当前只覆盖默认四服务启动集，不覆盖按需服务 `interaction-data-service`。

## 1. `platform-api`

主要配置来源：

- `apps/platform-api/.env`
- `apps/platform-api/.env.example`

关键变量：

- `LANGGRAPH_UPSTREAM_URL`
- `DATABASE_URL`
- `PLATFORM_DB_ENABLED`
- `PLATFORM_DB_AUTO_CREATE`
- `AUTH_REQUIRED`
- `LANGGRAPH_AUTH_REQUIRED`
- `LANGGRAPH_SCOPE_GUARD_ENABLED`
- `JWT_ACCESS_SECRET`
- `JWT_REFRESH_SECRET`

## 2. `platform-web`

主要配置来源：

- `apps/platform-web/.env`
- `apps/platform-web/.env.example`

关键变量：

- `NEXT_PUBLIC_API_URL`
- `NEXT_PUBLIC_ASSISTANT_ID`
- 可选：`LANGGRAPH_API_URL`

## 3. `runtime-service`

主要配置来源：

- `apps/runtime-service/graph_src_v2/.env`
- `apps/runtime-service/graph_src_v2/.env.example`
- `apps/runtime-service/graph_src_v2/conf/settings.yaml`
- `apps/runtime-service/graph_src_v2/conf/settings.local.yaml`

关键变量：

- `APP_ENV`
- `MODEL_ID`
- `ENABLE_TOOLS`
- `TOOLS`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`

缺失模型配置时，优先补这个仓库实际要写入的配置组合：

- `apps/runtime-service/graph_src_v2/.env` 中的 `MODEL_ID`
- `apps/runtime-service/graph_src_v2/conf/settings.yaml` 中对应的 `default.models.<model_id>` 配置块
- 不建议只给零散的 AK/SK、API Key、`base_url` 或模型名

## 4. `runtime-web`

主要配置来源：

- `apps/runtime-web/.env`
- `apps/runtime-web/.env.example`

关键变量：

- `NEXT_PUBLIC_API_URL`
- `NEXT_PUBLIC_ASSISTANT_ID`

## 5. 当前原则

- 默认四服务启动集的环境变量彼此独立维护
- 根目录暂不新增统一 `.env`
- 后续如果确实需要统一入口，再额外设计根级环境编排
- 默认本地部署的事实源不是本文，而是 `docs/local-deployment-contract.yaml`

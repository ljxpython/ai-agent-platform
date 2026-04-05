# 环境变量矩阵

本文只做配置文件与关键变量索引。

默认本地部署的服务成员、启动顺序、端口和链路，以 `docs/local-deployment-contract.yaml` 为准。

本文当前覆盖默认五服务启动集，并额外保留 `platform-web` 的兼容参考说明。

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

## 2. `interaction-data-service`

主要配置来源：

- `apps/interaction-data-service/.env`
- `apps/interaction-data-service/.env.example`

关键变量：

- `SERVICE_NAME`
- `INTERACTION_DB_ENABLED`
- `INTERACTION_DB_AUTO_CREATE`
- `DATABASE_URL`
- `DOCUMENT_ASSET_ROOT`

## 3. `platform-web-vue`

主要配置来源：

- `apps/platform-web-vue/.env.example`
- `apps/platform-web-vue/.env`
- `apps/platform-web-vue/.env.local`

关键变量：

- `VITE_PLATFORM_API_URL`
- `VITE_DEV_PROXY_TARGET`
- `VITE_DEV_PORT`
- `VITE_LANGGRAPH_DEBUG_URL`

## 4. `runtime-service`

主要配置来源：

- `apps/runtime-service/runtime_service/.env`
- `apps/runtime-service/runtime_service/.env.example`
- `apps/runtime-service/runtime_service/conf/settings.yaml`
- `apps/runtime-service/runtime_service/conf/settings.local.yaml`

关键变量：

- `APP_ENV`
- `MODEL_ID`
- `ENABLE_TOOLS`
- `TOOLS`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`

说明：`MODEL_ID` 建议默认留空，让 `settings.yaml` 的 `default_model_id` 生效；只有明确要覆盖默认模型时才填写，而且值必须在 `settings.yaml` 的 `models` 中存在。

缺失模型配置时，优先补这个仓库实际要写入的配置组合：

- `apps/runtime-service/runtime_service/.env` 中的 `MODEL_ID`（只有在你确实需要显式覆盖默认模型时）
- `apps/runtime-service/runtime_service/conf/settings.yaml` 中对应的 `default.models.<model_id>` 配置块
- 不建议只给零散的 AK/SK、API Key、`base_url` 或模型名

## 5. `runtime-web`

主要配置来源：

- `apps/runtime-web/.env`
- `apps/runtime-web/.env.example`

关键变量：

- `NEXT_PUBLIC_API_URL`
- `NEXT_PUBLIC_ASSISTANT_ID`

## 6. `platform-web`（历史兼容入口）

主要配置来源：

- `apps/platform-web/.env`
- `apps/platform-web/.env.example`

说明：

- 当前只用于历史兼容和迁移对照
- 不属于默认本地部署主线

## 7. 当前原则

- 默认五服务启动集的环境变量彼此独立维护
- 根目录暂不新增统一 `.env`
- `apps/platform-web-vue` 是当前正式平台前端宿主
- 后续如果确实需要统一入口，再额外设计根级环境编排
- 默认本地部署的事实源不是本文，而是 `docs/local-deployment-contract.yaml`

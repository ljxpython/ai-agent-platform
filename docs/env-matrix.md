# 环境变量矩阵

文档类型：`Operational`（配置索引，不是唯一事实源）

本文只做配置文件与关键变量索引。

默认本地部署的服务成员、启动顺序、端口和链路，以 `docs/local-deployment-contract.yaml` 为准。

建议按下面这个顺序理解配置口径：

1. `docs/local-deployment-contract.yaml`
2. `docs/local-dev.md`
3. 本文
4. 各 app README / app docs

当前仓库的总哲学是 `AI Harness`：正式主链优先收敛 app-local 配置，避免重新引入 repo-root 统一 `.env` 泥球。

## 1. 当前正式主链

当前正式本地演示链路包括：

- `platform-web-vue`
- `platform-api-v2`
- `runtime-service`
- `interaction-data-service`

可选调试入口：

- `runtime-web`

## 2. `platform-api-v2`

主要配置来源：

- `apps/platform-api-v2/.env`
- `apps/platform-api-v2/.env.example`
- `apps/platform-api-v2/deploy/env/local.example.env`
- `apps/platform-api-v2/deploy/env/dev.example.env`
- `apps/platform-api-v2/deploy/env/staging.example.env`
- `apps/platform-api-v2/deploy/env/prod.example.env`

关键变量：

- `PLATFORM_API_V2_LANGGRAPH_UPSTREAM_URL`
- `PLATFORM_API_V2_INTERACTION_DATA_SERVICE_URL`
- `PLATFORM_API_V2_DATABASE_URL`
- `PLATFORM_API_V2_PLATFORM_DB_ENABLED`
- `PLATFORM_API_V2_PLATFORM_DB_AUTO_CREATE`
- `PLATFORM_API_V2_AUTH_REQUIRED`
- `PLATFORM_API_V2_JWT_ACCESS_SECRET`
- `PLATFORM_API_V2_JWT_REFRESH_SECRET`
- `PLATFORM_API_V2_BOOTSTRAP_ADMIN_ENABLED`

说明：

- `platform-api-v2` 是当前正式控制面宿主
- 它既负责平台治理，也负责受控访问 `runtime-service` 与 `interaction-data-service`

## 3. `interaction-data-service`

主要配置来源：

- `apps/interaction-data-service/.env`
- `apps/interaction-data-service/.env.example`

关键变量：

- `SERVICE_NAME`
- `INTERACTION_DB_ENABLED`
- `INTERACTION_DB_AUTO_CREATE`
- `DATABASE_URL`
- `DOCUMENT_ASSET_ROOT`

说明：

- 它是结果域服务，不承载平台治理主数据
- 新结果域能力应继续沿 app-local 配置扩展，不回退到根级统一 `.env`

## 4. `platform-web-vue`

主要配置来源：

- `apps/platform-web-vue/.env.example`
- `apps/platform-web-vue/.env`
- `apps/platform-web-vue/.env.local`

关键变量：

- `VITE_PLATFORM_API_URL`
- `VITE_PLATFORM_API_V2_URL`
- `VITE_DEV_PROXY_TARGET`
- `VITE_DEV_PORT`
- `VITE_LANGGRAPH_DEBUG_URL`

说明：

- `platform-web-vue` 是当前正式平台前端宿主
- 正常情况下应通过 `platform-api-v2` 访问平台与 testcase 等治理能力

## 5. `runtime-service`

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

## 6. `runtime-web`（可选调试入口）

主要配置来源：

- `apps/runtime-web/.env`
- `apps/runtime-web/.env.example`

关键变量：

- `NEXT_PUBLIC_API_URL`
- `NEXT_PUBLIC_ASSISTANT_ID`

说明：

- 当前只作为可选调试入口
- 默认应直连 `runtime-service`
- 不属于正式产品前端主线

## 7. 历史兼容应用

### 7.1 `platform-web`

主要配置来源：

- `apps/platform-web/.env`
- `apps/platform-web/.env.example`

说明：

- 当前只用于历史兼容和迁移对照
- 不属于默认本地部署主线

### 7.2 `platform-api`

主要配置来源：

- `apps/platform-api/.env`
- `apps/platform-api/.env.example`

说明：

- 当前只保留历史参考与兼容价值
- 不属于正式本地演示主链

## 8. 当前原则

- 默认正式演示链路的环境变量彼此独立维护
- 根目录暂不新增统一 `.env`
- `apps/platform-web-vue` 是当前正式平台前端宿主
- `apps/platform-api-v2` 是当前正式控制面宿主
- `apps/runtime-service` 是当前正式执行层
- `apps/interaction-data-service` 是当前正式结果域服务
- 默认本地正式端口为 `8081 / 8123 / 2142 / 3000`
- 可选调试端口为 `3001`
- 后续如果确实需要统一入口，应先设计新的 harness contract，再决定是否引入新的编排层
- 默认本地部署的事实源不是本文，而是 `docs/local-deployment-contract.yaml`

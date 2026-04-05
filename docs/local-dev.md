# 本地开发与联调说明

本文是给人快速浏览的本地联调摘要；代理在读取 contract 后，也可以自行继续读取本文来补齐启动、验证和脚本使用细节。

默认本地部署的唯一事实源是 `docs/local-deployment-contract.yaml`；如果本文与 contract 有冲突，以 contract 为准。

本文只保留人类排查时最常看的摘要信息，不再承担独立规范源的职责。用户不需要在提示词里额外点名本文，代理应自行决定是否继续读取。

## 1. 固定端口与链路

以下内容对应 contract 中的默认五服务 profile。

- `apps/runtime-service`: `8123`
- `apps/interaction-data-service`: `8090`
- `apps/platform-api`: `2024`
- `apps/platform-web-vue`: `3000`
- `apps/runtime-web`: `3001`

当前默认链路：

- `platform-web-vue` -> `platform-api` -> `runtime-service`
- `platform-api` / `runtime-service` -> `interaction-data-service`
- `runtime-web` -> `runtime-service`

## 2. 配置文件口径

根目录不维护统一 `.env`，本地调试时只使用各应用自己的配置文件：

- `apps/platform-api/.env`
- `apps/platform-web-vue/.env.example`
- `apps/platform-web-vue/.env`
- `apps/platform-web-vue/.env.local`
- `apps/runtime-web/.env`
- `apps/interaction-data-service/.env`
- `apps/runtime-service/runtime_service/.env`
- `apps/runtime-service/runtime_service/conf/settings.yaml`

本地联调时，`runtime-web` 应直连 `http://localhost:8123`，不要沿用旧模板里的 `http://localhost:2024`。

## 3. 推荐启动顺序

1. 启动 `runtime-service`
2. 启动 `interaction-data-service`
3. 启动 `platform-api`
4. 启动 `platform-web-vue`
5. 启动 `runtime-web`

## 4. 各应用启动命令

### 4.1 `apps/runtime-service`

启动前先检查 `apps/runtime-service/runtime_service/.env`：

- `MODEL_ID` 留空：使用 `apps/runtime-service/runtime_service/conf/settings.yaml` 当前环境的 `default_model_id`
- `MODEL_ID` 非空：会覆盖默认模型，且必须是 `settings.yaml` 中真实存在的模型 key

如果只是按默认配置联调，建议把 `MODEL_ID` 留空，避免本地 `.env` 残留旧值导致运行时继续选错模型。

```bash
cd apps/runtime-service
uv run langgraph dev --config runtime_service/langgraph.json --port 8123 --no-browser
```

### 4.2 `apps/interaction-data-service`

```bash
cd apps/interaction-data-service
uv run uvicorn main:app --host 0.0.0.0 --port 8090 --reload
```

### 4.3 `apps/platform-api`

```bash
cd apps/platform-api
uv run uvicorn main:app --host 0.0.0.0 --port 2024 --reload
```

### 4.4 `apps/platform-web-vue`

```bash
cd apps/platform-web-vue
VITE_DEV_PORT=3000 pnpm dev
```

### 4.5 `apps/runtime-web`

```bash
cd apps/runtime-web
PORT=3001 pnpm dev
```

## 5. 最小健康检查

### 5.0 `interaction-data-service`

```bash
curl http://127.0.0.1:8090/_service/health
```

### 5.1 `runtime-service`

```bash
curl http://127.0.0.1:8123/info
curl http://127.0.0.1:8123/internal/capabilities/models
curl http://127.0.0.1:8123/internal/capabilities/tools
```

### 5.2 `platform-api`

```bash
curl http://127.0.0.1:2024/_proxy/health
curl http://127.0.0.1:2024/api/langgraph/info
```

### 5.3 页面访问

- `platform-web-vue`: `http://127.0.0.1:3000`
- `runtime-web`: `http://127.0.0.1:3001`

如果 `platform-api` 的 `/api/langgraph/info` 返回 `200`，说明平台到 runtime 的主联调链路已经打通。

## 6. 根级快捷脚本

仓库根目录提供：

```bash
scripts/dev-up.sh
scripts/check-health.sh
scripts/dev-down.sh
```

推荐把它们理解成固定的操作者入口：

- 启动：`scripts/dev-up.sh`
- 健康检查：`scripts/check-health.sh`
- 停止：`scripts/dev-down.sh`

对于最少描述触发的标准部署，代理可先按 contract 完成检查后尝试根脚本 bring-up；如果脚本失败、状态不清或需要隔离诊断，再回退到手工逐个启动。用户不需要额外指挥这一步。

## 7. 当前约定

- 不共享 `.venv`
- 不共享 Node 依赖
- 不共享根级 `.env`
- `apps/platform-web` 仅作为历史兼容入口保留，不再作为默认本地部署前端
- 先保证默认五服务启动集可独立运行，再处理统一工具链或更深层重构

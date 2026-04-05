# 部署准备与环境说明

本文是默认本地部署的补充说明，重点保留系统依赖、PostgreSQL、环境准备和常见排错信息。代理在读取 contract 后，如果需要更细的环境准备或启动上下文，应自行继续读取本文。

默认本地部署的唯一事实源是 `docs/local-deployment-contract.yaml`；代理执行规则见 `docs/ai-deployment-assistant-instruction.md`。

本文主要回答三个问题：

1. 拉取代码后，需要先准备哪些系统依赖？
2. 默认五服务启动集分别依赖什么、各自怎么配置？
3. `platform-api` 的 PostgreSQL、`.env`、`uv`、`pnpm` 应该怎么准备？

它不是额外提示词负担：用户不需要在请求里单独点名本文，代理应在需要这些细节时自行读取。

当前仓库结构：

```text
agent-platform/
├── apps/interaction-data-service
├── apps/platform-api
├── apps/platform-web
├── apps/platform-web-vue
├── apps/runtime-service
├── apps/runtime-web
├── docs/
└── scripts/
```

当前默认本地部署主线已经切换到 `apps/platform-web-vue`，`apps/platform-web` 只保留为历史兼容入口和迁移参考。

## 1. 总体部署前提

### 1.1 默认五服务启动集的职责

- `apps/platform-api`：平台控制面后端，依赖 PostgreSQL
- `apps/platform-web-vue`：正式平台前端宿主，连接 `platform-api`
- `apps/runtime-service`：LangGraph 运行时执行层，依赖 Python 配置与模型配置
- `apps/runtime-web`：直连 runtime 的调试前端，连接 `runtime-service`
- `apps/interaction-data-service`：结果域服务，承接工作流结果、文档和相关持久化能力

### 1.2 当前推荐联调关系

```text
platform-web-vue -> platform-api -> runtime-service
platform-api -> interaction-data-service
runtime-service -> interaction-data-service
runtime-web  -> runtime-service
```

### 1.3 当前推荐端口

- `platform-api`: `2024`
- `platform-web-vue`: `3000`
- `runtime-service`: `8123`
- `runtime-web`: `3001`
- `interaction-data-service`: `8090`

## 2. 需要先安装什么

### 2.1 Python

仓库内两个 Python 应用都要求：

- `Python 3.13`

证据：

- `apps/platform-api/.python-version`
- `apps/runtime-service/.python-version`
- `apps/platform-api/pyproject.toml`
- `apps/runtime-service/pyproject.toml`

### 2.2 uv

两个 Python 应用都通过 `uv` 管理环境和运行命令。

官方安装方式可选：

```bash
# 官方安装脚本（macOS / Linux）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或 Homebrew
brew install uv
```

安装后建议确认：

```bash
uv --version
uv python list
```

如果本机还没有 Python 3.13，也可以让 uv 安装：

```bash
uv python install 3.13
```

### 2.3 Node.js

当前正式前端宿主与调试前端建议都使用：

- `Node.js 22.x`

证据：

- `apps/platform-web-vue/package.json`
- `apps/runtime-web/.github/workflows/ci.yml`

虽然 `pnpm 10` 最低支持 Node `18.12+`，但当前仓库建议直接按 CI 对齐到 `Node 22.x`。

### 2.4 pnpm

当前前端应用统一固定：

- `pnpm@10.5.1`

证据：

- `apps/platform-web-vue/package.json`
- `apps/runtime-web/package.json`

官方安装方式可选：

```bash
# 方案 A：先装 Node，再启用 Corepack（推荐）
npm install --global corepack@latest
corepack enable pnpm
corepack use pnpm@10.5.1

# 方案 B：官方安装脚本
curl -fsSL https://get.pnpm.io/install.sh | sh -
```

安装后建议确认：

```bash
node -v
pnpm -v
```

### 2.5 PostgreSQL

当前明确要求 PostgreSQL 的应用是：

- `apps/platform-api`

数据库用途不是可选装饰，而是平台控制面的核心依赖，至少覆盖：

- 自建认证
- 用户
- 项目
- 项目成员关系
- agent / assistant profile
- 审计日志
- refresh token

证据：

- `apps/platform-api/.env.example`
- `apps/platform-api/README.md`
- `apps/platform-api/app/db/models.py`

### 2.6 模型 / LLM 接入准备

`runtime-service` 启动前还必须准备模型配置：

- `runtime_service/.env`
- `runtime_service/conf/settings.yaml`

至少要能提供这个仓库实际会落地的一组配置：

- `settings.yaml` 里的 `default.default_model_id`
- `settings.yaml` 里的 `default.models.<model_id>` 配置块

补充约定：`.env` 里的 `MODEL_ID` 默认可以留空；只有在你明确要覆盖 `default.default_model_id` 时才需要填写。

## 3. 一次性准备清单

建议先准备这些：

- 安装 `Python 3.13`
- 安装 `uv`
- 安装 `Node 22.x`
- 安装 `pnpm 10.5.1`
- 准备一个可连通的 PostgreSQL 16+ 实例
- 准备至少一个可用模型 API（OpenAI-compatible / DeepSeek / Moonshot 等）

如果继续读取 root docs 和检查本地文件后，发现这里仍缺少必须由用户提供的材料或决策，再一次性把当前已知缺失项问全，不要让用户重复描述任务。

## 4. PostgreSQL 怎么准备（platform-api）

### 4.1 推荐的数据库参数

当前仓库默认口径：

- host: `127.0.0.1`
- port: `5432`
- database: `agent_platform`
- user: `agent`

### 4.2 Docker 启动 PostgreSQL（推荐）

仓库已有现成手册：`apps/platform-api/docs/postgres-operations.md`

最小启动命令：

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
  postgres:16
```

连接测试：

```bash
docker exec -it "$PG_CONTAINER" psql -U agent -d agent_platform -c "SELECT version();"
```

### 4.3 `platform-api` 至少要准备哪些 PG 相关 env

最小可运行配置：

```env
PLATFORM_DB_ENABLED=true
PLATFORM_DB_AUTO_CREATE=true
DATABASE_URL=postgresql+psycopg://agent:<pg-password>@127.0.0.1:5432/agent_platform
```

说明：

- `PLATFORM_DB_ENABLED=true`：启用平台数据库能力
- `PLATFORM_DB_AUTO_CREATE=true`：首次启动自动建核心表
- `DATABASE_URL`：SQLAlchemy / psycopg 使用的 PostgreSQL 连接串

### 4.4 `platform-api` 会创建哪些核心表

从 `apps/platform-api/app/db/models.py` 可见，当前核心表至少包括：

- `tenants`
- `users`
- `projects`
- `project_members`
- `refresh_tokens`
- `agents`
- `assistant_profiles`
- `audit_logs`

首次本地启动时，如果配置：

```env
PLATFORM_DB_AUTO_CREATE=true
```

则应用会在启动时执行：

```python
Base.metadata.create_all(bind=engine)
```

对应实现见：

- `apps/platform-api/app/db/init_db.py`

### 4.5 生产环境的 PostgreSQL 建议

生产或 staging 不建议继续使用自动建表：

```env
PLATFORM_DB_ENABLED=true
PLATFORM_DB_AUTO_CREATE=false
DATABASE_URL=postgresql+psycopg://agent:${DB_PASSWORD}@prod-pg:5432/agent_platform
```

并建议：

- 迁移前先逻辑备份
- schema 变更走迁移方案，不手改生产库
- 将密码放入部署平台 Secret，不写死在仓库

## 5. 各应用需要准备什么

## 5.1 `apps/platform-api`

### 依赖

- Python `3.13`
- `uv`
- PostgreSQL

### 关键 env

最小本地可运行建议：

```env
LANGGRAPH_UPSTREAM_URL=http://127.0.0.1:8123

PLATFORM_DB_ENABLED=true
PLATFORM_DB_AUTO_CREATE=true
DATABASE_URL=postgresql+psycopg://agent:<pg-password>@127.0.0.1:5432/agent_platform

AUTH_REQUIRED=false
LANGGRAPH_AUTH_REQUIRED=false
LANGGRAPH_SCOPE_GUARD_ENABLED=false

API_DOCS_ENABLED=true

JWT_ACCESS_SECRET=local-access-secret-change-me
JWT_REFRESH_SECRET=local-refresh-secret-change-me
JWT_ACCESS_TTL_SECONDS=1800
JWT_REFRESH_TTL_SECONDS=604800

BOOTSTRAP_ADMIN_USERNAME=admin
BOOTSTRAP_ADMIN_PASSWORD=admin123456
```

### 启动前准备

```bash
cd apps/platform-api
cp .env.example .env
# 或使用更完整模板
cp config/environments/.env.dev.example .env
uv sync
```

### 启动命令

```bash
cd apps/platform-api
uv run uvicorn main:app --host 0.0.0.0 --port 2024
```

### 健康检查

```bash
curl http://127.0.0.1:2024/_proxy/health
curl http://127.0.0.1:2024/api/langgraph/info
```

### 重要说明：`.env` 生效位置以 contract 为准

默认本地部署当前只使用 app-local 配置文件，不使用 repo-root `.env`。

因此这里的结论不再依赖多份文档交叉解释：

- **优先在 `apps/platform-api/.env` 放实际生效配置**
- 如果其他历史文档仍提到 repo-root `.env`，以 contract 为准

## 5.2 `apps/runtime-service`

### 依赖

- Python `3.13`
- `uv`
- 至少一个可用模型 API

### 关键配置文件

- `apps/runtime-service/runtime_service/.env`
- `apps/runtime-service/runtime_service/conf/settings.yaml`

### 最小 `.env` 示例

```env
APP_ENV=test
# Leave empty to use settings.yaml -> <env>.default_model_id.
MODEL_ID=

MASS_URL=https://example.openai-compatible.com/v1
MASS_GLM_4_MODEL=glm-4
MASS_KIMI_KEY=your_api_key_here
```

说明：

- `APP_ENV`：选择 `settings.yaml` 的环境块，如 `test` / `production`
- `MODEL_ID`：默认可留空；留空时使用当前环境的 `default_model_id`
- 如果显式设置 `MODEL_ID`，它会覆盖默认模型，且值必须在 `settings.yaml` 的 `models` 中存在

### 最小 `settings.yaml` 示例

```yaml
default:
  default_model_id: glm4_mass
  models:
    glm4_mass:
      model_provider: openai
      model: your_model_name
      base_url: https://your-openai-compatible-endpoint/v1
      api_key: your_api_key

test:
  default_model_id: glm4_mass
```

如果你是在给 AI 代理补充缺失模型配置，不要只回复 AK/SK、API Key、`base_url` 和模型名；请直接按上面这种仓库配置形状回复完整的 `settings.yaml` 模型块；只有在需要覆盖默认模型时，再额外提供 `MODEL_ID`。

### 启动前准备

```bash
cd apps/runtime-service
cp runtime_service/.env.example runtime_service/.env
cp runtime_service/conf/settings.yaml.example runtime_service/conf/settings.yaml
uv sync
```

### 启动命令

```bash
cd apps/runtime-service
uv run langgraph dev --config runtime_service/langgraph.json --port 8123 --no-browser
```

### 健康检查

```bash
curl http://127.0.0.1:8123/info
curl http://127.0.0.1:8123/internal/capabilities/models
curl http://127.0.0.1:8123/internal/capabilities/tools
```

### 可选：OAuth / Supabase

只有在你要启用 runtime 鉴权时才需要：

- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`

并改用：

```bash
uv run langgraph dev --config runtime_service/langgraph_auth.json --port 8123 --no-browser
```

## 5.3 `apps/interaction-data-service`

### 依赖

- Python `3.13`
- `uv`

### 关键 env

最小本地可运行建议：

```env
SERVICE_NAME=interaction-data-service
INTERACTION_DB_ENABLED=false
INTERACTION_DB_AUTO_CREATE=false
DATABASE_URL=
```

如果你要让它真实接 PostgreSQL，再把：

```env
INTERACTION_DB_ENABLED=true
DATABASE_URL=postgresql+psycopg://agent:<pg-password>@127.0.0.1:5432/agent_platform
```

补进去。

### 启动前准备

```bash
cd apps/interaction-data-service
cp .env.example .env
uv sync
```

### 启动命令

```bash
cd apps/interaction-data-service
uv run uvicorn main:app --host 0.0.0.0 --port 8090 --reload
```

## 5.4 `apps/platform-web-vue`

### 依赖

- Node `22.x`
- `pnpm@10.5.1`

### 关键 env

最小本地可运行建议：

```env
VITE_PLATFORM_API_URL=http://localhost:2024
VITE_DEV_PROXY_TARGET=http://localhost:2024
VITE_DEV_PORT=3000
VITE_LANGGRAPH_DEBUG_URL=
```

### 启动前准备

```bash
cd apps/platform-web-vue
cp .env.example .env
pnpm install
```

### 启动命令

```bash
cd apps/platform-web-vue
VITE_DEV_PORT=3000 pnpm dev
```

### 生产构建命令

```bash
cd apps/platform-web-vue
pnpm build
pnpm preview
```

### 说明

- `apps/platform-web-vue` 是当前正式平台前端宿主
- `apps/platform-web` 不再是默认本地部署主线

## 5.5 `apps/runtime-web`

### 依赖

- Node `22.x`
- `pnpm@10.5.1`

### 关键 env

根据当前仓库联调口径，建议设置成：

```env
NEXT_PUBLIC_API_URL=http://localhost:8123
NEXT_PUBLIC_ASSISTANT_ID=assistant
```

### 启动前准备

```bash
cd apps/runtime-web
cp .env.example .env
pnpm install
```

然后确认 `.env` 里的值与上面的本地联调口径一致；如果你已经直接从当前模板复制，默认应当就是 `http://localhost:8123` + `assistant`。

### 启动命令

```bash
cd apps/runtime-web
PORT=3001 pnpm dev
```

### 重要说明：`runtime-web` 应保持直连 `runtime-service`

当前默认联调口径已经统一为：

- `runtime-web -> runtime-service`
- `runtime-service` 默认端口是 `8123`
- `apps/runtime-web/.env` 与 `.env.example` 都应保持 `NEXT_PUBLIC_API_URL=http://localhost:8123`

如果你本地历史配置里还残留 `http://localhost:2024`，请手动改回 `http://localhost:8123`。

## 6. 从零开始的完整准备步骤

## 6.1 克隆代码

```bash
git clone git@github.com:ljxpython/agent-platform.git
cd agent-platform
```

## 6.2 安装 Python 工具链

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.13
```

## 6.3 安装 Node / pnpm

建议先安装 Node 22，再启用 Corepack：

```bash
node -v
npm install --global corepack@latest
corepack enable pnpm
corepack use pnpm@10.5.1
```

## 6.4 准备 PostgreSQL

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
  postgres:16
```

## 6.5 配置 runtime-service

```bash
cd apps/runtime-service
cp runtime_service/.env.example runtime_service/.env
cp runtime_service/conf/settings.yaml.example runtime_service/conf/settings.yaml
uv sync
```

## 6.6 配置 platform-api

```bash
cd ../platform-api
cp config/environments/.env.dev.example .env
uv sync
```

然后把 `.env` 中的 `DATABASE_URL` 密码替换成你自己的 PostgreSQL 密码。

## 6.7 配置 interaction-data-service

```bash
cd ../interaction-data-service
cp .env.example .env
uv sync
```

## 6.8 配置 platform-web-vue

```bash
cd ../platform-web-vue
cp .env.example .env
pnpm install
```

## 6.9 配置 runtime-web

```bash
cd ../runtime-web
cp .env.example .env
pnpm install
```

然后把 `.env` 改成：

```env
NEXT_PUBLIC_API_URL=http://localhost:8123
NEXT_PUBLIC_ASSISTANT_ID=assistant
```

## 7. 推荐启动顺序

```text
1. runtime-service
2. interaction-data-service
3. platform-api
4. platform-web-vue
5. runtime-web
```

启动命令：

```bash
# terminal 1
cd apps/runtime-service
uv run langgraph dev --config runtime_service/langgraph.json --port 8123 --no-browser

# terminal 2
cd apps/interaction-data-service
uv run uvicorn main:app --host 0.0.0.0 --port 8090 --reload

# terminal 3
cd apps/platform-api
uv run uvicorn main:app --host 0.0.0.0 --port 2024

# terminal 4
cd apps/platform-web-vue
VITE_DEV_PORT=3000 pnpm dev

# terminal 5
cd apps/runtime-web
PORT=3001 pnpm dev
```

## 8. 一键脚本（可选）

根目录已有：

- `scripts/dev-up.sh`
- `scripts/dev-down.sh`
- `scripts/check-health.sh`

对于最少描述触发的标准部署，先按 contract 做配置检查后优先使用根脚本 bring-up；如果脚本失败、状态不清，或已经进入排错阶段，再回退到手工逐个启动。

日常重复操作时，建议固定这样用：

- 启动：`scripts/dev-up.sh`
- 健康检查：`scripts/check-health.sh`
- 停止：`scripts/dev-down.sh`

## 9. 部署时最容易踩的坑

### 9.1 `platform-api` 的 `.env` 放错位置

当前代码实际更依赖你从哪个目录启动进程。

建议：

- 在 `apps/platform-api/.env` 放实际配置
- 并从 `apps/platform-api` 目录执行 `uv run ...`

### 9.2 `platform-web-vue` 仍沿用旧前端认知

当前正式平台前端已经是 `apps/platform-web-vue`。

如果你还在默认部署文档、脚本或本地习惯里优先启动 `apps/platform-web`，会导致你看到的是历史前端，而不是当前正式工作台。

### 9.3 `runtime-web` 历史本地配置残留旧地址

当前模板已经按 `8123` 对齐；如果你本地 `apps/runtime-web/.env` 还残留旧的 `2024` 地址，需要手动改回 `http://localhost:8123`。

### 9.4 `runtime-service` 不是只复制 `.env` 就能跑

它还必须有：

- `runtime_service/conf/settings.yaml`
- 且其中至少有一个可用模型组

### 9.5 `platform-api` 没有 PG 就启动不完整

如果你启用了：

```env
PLATFORM_DB_ENABLED=true
```

但 PostgreSQL 没准备好，平台认证、项目管理、审计等控制面能力无法正常工作。

## 10. 相关文档

- 默认本地部署 contract：`docs/local-deployment-contract.yaml`
- 代理执行说明：`docs/ai-deployment-assistant-instruction.md`
- 人类快速摘要：`docs/local-dev.md`
- 环境变量索引：`docs/env-matrix.md`
- PostgreSQL 深入排查：`apps/platform-api/docs/postgres-operations.md`

除非你在排查特定应用的内部问题，否则默认本地部署不需要先读 app README 或源码。

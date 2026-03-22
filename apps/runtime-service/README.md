# langgraph-agent-studio

## 0) 前置说明（必读）

本项目运行前需要先把两处配置准备好：

- `graph_src_v2/.env`：运行时环境变量（由 `graph_src_v2/langgraph.json` 自动加载）
- `graph_src_v2/conf/settings.yaml`：模型组配置（模型 provider / model / base_url / api_key）

### 0.1 配置 `graph_src_v2/.env`

1) 从模板复制：

```bash
cp graph_src_v2/.env.example graph_src_v2/.env
```

2) 至少确认以下变量已填写：

- `APP_ENV`：环境名（如 `test` / `production`），用于选择 `settings.yaml` 的环境块
- `MODEL_ID`：要使用的模型组 id（必须在 `graph_src_v2/conf/settings.yaml` 的 `models` 中存在）

可选（按需启用）：

- `SYSTEM_PROMPT`：运行时覆盖 prompt。若未设置，则由各个 graph 自己回退到业务默认提示词
- `ENABLE_TOOLS`：公共工具池总开关
- `TOOLS`：公共工具白名单（逗号分隔，支持本地工具与 `mcp:<server>`）

若你需要 OAuth 鉴权（Supabase），还需在 `.env` 中准备：

- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- 可选：`SUPABASE_TIMEOUT_SECONDS`

并使用带鉴权配置启动：`--config graph_src_v2/langgraph_auth.json`。

### 0.2 配置 `graph_src_v2/conf/settings.yaml`

配置加载逻辑在 `graph_src_v2/conf/settings.py`：会先读 `settings.yaml`，再叠加 `settings.local.yaml`（本地覆写）。

建议从模板开始：

```bash
cp graph_src_v2/conf/settings.yaml.example graph_src_v2/conf/settings.yaml
```

最小可运行要求：

- `default.default_model_id`：默认模型组 id
- `default.models.<model_id>`：每个模型组必须包含以下四个字段：
  - `model_provider`
  - `model`
  - `base_url`
  - `api_key`

说明：运行时只需要传/设置 `MODEL_ID`（或使用 `default_model_id`），模型四元组由 `settings.yaml` 统一映射。

安全建议：真实 `api_key` / 内网 `base_url` 建议放在 `settings.local.yaml` 做本地覆写，避免提交到仓库。

### 0.3 更多文档（推荐）

推荐按下面顺序阅读：

1. `graph_src_v2/docs/README.md`
2. `graph_src_v2/docs/02-architecture.md`
3. `graph_src_v2/agents/assistant_agent/graph.py`

更完整的开发/验证说明见：`graph_src_v2/docs/README.md`。

## 本地启动

在当前仓库中，推荐以前台方式启动，便于联调和排错：

```bash
# from repo root
cd apps/runtime-service
uv run langgraph dev --config graph_src_v2/langgraph.json --port 8123 --no-browser
```

如果你已经在 `apps/runtime-service` 目录内，直接执行最后一行 `uv run ...` 即可。

启动后建议先做最小健康检查：

```bash
curl http://127.0.0.1:8123/info
curl http://127.0.0.1:8123/internal/capabilities/models
curl http://127.0.0.1:8123/internal/capabilities/tools
```

如果你需要查看当前仓库统一的本地联调口径，参考根级文档：

- `docs/local-dev.md`
- `docs/env-matrix.md`
- `docs/deployment-guide.md`

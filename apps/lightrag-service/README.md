# lightrag-service

文档类型：`Current App Overview`

`apps/lightrag-service` 是 AITestLab 内的仓库内知识服务，用于把 LightRAG 的服务侧能力收口到当前仓库中，同时保持现有两条接入链路不变：

- `platform-api -> LightRAG HTTP`
- `runtime-service -> LightRAG project-scoped MCP`

当前默认本地一键启动脚本会把它和其他主链服务一起拉起；默认 Compose 栈仍不会自动把它作为成员带起来。

## 首版边界

当前首版只迁入 **service-side upstream**：

- `lightrag-server`
- `lightrag-mcp`
- 必要的 Python 包、配置样例和 MCP 测试

明确不做：

- 不迁上游 WebUI / `lightrag_webui`
- 不迁 CI / release / image publish 工作流
- 不提交运行产物（`data/`、日志、缓存等）
- 不重设计现有 HTTP / MCP 对外契约

## 目录说明

```text
apps/lightrag-service/
├── lightrag/                  # 上游服务侧 Python 包
├── raganything/               # 上游多模态依赖包（保留为服务侧代码）
├── tests/mcp/                 # 必跑的 project-scoped MCP 回归测试
├── deploy/                    # repo-native 可选容器化资产
├── .env.example               # 主机直跑环境样例
├── config.ini.example
└── README.md
```

## 配置文件

主机直跑前至少准备：

```bash
cp apps/lightrag-service/.env.example apps/lightrag-service/.env
```

重点配置：

- `HOST=0.0.0.0`
- `PORT=9621`
- `WORKING_DIR=./data/rag_storage`
- `INPUT_DIR=./data/inputs`

project-scoped MCP 的 repo-local 默认口径：

- `MCP_TRANSPORT=sse`
- `MCP_HOST=127.0.0.1`
- `MCP_PORT=8621`
- `MCP_PATH=/sse`
- `MCP_MESSAGE_PATH=/messages/`
- `LIGHTRAG_MCP_STORAGE_ROOT=${WORKING_DIR}`
- `LIGHTRAG_MCP_INPUT_ROOT=${INPUT_DIR}`

## 本地主机直跑（推荐）

### 1. 启动 HTTP 服务

```bash
cd apps/lightrag-service
uv run lightrag-server
```

默认访问：

- `http://127.0.0.1:9621/health`

### 2. 启动 project-scoped MCP SSE

```bash
cd apps/lightrag-service
MCP_TRANSPORT=sse \
MCP_HOST=127.0.0.1 \
MCP_PORT=8621 \
MCP_PATH=/sse \
MCP_MESSAGE_PATH=/messages/ \
LIGHTRAG_MCP_STORAGE_ROOT="${LIGHTRAG_MCP_STORAGE_ROOT:-./data/rag_storage}" \
LIGHTRAG_MCP_INPUT_ROOT="${LIGHTRAG_MCP_INPUT_ROOT:-./data/inputs}" \
uv run --with 'fastmcp>=3.2.0' python -m lightrag.mcp
```

默认 SSE 地址：

- `http://127.0.0.1:8621/sse`

### 3. 用仓库根脚本管理

仓库根目录脚本现在会默认联动它，同时也提供单独控制脚本：

- `scripts/lightrag-service-up.sh`
- `scripts/lightrag-service-health.sh`
- `scripts/lightrag-service-down.sh`

`scripts/dev-up.sh` / `scripts/check-health.sh` / `scripts/dev-down.sh` 已经会串联这组脚本，因此 LightRAG HTTP + MCP 现在属于默认本地一键启动的一部分。
默认脚本口径同样收敛到：

- `WORKING_DIR=./data/rag_storage`
- `INPUT_DIR=./data/inputs`

## 与 AITestLab 的契约对齐

### HTTP lane

`platform-api` 继续使用已有配置：

- `PLATFORM_API_KNOWLEDGE_UPSTREAM_URL=http://127.0.0.1:9621`

并继续发送 `LIGHTRAG-WORKSPACE` header。

### MCP lane

`runtime-service` 继续使用：

- `TEST_CASE_V2_KNOWLEDGE_MCP_URL=http://127.0.0.1:8621/sse`

且继续只传显式 `project_id`。

### 共享语料规则

虽然 MCP 仍对外暴露 `project_id`，HTTP 仍对外暴露 `LIGHTRAG-WORKSPACE`，但当前迁移版内部必须把两者收口到**同一份知识语料**：

- HTTP lane 使用 `workspace_key = kb_<project_uuid.hex>`
- MCP lane 内部也把 `project_id` 映射到相同 `workspace_key`
- MCP 与 HTTP 共享同一个 `WORKING_DIR` 根目录和同一套 workspace/input-dir 约定

这保证 `platform-api` 写入的项目知识可以被 `runtime-service` 的 MCP 查询读取到。

## 必跑验证

最小必跑：

```bash
cd apps/lightrag-service
uv run python -m compileall lightrag
uv run pytest tests/mcp/test_mcp_contract.py tests/mcp/test_project_query_service.py tests/mcp/test_project_scope_isolation.py tests/mcp/test_document_status_tools.py -q
```

如果要做 repo-local 烟雾验证：

```bash
bash ../../scripts/lightrag-service-up.sh
bash ../../scripts/lightrag-service-health.sh
bash ../../scripts/lightrag-service-down.sh
```

## 容器化

可选容器化资产位于：

- `apps/lightrag-service/deploy/Dockerfile`
- `apps/lightrag-service/deploy/docker-compose.lightrag-service.yml`
- `apps/lightrag-service/deploy/.env.lightrag-service.example`

容器 lane 是可选补充，不改变 root stack 的默认成员。

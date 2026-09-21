# 非 Docker 配置矩阵

2026-09-21 收口，按实际脚本、配置类核对。操作见[部署手册](deployment-guide.md)。
仅记录名称和占位符，真实密码、JWT secret、模型 Key、token 只存私有配置。

## 读取规则

| 文件 | 使用者 | 注意 |
|---|---|---|
| apps/runtime-service/.env | 脚本、GraphHarbor API/Worker | 被 bash source，必须正确引用特殊字符 |
| apps/platform-api/.env | Settings、database.py | dotenv 读取，进程环境优先，不直接 source |
| apps/platform-web/.env.local | Vite | 仅公开参数；脚本覆盖 API、代理、端口 |
| apps/interaction-data-service/.env | 可选结果域 | 默认不启动 |
| 根目录 .env | 私有保留文件 | 非统一启动配置，不整体注入 |

旧 Runtime 嵌套目录和 conf/settings*.yaml 已退出默认链路，模型来源是平台模型目录。

## Runtime

| 字段 | 推荐值 / 规则 |
|---|---|
| DATABASE_URI | postgresql://runtime_service:<URI编码密码>@127.0.0.1:5432/runtime_service |
| REDIS_URI | redis://127.0.0.1:6379/7；认证按现有环境 |
| PLATFORM_RUNTIME_DELEGATION_SECRET | 与平台同值，至少 32 字节 |
| PLATFORM_RUNTIME_DELEGATION_ISSUER | platform-api |
| PLATFORM_RUNTIME_DELEGATION_AUDIENCE | runtime-service |
| PLATFORM_RUNTIME_MODEL_CONFIG_URL | http://127.0.0.1:2142/api/runtime/internal/model-config |
| GRAPHHARBOR_RUNTIME_CONTEXT_SECRET | 独立随机值，至少 32 字符，API/Worker 共用 |
| GRAPHHARBOR_RUNTIME_CONTEXT_ISSUER | https://runtime-service.local，身份标识，无需建站 |
| GRAPHHARBOR_RUNTIME_CONTEXT_AUDIENCE | graphharbor-worker |
| GRAPHHARBOR_RUN_TIMEOUT_SECONDS | 900（支持长会话、深度调研与大型方案生成；默认 300） |
| GRAPHHARBOR_WORKSPACE_ROOT | 可写绝对路径，推荐持久目录；本地原值 /tmp/aitestlab-runtime-workspaces |
| RUNTIME_WORKSPACE_MAX_FILE_BYTES | 10485760 |
| RUNTIME_WORKSPACE_MAX_FILES | 10000 |
| RUNTIME_WORKSPACE_MAX_TOTAL_BYTES | 1073741824 |
| RUNTIME_WORKSPACE_TTL_SECONDS | 604800 |
| RUNTIME_SHOWCASE_BACKEND | local |
| RUNTIME_TERMINAL_BACKEND | local |
| RUNTIME_TERMINAL_ENABLED | 1，工具以应用用户权限执行 |
| RUNTIME_GRAPH_CONFIG_PATH | 可选，默认 apps/runtime-service/langgraph.json |

LANGFUSE_ENABLED=true 时必须提供 LANGFUSE_PUBLIC_KEY、LANGFUSE_SECRET_KEY、LANGFUSE_BASE_URL。
LANGSMITH_API_KEY、图片、搜索、MCP 凭据按功能提供。
DEEPSEEK_PROXY_* / GPT_PROXY_* 供独立 smoke 等使用，不会创建平台模型目录。
不要求 LANGGRAPH_CLOUD_LICENSE_KEY、旧 MODEL_ID 或 YAML profile。

以上名称与通用 .env.example 对齐；收到个人交接时按其账号映射替换库名和角色。
业务连接必须实际使用 SCRAM，.pgpass（600）只负责提供客户端凭据，不替代服务端认证。
具体正反向验收见[部署手册第 6 节](deployment-guide.md#6-建库密码认证和验收按顺序完成)。

## Platform API

下表字段都加 PLATFORM_API_ 前缀：

| 后缀 | 推荐值 / 规则 |
|---|---|
| APP_ENV | local，仅受控开发 |
| PLATFORM_DB_ENABLED | true |
| PLATFORM_DB_AUTO_CREATE | false |
| DATABASE_URL | postgresql+psycopg://platform_api:<URI编码密码>@127.0.0.1:5432/platform_api |
| LANGGRAPH_UPSTREAM_URL | http://127.0.0.1:8123 |
| RUNTIME_DELEGATION_SECRET | 与 Runtime 同值 |
| RUNTIME_DELEGATION_ISSUER | platform-api |
| RUNTIME_DELEGATION_AUDIENCE | runtime-service |
| MODEL_CONFIG_MASTER_KEY | 有效 Fernet 密钥，持久保存 |
| RUNTIME_MODEL_CONFIG_SECRET | 可选，默认复用委托密钥 |
| JWT_ACCESS_SECRET / JWT_REFRESH_SECRET | 两个独立随机值，不能保留模板值 |
| AUTH_REQUIRED | true |
| BOOTSTRAP_ADMIN_ENABLED | 首次 true，确认后可关闭 |
| BOOTSTRAP_ADMIN_USERNAME | admin |
| BOOTSTRAP_ADMIN_PASSWORD | 私有密码，不写公开文档 |
| CORS_ALLOW_ORIGINS | JSON 数组；推荐前端同源代理 |

LANGGRAPH_UPSTREAM_API_KEY 可选，不是当前 GraphHarbor 委托认证必填项。
旧 OPERATIONS_* 已不代表平台 Worker，创建新环境可省略。
完整规则见[平台配置](../../apps/platform-api/docs/handbook/configuration.md)。

## Platform Web

```dotenv
VITE_PLATFORM_API_URL=/
VITE_PLATFORM_API_RUNTIME_ENABLED=true
VITE_DEV_PROXY_TARGET=http://127.0.0.1:2142
VITE_DEV_PORT=3000
VITE_LANGGRAPH_DEBUG_URL=
```

VITE_* 会进入浏览器，不放密钥。SSH 只转发前端即可。

## 可选结果域

SERVICE_NAME=interaction-data-service，当前本地 INTERACTION_DB_ENABLED=false、
INTERACTION_DB_AUTO_CREATE=false、DATABASE_URL 为空。
启用时使用独立库 interaction_data_service 和同名角色，按结果域自己的规范建表；
控制面 Alembic 不管理这些表。

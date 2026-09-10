# 配置

定义见[config.py](../../src/platform_api/config.py)。环境变量统一加 `PLATFORM_API_` 前缀；环境变量优先于工作目录 `.env`，未提供时使用Settings默认值。示例文件是本地配置，不是生产默认值。未知项被忽略，拼错变量不会自动报错。

## 启动与数据库

以下后缀均需加上述前缀。

| 后缀 | 代码默认值 | 要求 |
| --- | --- | --- |
| APP_ENV | local | local/dev/staging/prod/production |
| APP_NAME / APP_VERSION | Platform API / 0.1.2 | 展示信息，不是依赖版本选择器 |
| API_DOCS_ENABLED | true | prod/production必须false |
| CORS_ALLOW_ORIGINS | ["*"] | 明确前端来源，推荐JSON数组 |
| PLATFORM_DB_ENABLED | false | 业务需要开启；开启时DATABASE_URL必填 |
| PLATFORM_DB_AUTO_CREATE | false | 仅本地SQLite快速开发可开启，PG用Alembic |
| DATABASE_URL | 无 | 同步SQLAlchemy URL，如postgresql+psycopg://user:password@127.0.0.1:5432/platform |

## 用户与服务账号

- `AUTH_REQUIRED=true`，实际接入保持认证开启。
- `JWT_ACCESS_SECRET`、`JWT_REFRESH_SECRET` 自行设置并分别保管，不使用示例秘密。`JWT_ALGORITHM=HS256`，支持HS256/384/512。
- `JWT_ISSUER=platform-api`、`JWT_AUDIENCE=platform-control-plane`；`JWT_ACCESS_TTL_SECONDS=1800`、`JWT_REFRESH_TTL_SECONDS=604800`。
- `JWT_ACCESS_KID=access-v1`、`JWT_REFRESH_KID=refresh-v1`。轮换时通过 `JWT_ACCESS_VERIFICATION_KEYS`、`JWT_REFRESH_VERIFICATION_KEYS` JSON映射保留旧验证键，区分签发与验证。
- `BOOTSTRAP_ADMIN_ENABLED=true`、`BOOTSTRAP_ADMIN_USERNAME=admin`，自行设置 `BOOTSTRAP_ADMIN_PASSWORD`。初始化后按运维要求关闭，prod/production禁止启用bootstrap。
- `SERVICE_ACCOUNTS_ENABLED=true`、`SERVICE_ACCOUNT_API_KEY_HEADER=x-platform-api-key`、`SERVICE_ACCOUNT_TOKEN_DEFAULT_TTL_DAYS=90`，详见[权限](../standards/permission-standard.md)。
- `OIDC_ENABLED=false`；启用时配置校验要求 `OIDC_ISSUER_URL`、`OIDC_CLIENT_ID`。当前只有配置边界/视图，没有完整OIDC登录流程。

## Runtime信任与模型

| Platform后缀 | 默认/要求 | Runtime对应 |
| --- | --- | --- |
| LANGGRAPH_UPSTREAM_URL | http://127.0.0.1:8123 | 实际GraphHarbor API |
| LANGGRAPH_UPSTREAM_TIMEOUT_SECONDS | 30，范围(0,600] | 普通请求超时，长流读取由adapter处理 |
| LANGGRAPH_UPSTREAM_API_KEY | 可选 | 部署需要时填写，不是用户token |
| RUNTIME_DELEGATION_SECRET | 空；实际网关必需，至少32字节 | PLATFORM_RUNTIME_DELEGATION_SECRET |
| RUNTIME_DELEGATION_ISSUER | platform-api | PLATFORM_RUNTIME_DELEGATION_ISSUER |
| RUNTIME_DELEGATION_AUDIENCE | runtime-service | PLATFORM_RUNTIME_DELEGATION_AUDIENCE |
| RUNTIME_DELEGATION_KID | runtime-delegation-v1 | 委托签发key ID |
| RUNTIME_DELEGATION_TTL_SECONDS | 60，范围10–300 | 短期委托 |
| MODEL_CONFIG_MASTER_KEY | 无，配置模型前必填 | 仅Platform持有，有效Fernet密钥 |
| RUNTIME_MODEL_CONFIG_SECRET | 未配置则复用委托secret | Platform签发/验证模型引用 |

Runtime另需 `PLATFORM_RUNTIME_MODEL_CONFIG_URL` 指向本平台 `/api/runtime/internal/model-config`。双方委托secret/issuer/audience必须一致；业务JWT由Platform/Runtime处理，不给GraphHarbor核心增加业务handler。

在 `apps/platform-api` 生成本机master key：

```bash
uv run --frozen python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

输出属于秘密，写入自己的秘密管理配置，不贴进日志、文档或Git。丢失master key会导致模型连接无法解密，必须与数据库备份配套保管。

## 观测与生产校验

`OBSERVABILITY_METRICS_TOP_PATHS_LIMIT` 默认10，范围1–50。metrics是进程内快照，不是跨实例持久化指标系统。

prod/production启动要求关闭API文档与bootstrap、覆盖内置默认JWT秘密、配置Runtime委托secret。staging不执行全部生产校验；这些校验不代表生产部署已验收，也不替部署者启用数据库或配置网络。

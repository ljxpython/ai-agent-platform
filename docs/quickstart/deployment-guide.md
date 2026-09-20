# 非 Docker 开发环境部署手册

当前事实源，2026-09-21 收口；按启动脚本、配置类和依赖锁文件核对。
适用于本机或 Linux 远程开发机，直接运行源码。配置见[环境矩阵](env-matrix.md)，
机器可读范围见[部署契约](../local-deployment-contract.yaml)，Docker 另见[容器指南](../../deploy/README.md)。

## 1. 范围与完成标准

本手册默认新建开发环境，复制代码和配置，使用空库初始化管理员；不迁移旧项目、其他用户、聊天、Thread、Checkpoint、
审计、Redis 队列或工作区。源码 graph 随代码提供，平台项目和模型连接需要重新创建。
复制 .env 不会复制数据库里的用户和模型目录。

默认只有四个进程：Runtime API、Runtime Worker、Platform API、Platform Web。
没有 Platform Worker；结果域是独立可选服务，LightRAG 不在当前仓库可部署范围。

| 组件 | 地址 / 推荐 |
|---|---|
| PostgreSQL | 127.0.0.1:5432，推荐 17 |
| Redis | 127.0.0.1:6379/7，推荐 Redis 7，独立逻辑库 |
| Runtime API | 127.0.0.1:8123，GraphHarbor |
| Runtime Worker | 无监听端口，与 API 共用配置、PG、Redis、工作区 |
| Platform API | 127.0.0.1:2142 |
| Platform Web | 127.0.0.1:3000，Vite 同源代理 |
| 可选结果域 | 127.0.0.1:8081，默认不启动、不落库 |

完成标准：依赖检查、迁移、四进程健康、管理员登录，再创建项目、配置模型并完成一次真实聊天。
健康检查不等于模型链路验收。接手部署者先读[运维交接与回执](operator-handoff.md)。
本文是通用步骤；具体机器、账号映射、源码版本和私有配置位置以该次交接的 README 为准。
通用手册中的示例账号不能覆盖已确认的私有交接配置。

## 2. 检查服务器，复用已有依赖

```bash
cat "/etc/os-release"
uname -m
free -h
df -h "/"
python3 --version
uv --version
node --version
pnpm --version
psql --version
ss -ltn
```

推荐至少 4 核、8 GB 内存、20 GB 可用磁盘，这是容量建议而非性能承诺。
4 GB 可先尝试基础链路，前端类型检查和并发工具执行可能需要更多内存。
云安全组仅开放受控来源 SSH；通过 SSH 隧道访问前端，不开放开发端口、PG 和 Redis 到公网。

### 已有基础设施

核对版本、端口、进程用户和安装来源。面板管理的 PG/Redis 继续由面板管理，
不要用 apt 安装第二套抢占端口。确保 psql、pg_isready、pg_dump、redis-cli 在 PATH。
已有同名数据库需先确认归属；本流程不清库、不重置密码、不导入 dump。

### 全新 Debian 13 / Ubuntu 24.04

仅对缺少这些组件的新机执行：

```bash
sudo apt-get update
sudo apt-get install -y git curl ca-certificates build-essential python3 python3-venv \
  python3-dotenv lsof postgresql postgresql-client redis-server
sudo systemctl enable --now postgresql redis-server
```

Debian 13 默认 PG 17，Ubuntu 24.04 默认 PG 16；统一 PG 17 时使用 PostgreSQL 官方包源。
面板版与系统版不要混装。PG 保持回环监听，TCP 本地连接采用 scram-sha-256；
本地和服务器都不得用 trust 绕过密码校验。Redis 保持回环监听和 protected mode，
已有认证则配置相应 REDIS_URI，不为教程关闭认证。

### Python / uv / Node / pnpm

应用使用普通开发用户，系统安装才使用 sudo。启动脚本直接调用 python3 并导入 dotenv，
因此系统 python3-dotenv 或已激活的应用虚拟环境必须可用。

uv 缺失时：

```bash
curl -LsSf "https://astral.sh/uv/install.sh" | sh
export PATH="$HOME/.local/bin:$PATH"
uv python install 3.13
```

Node 使用 22.x，pnpm 使用 10.5.1；已有正确版本直接复用。
全新 Linux x86_64 可将 Node 官方发行包安装到当前用户（其他架构替换发行包名）：

```bash
mkdir -p "$HOME/.local/opt"
cd "$HOME/.local/opt"
curl -fLO "https://nodejs.org/dist/v22.22.2/node-v22.22.2-linux-x64.tar.xz"
curl -fLO "https://nodejs.org/dist/v22.22.2/SHASUMS256.txt"
grep ' node-v22.22.2-linux-x64.tar.xz$' "SHASUMS256.txt" | sha256sum -c -
tar -xJf "node-v22.22.2-linux-x64.tar.xz"
export PATH="$HOME/.local/opt/node-v22.22.2-linux-x64/bin:$PATH"
corepack enable
corepack prepare pnpm@10.5.1 --activate
node --version
pnpm --version
```

将 PATH 配置保存到该用户的 shell 启动文件，再开一个登录终端核对。
若已有发行版不含 Corepack，在自己管理的 Node 环境安装 pnpm@10.5.1 即可。

## 3. 代码与依赖

从自己的仓库地址 clone，或使用源码交接包，已有目录不要直接覆盖。
交接包是不含 .git 的当前工作区快照，包含交付时未提交的源码，不能当成已发布 commit。
要继续 Git 开发，在独立目录 clone 后对比同步。

以下在仓库根目录执行：

```bash
uv sync --project "apps/runtime-service" --python 3.13 --frozen
uv sync --project "apps/platform-api" --python 3.13 --frozen
pnpm --dir "apps/platform-web" install --frozen-lockfile
```

每个应用独立 .venv 和锁文件，不复制 macOS 的 .venv/node_modules 到 Linux。
GraphHarbor 从 Runtime 锁文件安装，不依赖相邻源码仓库、私有 wheel、LangGraph CLI 或 license key。

## 4. 数据库与账号标准

通用模板与 apps/*/.env.example 对齐：

| 用途 | 默认数据库 / 逻辑库 | 默认用户名 | 凭据来源 |
|---|---|---|---|
| Runtime | runtime_service | runtime_service | Runtime 私有 .env |
| Platform API | platform_api | platform_api | Platform 私有 .env |
| Redis | 7 | 按已有 ACL | 当前服务器认证配置 |
| 平台登录 | 平台数据库里的用户 | admin | Platform bootstrap 配置 |
| 可选结果域 | interaction_data_service | interaction_data_service | 启用时单独设置 |

如果交接指定了其他名字，后续 SQL、HBA、连接串统一替换，不能只改其中一处。
个人交接中的库名、角色名属于该环境的映射，不是所有人的必填值。

业务角色创建为非超级用户，不授予 CREATEDB、CREATEROLE、REPLICATION 或 BYPASSRLS。
SSH 用户、PG 管理员、PG 业务角色和平台管理员是四种身份；同名不代表相同权限或密码。
新环境不复制开发机的超级用户权限。所有真实密码和密钥只存私有配置。

.pgpass（权限 600）可让遵循 libpq/passfile 的客户端自动提供密码，不等于服务器允许免密。
为测试认证效果，第 6 节会隔离该文件。不读取密码文件的客户端必须显式配置密码。

## 5. 配置文件

| 路径 | 用途 |
|---|---|
| apps/runtime-service/.env | PG、Redis、委托、工作区、工具和观测配置 |
| apps/platform-api/.env | 平台 PG、JWT、管理员、模型加密主密钥 |
| apps/platform-web/.env.local | 前端公开参数，不放密钥 |
| apps/interaction-data-service/.env | 可选结果域，当前本地禁用落库 |
| 根目录 .env | 私有备份，非统一配置入口，不整体 source 或注入应用 |

没有私有配置时从示例创建缺失文件，已有文件不要覆盖：

```bash
test -e "apps/runtime-service/.env" || cp "apps/runtime-service/.env.example" "apps/runtime-service/.env"
test -e "apps/platform-api/.env" || cp "apps/platform-api/.env.example" "apps/platform-api/.env"
test -e "apps/platform-web/.env.local" || cp "apps/platform-web/.env.example" "apps/platform-web/.env.local"
chmod 600 "apps/runtime-service/.env" "apps/platform-api/.env" "apps/platform-web/.env.local"
```

Runtime .env 被 bash source，值须兼容 shell，特殊字符正确引用。
Platform .env 按 dotenv 解析，不要直接 source（应用名称等可能有空格）。
以下占位符必须替换：

```dotenv
# apps/runtime-service/.env
DATABASE_URI=postgresql://runtime_service:<URI编码密码>@127.0.0.1:5432/runtime_service
REDIS_URI=redis://127.0.0.1:6379/7
PLATFORM_RUNTIME_MODEL_CONFIG_URL=http://127.0.0.1:2142/api/runtime/internal/model-config
RUNTIME_SHOWCASE_BACKEND=local
RUNTIME_TERMINAL_BACKEND=local
RUNTIME_TERMINAL_ENABLED=1

# apps/platform-api/.env
PLATFORM_API_DATABASE_URL=postgresql+psycopg://platform_api:<URI编码密码>@127.0.0.1:5432/platform_api
PLATFORM_API_PLATFORM_DB_ENABLED=true
PLATFORM_API_PLATFORM_DB_AUTO_CREATE=false
PLATFORM_API_LANGGRAPH_UPSTREAM_URL=http://127.0.0.1:8123
PLATFORM_API_BOOTSTRAP_ADMIN_ENABLED=true
PLATFORM_API_BOOTSTRAP_ADMIN_USERNAME=admin
PLATFORM_API_BOOTSTRAP_ADMIN_PASSWORD=<私有密码>

# apps/platform-web/.env.local
VITE_PLATFORM_API_URL=/
VITE_PLATFORM_API_RUNTIME_ENABLED=true
VITE_DEV_PROXY_TARGET=http://127.0.0.1:2142
VITE_DEV_PORT=3000
```

还必须完成以下配置，详见[矩阵](env-matrix.md)：

- 平台 PLATFORM_API_RUNTIME_DELEGATION_SECRET 与 Runtime PLATFORM_RUNTIME_DELEGATION_SECRET 完全一致，至少 32 字节。
- 双方 delegation issuer/audience 为 platform-api/runtime-service。
- GRAPHHARBOR_RUNTIME_CONTEXT_SECRET 独立生成，至少 32 字符；API 和 Worker 共用。
- context issuer/audience 为 https://runtime-service.local / graphharbor-worker，issuer 是标识，无需部署该域名。
- 两个 JWT secret 使用独立随机值，不保留示例值。
- PLATFORM_API_MODEL_CONFIG_MASTER_KEY 是有效 Fernet 密钥，持久保存；正式模型目录依赖它加解密。
- 保留 Runtime 示例中的工作区配额、超时和 TTL 必填数值。
- GRAPHHARBOR_WORKSPACE_ROOT 是可写的绝对路径；推荐持久目录，配置中不要直接写未展开的 ~。
- LANGFUSE_ENABLED=true 时必须配置完整观测凭据，不使用则关闭。

创建工作区可执行 mkdir -p "$HOME/.local/share/ai-agent-platform/workspaces"，再把展开后的绝对路径填入配置。
本地工具和终端具有服务用户权限，因此应用不要用 root 运行。

没有私有交接配置时，可在平台目录执行下面命令生成随机密钥；每次取独立随机值，
仅将输出写入自己的受保护配置，不录屏、不贴日志。已经有真实密钥的文件不要重新生成覆盖。

```bash
cd "apps/platform-api"
uv run --frozen python -c 'import secrets; print(secrets.token_urlsafe(48))'
uv run --frozen python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
cd "../.."
```

## 6. 建库、密码认证和验收（按顺序完成）

### 6.1 先确认管理入口和现有数据

Linux 系统安装通常可用下列 peer 管理入口；面板安装的 psql 路径和系统用户按实际替换。
TCP 管理已启用密码时，也可用其受保护的 PGPASSFILE 连接，不改变现有管理认证。

```bash
sudo -u postgres psql -X -d postgres
```

以下语句在同一个管理员 psql 会话中执行；先保留该会话直到新连接测试通过：

```sql
SELECT current_user, version();
SHOW hba_file;
SHOW listen_addresses;
SHOW port;
SHOW password_encryption;
SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls
FROM pg_roles WHERE rolname IN ('runtime_service', 'platform_api');
SELECT datname, pg_get_userbyid(datdba) AS owner
FROM pg_database WHERE datname IN ('runtime_service', 'platform_api');
SELECT line_number, type, database, user_name, address, auth_method, error
FROM pg_hba_file_rules ORDER BY line_number;
```

| 发现 | 下一步 |
|---|---|
| 角色和数据库均不存在 | 执行 6.2 |
| 对象已存在且确认属于此次环境 | 不重建；核对密码、owner、角色权限后继续 |
| 同名库含未知业务数据或 owner/权限不符 | 停止该数据库变更，由负责人确定复用或另取名称 |
| 其他项目也使用当前实例 | 只约束本次业务角色，不整体替换全部 HBA 规则 |

已有角色不得自动降权或重置密码。先用其已确认的密码；确需修正权限或密码时按影响范围处理。
本手册不使用 DROP、清空表或恢复旧 dump。可选结果域库暂不需要创建。

### 6.2 新建两个业务角色与空库

仅创建确认不存在的对象。先设置本会话使用 SCRAM 保存密码；
反斜杠 password 命令会交互询问两遍密码，输入私有应用配置中对应值，不写进 SQL 字符串或 shell 历史。

```sql
SET password_encryption = 'scram-sha-256';
CREATE ROLE runtime_service LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
\password runtime_service
CREATE DATABASE runtime_service OWNER runtime_service;
CREATE ROLE platform_api LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
\password platform_api
CREATE DATABASE platform_api OWNER platform_api;
```

有交接私有密码就保持一致，不重复生成。独立新环境自行生成密码，再写入对应 app-local .env；
URL 中的特殊字符要进行 URI 编码，不把编码后的密码作为数据库原始密码设置。
仅配置两个库时无需运行会额外创建结果域库的全栈初始化脚本。
已有自动化需求可复用[数据库规范](../guides/database-operations.md)中的建库脚本，不与本节重复执行。

### 6.3 设置真正校验密码的 HBA 规则

从 SHOW hba_file 得到实际文件路径，用部署机器的管理员权限操作：
先做权限受保护、文件名唯一的备份，再用编辑器添加以下规则。
将示例角色替换成 6.2 的实际角色，规则放在任何可能先匹配它们的 trust/peer 规则之前。

```text
# Only the application roles for this deployment:
local   all   runtime_service,platform_api                         scram-sha-256
host    all   runtime_service,platform_api   127.0.0.1/32            scram-sha-256
host    all   runtime_service,platform_api   ::1/128                 scram-sha-256
```

HBA 按首条匹配规则执行；追加到文件末尾但前面有 trust，不会得到密码保护。
保留现有 postgres 管理员的 peer 入口及其他项目规则，不整文件替换。
上述两个业务角色禁止复制权限，因此不新增复制访问规则。
监听保持回环地址；这里只需 reload，不更改端口或重启数据库。

仍在保留的管理会话中执行：

```sql
SELECT line_number, error FROM pg_hba_file_rules WHERE error IS NOT NULL;
SELECT rolname, rolpassword LIKE 'SCRAM-SHA-256$%' AS password_is_scram
FROM pg_authid WHERE rolname IN ('runtime_service', 'platform_api');
SELECT pg_reload_conf();
```

要求第一条无错误、两个 password_is_scram 均 true、reload 返回 true。
这只能证明规则能解析和已请求加载，最终是否生效由下一节新连接验证。
失败时通过保留的管理会话恢复 HBA 备份并 reload；新建对象保留排查，不自动删除。
确认应用可用后再结束管理会话。

### 6.4 隔离密码文件，验证正确、缺失和错误密码

依赖已按第 3 节安装、两个 app-local .env 已填真实密码。
在仓库根目录使用 Runtime Python；只执行 SELECT 1，不读取业务数据。
先验证正确密码成功，再验证另外两种情况确为认证拒绝，不能把端口不通当成密码保护成功。

```bash
"apps/runtime-service/.venv/bin/python" - <<'PY_AUTH'
import os
import tempfile
from urllib.parse import unquote, urlsplit

import psycopg
from dotenv import dotenv_values

# Prevent ambient libpq credentials/services from masking a missing password.
for key in list(os.environ):
    if key.startswith("PG"):
        os.environ.pop(key)
with tempfile.NamedTemporaryFile() as empty_passfile:
    for filename, key in [
        ("apps/runtime-service/.env", "DATABASE_URI"),
        ("apps/platform-api/.env", "PLATFORM_API_DATABASE_URL"),
    ]:
        endpoint = urlsplit(dotenv_values(filename)[key])
        password = unquote(endpoint.password or "")
        assert password, f"{filename}: database password missing"
        for mode, supplied in [
            ("correct", password),
            ("missing", ""),
            ("wrong", password + "-intentionally-wrong"),
        ]:
            try:
                with psycopg.connect(
                    host=endpoint.hostname, port=endpoint.port or 5432,
                    dbname=endpoint.path.lstrip("/"),
                    user=unquote(endpoint.username or ""),
                    password=supplied, passfile=empty_passfile.name,
                    connect_timeout=5,
                ) as connection:
                    assert connection.execute("SELECT 1").fetchone() == (1,)
                accepted = True
            except psycopg.OperationalError as exc:
                auth_rejected = (
                    exc.sqlstate == "28P01"
                    or "password authentication failed" in str(exc)
                    or "no password supplied" in str(exc)
                )
                assert auth_rejected, f"{filename}: network/server failure, not auth proof"
                accepted = False
            assert accepted == (mode == "correct"), (filename, mode)
            print(filename, mode, "PASS")
PY_AUTH
```

预期 6 行 PASS，不输出任何密码。该脚本验证实际应用连接地址；
若服务器启用了 IPv6 或 Unix socket 业务访问，还需按同样方法分别指定 ::1 和
SHOW unix_socket_directories 返回的目录验证。未监听的协议可标“不适用”，不能标“通过”。
管理员 peer 连接不属于业务角色缺密码测试，不应拿它当成失败。

Redis 使用实际认证方式验证 PING；无认证的回环实例可执行 redis-cli -n 7 ping。
有认证时通过受保护配置或交互提供密码，不写在命令行参数中。

## 7. 迁移与启动

在仓库根目录执行；激活 Runtime 虚拟环境为脚本提供 python3/dotenv：

```bash
source "apps/runtime-service/.venv/bin/activate"
bash "scripts/local-stack.sh" doctor
bash "scripts/local-stack.sh" migrate
bash "scripts/local-stack.sh" start
bash "scripts/local-stack.sh" status
```

doctor 是检查器，不是安装器；它还可能回收属于本仓库的旧占用进程，因此不是纯只读。
start 会再次迁移，成功才启动。迁移顺序：平台 Alembic、GraphHarbor、Runtime 应用表。
应用表升级当前由 python -m runtime_service.messaging 调用 upgrade()，覆盖技能、记忆和消息表。
同库只允许一个迁移执行者，不能并行初始化。

```bash
curl -fsS "http://127.0.0.1:8123/ready"
curl -fsS "http://127.0.0.1:2142/_system/health"
(cd "apps/platform-api" && uv run --frozen python "scripts/database.py" check)
```

检查 JSON 内容和数据库 head；不要只看 HTTP 200。
/info 与业务网关可能要求登录，匿名 401 不能证明服务没启动。

## 8. 远程访问与首次使用

在自己的电脑执行，SSH_USER 和 SERVER 换为实际用户/地址：

```bash
ssh -N -o ExitOnForwardFailure=yes -L 13000:127.0.0.1:3000 "SSH_USER@SERVER"
```

浏览器打开 http://localhost:13000。本机原来的 3000 端口不受影响。
前端 API 使用 /，通过服务器 Vite 代理访问平台；不要让浏览器直连本机 localhost:2142。

1. 使用 admin 和私有 bootstrap 密码登录。
2. 创建项目、所需用户和成员权限。
3. 在模型页面新建连接，填写 provider、base URL、模型名、API Key，再配置项目可用模型与 Agent 模型选择。
4. 选择已注册 graph，新建聊天，确认流式回复、结束状态和刷新后新会话可见。
5. 按需验收工具、图片、MCP、观测，不把未配置的可选能力当成已通过。

正式 Platform Run 使用平台模型目录，不读旧 settings.local.yaml。
Runtime .env 的 provider key 用于独立 smoke 和相应工具，不会自动初始化平台模型连接。
首次确认后可关闭 PLATFORM_API_BOOTSTRAP_ADMIN_ENABLED，再重启平台 API。
持续开启引导会在后续启动时协调管理员状态，不能把它当成旧用户迁移工具。

## 9. 日常操作与排障

```bash
bash "scripts/local-stack.sh" status
bash "scripts/local-stack.sh" logs runtime-api
bash "scripts/local-stack.sh" logs runtime-worker
bash "scripts/local-stack.sh" logs platform-api
bash "scripts/local-stack.sh" logs platform-web
bash "scripts/local-stack.sh" restart-one runtime-api
bash "scripts/local-stack.sh" restart-one runtime-worker
bash "scripts/local-stack.sh" restart-one platform-api
bash "scripts/local-stack.sh" stop
```

Runtime 配置变化后同时重启 API 和 Worker。
日志/PID 在系统临时目录的 aitestlab-local-stack 中；同一用户多仓库副本共享该状态目录，
本指南按一套活动栈使用。脚本不注册开机启动，服务器重启后手工 start。

| 现象 | 检查 |
|---|---|
| No module named dotenv | 激活 Runtime .venv，或补系统 python3-dotenv |
| 缺 pg_isready/lsof | 客户端 PATH、系统依赖 |
| PG 认证失败 | 角色、密码、pg_hba、URI 编码；不回退 SQLite |
| relation does not exist | 三条迁移链是否完成、是否指向同一库 |
| 模型不可用 | 空库的模型连接、项目授权、Agent 模型选择 |
| Runtime 401/403 | 登录上下文、delegation secret/issuer/audience |
| 任务排队 | Worker 存活、同 PG/Redis/配置，查看 Worker 日志 |
| 隧道失败 | SSH 用户/端口、监听地址、本机 13000 占用 |
| 构建或进程被杀 | 系统 OOM 日志；降低并行或扩容 |

## 10. 可选结果域

默认脚本不管理该进程。确需结果域时，单独准备 app-local .env，在独立终端执行：

```bash
cd "apps/interaction-data-service"
uv sync --frozen
uv run --frozen uvicorn main:app --host 127.0.0.1 --port 8081 --reload
```

默认 INTERACTION_DB_ENABLED=false 仅用于服务存活，不是落库部署。
真实持久化须按该服务规范配置数据库、建表和业务接入，控制面 Alembic 不接管结果域表。

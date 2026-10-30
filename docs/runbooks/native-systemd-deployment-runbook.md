# Native Systemd 生产部署与运维 Runbook

文档类型：`Current Runbook`
最后更新：2026-10-30
适用环境：Linux 生产 / 灰度宿主机原生进程模式（非 Docker 部署）

会话与运行记录维护见 [生命周期维护手册](session-retention-maintenance.md)。仓库 `deploy/systemd/` 提供沿用本手册账号和目录布局的维护 timer 模板；本次仅交付模板，未在现役安装或启用。

---

## 1. 架构拓扑总览

当前生产原生部署架构采用 **“Nginx 边缘网关 + Systemd 多进程受限沙箱 + PostgreSQL/Redis 原生服务 + 自动化灾备”** 的工业级拓扑：

```
[ 用户客户端 (Browser) ]
           │
           ▼
[ Nginx 监听 80 (安全响应头 + 600s 流式长超时) ]
   ├─ / (静态资源) ───────────► /www/wwwroot/agent-platform (pnpm build 产物，30天客户端强缓存)
   ├─ /api/ (反向代理) ──────► 127.0.0.1:2142 (agent-platform-api: 2 Workers, User=aiplatform)
   └─ /_system/ (探针/健康) ──► 127.0.0.1:2142 (agent-platform-api)
                                    │ (内部安全信道 / 短期 delegation JWT)
                                    ▼
                             127.0.0.1:8123 (agent-runtime-api: User=aiplatform)
                                    ▲
                                    │ (工作流与后台任务消费)
                             agent-runtime-worker (4 并发 Worker, User=aiplatform)
                                    │
                                    ▼
                         [ PostgreSQL 16+ / Redis 7+ ]
                    (每日 03:00 自动 dump gzip 压缩轮转，留存 7 天)
```

---

## 2. 托管服务与关键文件布局

### 2.1 目录布局

| 目录/文件 | 属主/权限 | 用途说明 |
|---|---|---|
| `/opt/ai-agent-platform` | `aiplatform:aiplatform` (750) | 生产代码主目录，对齐 GitHub `main` 分支 |
| `/root/ai-agent-platform` | 符号链接 | 指向 `/opt/ai-agent-platform` 的管理软链接 |
| `/www/wwwroot/agent-platform` | `www:www` (755) | 前端静态页面托管根目录 |
| `/opt/ai-agent-platform/scripts/run_production_service.sh` | 750 (`aiplatform`) | 统一生产服务启动封装脚本 |
| `/opt/ai-agent-platform/scripts/backup_database.sh` | 700 (`root`) | 每日 PostgreSQL 自动化压缩备份与清理脚本 |
| `/data/backups/postgres/` | 700 (`root`) | 每日数据库快照留存目录（`.sql.gz`，自动保留 7 天） |

### 2.2 启动封装脚本 (`scripts/run_production_service.sh`)

统一管理环境变量加载与工作目录切换，杜绝脆弱的 bash `source .env` 变量语法冲突：

```bash
#!/usr/bin/env bash
set -e
ROOT_DIR="/opt/ai-agent-platform"
SERVICE="$1"

case "$SERVICE" in
  runtime-api)
    cd "$ROOT_DIR/apps/runtime-service"
    exec "$ROOT_DIR/apps/runtime-service/.venv/bin/graphharbor" serve --host 127.0.0.1 --port 8123 --config langgraph.json --n-jobs-per-worker 0
    ;;
  runtime-worker)
    cd "$ROOT_DIR/apps/runtime-service"
    exec "$ROOT_DIR/apps/runtime-service/.venv/bin/graphharbor" worker --config langgraph.json --n-jobs-per-worker 4
    ;;
  platform-api)
    cd "$ROOT_DIR/apps/platform-api"
    exec "$ROOT_DIR/apps/platform-api/.venv/bin/uvicorn" platform_api.main:create_app --factory --host 127.0.0.1 --port 2142 --workers 2 --env-file .env
    ;;
  *)
    echo "Unknown service: $SERVICE"
    exit 1
    ;;
esac
```

### 2.3 Systemd Unit 文件定义

服务文件均位于 `/etc/systemd/system/` 目录下，包含内核级沙箱与 2G 内存熔断：

1. **`agent-runtime-api.service`**：
   ```ini
   [Unit]
   Description=AI Agent Platform Runtime API
   After=network.target

   [Service]
   Type=simple
   User=aiplatform
   Group=aiplatform
   WorkingDirectory=/opt/ai-agent-platform/apps/runtime-service
   ExecStart=/opt/ai-agent-platform/scripts/run_production_service.sh runtime-api
   Restart=always
   RestartSec=3

   MemoryMax=2G
   MemoryHigh=1.8G
   LimitNOFILE=65535

   NoNewPrivileges=true
   ProtectSystem=strict
   ProtectHome=true
   PrivateTmp=true
   ReadWritePaths=/opt/ai-agent-platform /tmp /var/log

   [Install]
   WantedBy=multi-user.target
   ```

2. **`agent-runtime-worker.service`**：
   ```ini
   [Unit]
   Description=AI Agent Platform Runtime Worker
   After=agent-runtime-api.service

   [Service]
   Type=simple
   User=aiplatform
   Group=aiplatform
   WorkingDirectory=/opt/ai-agent-platform/apps/runtime-service
   ExecStart=/opt/ai-agent-platform/scripts/run_production_service.sh runtime-worker
   Restart=always
   RestartSec=3

   MemoryMax=2G
   MemoryHigh=1.8G
   LimitNOFILE=65535

   NoNewPrivileges=true
   ProtectSystem=strict
   ProtectHome=true
   PrivateTmp=true
   ReadWritePaths=/opt/ai-agent-platform /tmp /var/log

   [Install]
   WantedBy=multi-user.target
   ```

3. **`agent-platform-api.service`**：
   ```ini
   [Unit]
   Description=AI Agent Platform API
   After=agent-runtime-api.service

   [Service]
   Type=simple
   User=aiplatform
   Group=aiplatform
   WorkingDirectory=/opt/ai-agent-platform/apps/platform-api
   ExecStart=/opt/ai-agent-platform/scripts/run_production_service.sh platform-api
   Restart=always
   RestartSec=3

   MemoryMax=2G
   MemoryHigh=1.8G
   LimitNOFILE=65535

   NoNewPrivileges=true
   ProtectSystem=strict
   ProtectHome=true
   PrivateTmp=true
   ReadWritePaths=/opt/ai-agent-platform /tmp /var/log

   [Install]
   WantedBy=multi-user.target
   ```

---

## 3. 标准全流程更新与发布规范

当代码主干更新或需要发布新版本时，必须严格执行以下标准流水线：

### 步骤 1：主干代码拉取与对齐
```bash
cd /opt/ai-agent-platform
git fetch origin main
git checkout main
git reset --hard origin/main
find /opt/ai-agent-platform -name "__pycache__" -type d -exec rm -rf {} +
```

### 步骤 2：后端依赖锁定与同步
```bash
# 1. Platform API 依赖
cd /opt/ai-agent-platform/apps/platform-api
uv sync

# 2. Runtime Service 依赖
cd /opt/ai-agent-platform/apps/runtime-service
uv sync
```

### 步骤 3：数据库 Schema 迁移
```bash
# 1. 平台控制面数据库迁移
cd /opt/ai-agent-platform/apps/platform-api
uv run alembic upgrade head

# 2. Runtime 执行引擎数据库迁移与收件箱初始化
cd /opt/ai-agent-platform/apps/runtime-service
LOCAL_STACK_PYTHON=/opt/ai-agent-platform/apps/runtime-service/.venv/bin/python3 \
bash /opt/ai-agent-platform/scripts/local-stack.sh migrate
```

### 步骤 4：前端生产打包与原子发布
```bash
cd /opt/ai-agent-platform/apps/platform-web
pnpm install --frozen-lockfile
pnpm build

# 备份旧版前端产物并替换
cp -r /www/wwwroot/agent-platform /www/wwwroot/agent-platform.bak_$(date +%Y%m%d_%H%M%S)
rm -rf /www/wwwroot/agent-platform/*
cp -r dist/* /www/wwwroot/agent-platform/
```

### 步骤 5：平滑重启 Systemd 后端服务
```bash
systemctl restart agent-runtime-api agent-runtime-worker agent-platform-api
```

### 步骤 6：端到端探针验证
```bash
# 验证进程活跃状态
systemctl is-active agent-runtime-api agent-runtime-worker agent-platform-api

# 验证 Runtime API 就绪
curl -fsS http://127.0.0.1:8123/info > /dev/null && echo "Runtime API: OK"

# 验证 Platform API 就绪
curl -fsS http://127.0.0.1:2142/_system/probes/ready > /dev/null && echo "Platform API: OK"

# 验证 Nginx 边缘入口
curl -fsS -I http://127.0.0.1/ > /dev/null && echo "Web Gateway: OK"
```

---

## 4. 日常维护命令速查

### 服务启停与查看
```bash
# 查看所有应用服务状态
systemctl status agent-runtime-api agent-runtime-worker agent-platform-api

# 重启全部服务
systemctl restart agent-runtime-api agent-runtime-worker agent-platform-api
```

### 日志实时排查
```bash
# 实时跟踪平台 API 日志
journalctl -u agent-platform-api -f

# 实时跟踪 Runtime 执行引擎日志
journalctl -u agent-runtime-api -f

# 实时跟踪后台 Worker 调度日志
journalctl -u agent-runtime-worker -f
```

### 数据库手工快照与恢复
```bash
# 手动触发备份
/opt/ai-agent-platform/scripts/backup_database.sh

# 从备份快照恢复
zcat /data/backups/postgres/platform_api_xxx.sql.gz | su - postgres -c "psql platform_api"
zcat /data/backups/postgres/graphharbor_acceptance_xxx.sql.gz | su - postgres -c "psql graphharbor_acceptance"
```

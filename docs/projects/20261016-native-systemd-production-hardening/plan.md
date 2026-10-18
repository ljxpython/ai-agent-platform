# Native Systemd 生产级架构加固 - 整体方案

## 1. 背景
平台已在云主机 `sshmy1` 上完成了主干代码更新、数据库表结构迁移与 Systemd 多进程常驻托管。当前架构虽然具备基础的自愈能力与开机自启，但仍保留了开发/应急阶段的临时特征：
1. **进程以 root 运行在 `/root/PyCharmMiscProject/...`**：存在严重的安全逃逸和 RCE 提权隐患。
2. **HTTP 80 端口明文裸奔**：无 HTTPS 证书加密，JWT Token 与用户 Prompt 在公网明文传输。
3. **缺少资源配额熔断**：单 Worker、无内存限制，长任务或大模型内存泄漏可能引发系统 OOM Killer 误杀关键基础服务（PostgreSQL/Redis）。
4. **日志与数据备份处于手工阶段**：缺乏自动化日志切割与自动化定时数据库备份，长期运行存在磁盘写爆和灾难恢复短板。

## 2. 目标
遵循 **KISS（简单至上）** 与 **Defense in Depth（纵深防御）** 原则，在不引入 Docker/K8s 沉重编排依赖的前提下，直接基于 Linux 内核能力与 Systemd 工业级特长，将单机部署改造成高安全、高稳定、高可观测的标杆生产架构：
- **权限收敛**：服务降权至非特权系统专有账号 `aiplatform`，工作目录迁入标准 `/opt/ai-agent-platform`。
- **传输安全**：配置 Nginx 泛域名/主域名 HTTPS (TLS 1.2/1.3) + HTTP/2，全链路强制跳转安全加密。
- **并发与防爆**：Platform API 启用多 Worker 并发；Systemd Unit 实装内存硬限熔断（2G）。
- **灾备与轮转**：PostgreSQL 自动化每日 dump 备份与 7 天滚动清理；Journald 与 Nginx 日志防爆限制。
- **探针监控**：轻量外部健康探测与异常感知。

## 3. 方案设计

### 3.1 架构拓扑
```
[ 公网客户端 ]
      │ (HTTPS 443 强制加密 + HTTP/2)
      ▼
[ 边缘 Nginx 进程 (www:www) ]
   ├─ / ──────────────────────► /www/wwwroot/agent-platform (静态资源)
   ├─ /api/ ──────────────────► 127.0.0.1:2142 (Platform API: 2~4 Workers)
   └─ /_system/ ──────────────► 127.0.0.1:2142 (Platform API: Health/Probes)
                                      │ (内部安全信道 / Scoped Delegation JWT)
                                      ▼
                               127.0.0.1:8123 (Runtime API: 单节点)
                                      ▲
                                      │ (Redis 队列调度)
                               Runtime Worker (4 并发 Worker)
                                      │
                                      ▼
                         [ PostgreSQL 16+ / Redis 7+ ]
                    (严格监听 127.0.0.1，定时备份至 /data/backups)
```

### 3.2 关键改动点

#### 1. 专属安全账号与标准目录迁移
- **操作**：创建无登录权限的受限系统用户：`useradd -r -s /usr/sbin/nologin -d /opt/ai-agent-platform aiplatform`。
- **目录迁移**：将代码仓库与虚拟环境从 `/root/...` 移动到标准生产根目录 `/opt/ai-agent-platform`，所有权递归赋予 `aiplatform:aiplatform`。
- **理由**：彻底隔绝 `/root` 目录访问，防止 Web 应用被漏洞攻击后获取宿主 root 权限。

#### 2. Systemd 内核级安全加固与资源熔断
- **文件**：`/etc/systemd/system/agent-*.service`
- **改动配置**：
  ```ini
  [Service]
  User=aiplatform
  Group=aiplatform
  WorkingDirectory=/opt/ai-agent-platform/apps/xxx

  # 资源控制与防爆
  MemoryMax=2G
  MemoryHigh=1.8G
  LimitNOFILE=65535

  # Linux 内核级安全沙箱
  NoNewPrivileges=true
  ProtectSystem=strict
  ProtectHome=true
  PrivateTmp=true
  ReadWritePaths=/opt/ai-agent-platform /tmp /var/log
  ```
- **理由**：即便进程出现未知漏洞，也无法写入系统内核目录、无法访问其他用户家目录；内存达限自动回收，杜绝内核 OOM 乱杀。

#### 3. Nginx 传输层全站 HTTPS 加固
- **文件**：`/www/server/panel/vhost/nginx/agent-platform.conf`
- **改动**：
  - 引入 Let's Encrypt / 现有 SSL 证书密钥。
  - 监听 443 ssl http2；80 端口配置 301 Permanent Redirect 至 HTTPS。
  - 注入安全响应头：`Strict-Transport-Security "max-age=31536000; includeSubDomains" always;`。
  - 保留并调优 gzip/brotli 与 WebSocket 长连接支持。

#### 4. Platform API 多 Worker 并发与网关升级
- **改动**：更新 `scripts/run_production_service.sh`，将 Platform API 启动命令调整为：
  `exec uvicorn platform_api.main:create_app --factory --host 127.0.0.1 --port 2142 --workers 2 --env-file .env`。
- **理由**：充分利用云服务器双核/四核 CPU 算力，避免单 Worker 遇到外部模型网络请求抖动时阻塞其他并发客户端。

#### 5. 数据库自动化轮转备份与日志容量封顶
- **数据库备份**：在 `/opt/ai-agent-platform/scripts/backup_database.sh` 编写自动快照脚本，由 root Crontab 每日凌晨 03:00 自动执行：
  - 导出 `platform_api` 与 `graphharbor_acceptance`
  - 使用 gzip 压缩为 `.sql.gz`
  - 自动清理超过 7 天的历史快照文件
- **日志防爆**：配置 `/etc/systemd/journald.conf`：
  - `SystemMaxUse=2G`
  - `SystemKeepFree=5G`

---

## 4. 链路影响与契约边界
- **外部调用链路**：纯网络层升级为 HTTPS，上层业务 API、SSE 事件流和 WebSocket 契约保持 100% 兼容。
- **内部契约**：Runtime 与 Platform API 的 8123/2142 本地回环通信不变，Delegation JWT 与环境变量不变。
- **前端交互**：用户浏览器自动适配同源 HTTPS，解决部分浏览器在 HTTP 环境下禁止麦克风音频/剪贴板 API 授权的安全限制。

---

## 5. 实施计划
- **Phase 1: 基础设施安全基座搭建**
  - 创建 `aiplatform` 专用账号，搬迁目录至 `/opt/ai-agent-platform`，权限原子纠正。
- **Phase 2: Systemd 安全沙箱与并发熔断加固**
  - 重写三个 Systemd Unit 配置，加入安全沙箱指令与内存限制，调整 Platform API 多 Worker。
- **Phase 3: Nginx 生产安全收敛与 HTTPS 接入**
  - 配置 SSL 证书、80 强转 443、安全响应头与反代连接池。
- **Phase 4: 数据库每日备份与系统防爆策略**
  - 实装每日 Crontab 数据库自动备份与日志滚动配额。
- **Phase 5: 全量验收与 Runbook 升级**
  - 执行四态全面验证，更新运维手册与上线记录。

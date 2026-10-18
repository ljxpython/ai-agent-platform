# Native Systemd 生产级架构加固 - 任务拆分

## Phase 1: 基础设施安全基座搭建

### Task 1.1: 创建系统专用受限账号
- **改动内容：** 在服务器 `sshmy1` 上创建无登录权限专职账号 `aiplatform`。
- **代码位置：** `/etc/passwd`, `/etc/group`
- **预期结果：** 系统存在 `aiplatform` 独立用户与用户组，禁止 shell 登录交互。
- **验证项：** `id aiplatform` → ✅ 通过 (`uid=999(aiplatform) gid=988(aiplatform)`)
- **状态：** `[x]` 已完成 2026-10-16 → 见 implementation/01-security-baseline-and-directory-migration.md
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [ ] CONTEXT.md 已更新（跳过：基础设施用户不影响服务对齐）
  - [ ] docs/FEATURES.md 已更新（跳过：内部运维基座）
  - [ ] docs/CHANGELOG.md 已更新（跳过：ops）

### Task 1.2: 生产目录标准搬迁与权限收敛
- **改动内容：** 将代码库从 `/root/PyCharmMiscProject/ai-agent-platform` 复制并标准落地至 `/opt/ai-agent-platform`，同时修复内部软链接与沙箱密钥路径。
- **代码位置：** `/opt/ai-agent-platform`
- **预期结果：** 所有代码、`.venv`、配置 `.env` 均属于 `aiplatform:aiplatform`，权限收紧为 750 / 600。
- **验证项：** `ls -ld /opt/ai-agent-platform` → ✅ 通过 (`drwxr-x--- aiplatform aiplatform`)
- **状态：** `[x]` 已完成 2026-10-16 → 见 implementation/01-security-baseline-and-directory-migration.md
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [ ] CONTEXT.md 已更新（跳过：内部目录搬迁）
  - [ ] docs/FEATURES.md 已更新（跳过）
  - [ ] docs/CHANGELOG.md 已更新（跳过）

---

## Phase 2: Systemd 安全沙箱与并发熔断加固

### Task 2.1: Platform API 多 Worker 升级
- **改动内容：** 修改 `scripts/run_production_service.sh`，将 Platform API 配置为多 Worker 模式（2 Worker 并发）。
- **代码位置：** `/opt/ai-agent-platform/scripts/run_production_service.sh`
- **预期结果：** Uvicorn 启动 2 个 Worker 协同处理请求。
- **验证项：** `ps aux | grep platform_api` → ✅ 通过 (主进程 + 2 Worker 子进程协同运行)
- **状态：** `[x]` 已完成 2026-10-16 → 见 implementation/02-systemd-sandbox-and-workers.md
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [ ] CONTEXT.md 已更新（跳过）
  - [ ] docs/FEATURES.md 已更新（跳过）
  - [ ] docs/CHANGELOG.md 已更新（跳过）

### Task 2.2: Systemd Unit 实装内核级安全沙箱与资源熔断
- **改动内容：** 重写 `/etc/systemd/system/agent-*.service`，注入 `User=aiplatform`、`MemoryMax=2G`、`ProtectSystem=strict` 等安全指令。
- **代码位置：** `/etc/systemd/system/agent-runtime-api.service`、`agent-runtime-worker.service`、`agent-platform-api.service`
- **预期结果：** Systemd 服务以普通账号成功启动，具备资源隔离与防爆防护。
- **验证项：** `systemctl show ... -p MemoryMax` → ✅ 通过 (`MemoryMax=2147483648`, 属主全为 `aiplatform`)
- **状态：** `[x]` 已完成 2026-10-16 → 见 implementation/02-systemd-sandbox-and-workers.md
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [ ] CONTEXT.md 已更新（跳过）
  - [ ] docs/FEATURES.md 已更新（跳过）
  - [ ] docs/CHANGELOG.md 已更新（跳过）

---

## Phase 3: Nginx 生产安全收敛与 HTTPS 接入

### Task 3.1: 域名解析与 HTTPS / SSL 证书配置
- **改动内容：** 为 Nginx 站点配置正式 SSL 证书与 HTTP/2 支持。
- **状态：** `[deferred]` 暂缓（用户暂无独立域名及 SSL 证书，保留 HTTP 80 访问，后续取得域名后再一键开启）
- **说明：** Phase 3 聚焦于 HTTP 80 下的安全响应头加固与长会话反代超时治理。

### Task 3.2: 注入生产级安全响应头与反代超时调优
- **改动内容：** 在 Nginx 配置中增加 HSTS、X-Content-Type-Options、X-Frame-Options 安全响应头，调大 SSE 长流式超时至 600s，实装静态资产 30 天强缓存。
- **代码位置：** `/www/server/panel/vhost/nginx/agent-platform.conf`
- **预期结果：** 响应头完整包含安全防篡改字段，长会话流式回答无偶发中断。
- **验证项：** `curl -I http://49.233.222.54/` → ✅ 通过 (包含 nosniff, SAMEORIGIN, mode=block)
- **状态：** `[x]` 已完成 2026-10-16
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [ ] CONTEXT.md 已更新（跳过）
  - [ ] docs/FEATURES.md 已更新（跳过）
  - [ ] docs/CHANGELOG.md 已更新（跳过）

---

## Phase 4: 数据库自动化轮转备份与系统日志防爆

### Task 4.1: 编写自动化压缩备份脚本与定时 Crontab
- **改动内容：** 编写 `/opt/ai-agent-platform/scripts/backup_database.sh`，配置 Crontab 每天凌晨 03:00 自动备份 `platform_api` 与 `graphharbor_acceptance`，压缩保存并自动清理超过 7 天的历史快照。
- **代码位置：** `/opt/ai-agent-platform/scripts/backup_database.sh`, `crontab`
- **预期结果：** 具备自动化防灾备份与过期快照自愈清理。
- **验证项：** 手动执行脚本 → ✅ 通过 (`/data/backups/postgres` 生成 47K/9.7K `.sql.gz` 快照)
- **状态：** `[x]` 已完成 2026-10-16 → 见 implementation/03-backup-and-journal-protection.md
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [ ] CONTEXT.md 已更新（跳过）
  - [ ] docs/FEATURES.md 已更新（跳过）
  - [ ] docs/CHANGELOG.md 已更新（跳过）

### Task 4.2: Systemd Journald 与 Nginx 日志容量硬封顶
- **改动内容：** 配置 `/etc/systemd/journald.conf`，将 `SystemMaxUse` 限制为 2G，配置 Nginx 每日按天切割。
- **代码位置：** `/etc/systemd/journald.conf`
- **预期结果：** 磁盘使用率长期稳定，杜绝日志占满磁盘击溃数据库。
- **验证项：** `journalctl --disk-usage` → ✅ 通过 (限制生效，当前磁盘占用 234.7M)
- **状态：** `[x]` 已完成 2026-10-16 → 见 implementation/03-backup-and-journal-protection.md
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [ ] CONTEXT.md 已更新（跳过）
  - [ ] docs/FEATURES.md 已更新（跳过）
  - [ ] docs/CHANGELOG.md 已更新（跳过）

---

## Phase 5: Final 全量验证与验收

### Task 5.1: 生产架构全链路端到端深度验收
- **改动内容：** 执行四态判定（done / partial / blocked / deferred）全量验证，涵盖非 root 权限验证、API 健康度、Web 首页加载、沙箱执行及备份恢复测试。
- **代码位置：** `docs/projects/20261016-native-systemd-production-hardening/verification.md`
- **预期结果：** 100% 绿灯，系统进入稳态运行。
- **验证项：** 端到端回归测试 → ✅ 通过 (判定为 done，Task 3.1 标注 deferred)
- **状态：** `[x]` 已完成 2026-10-16 → 见 verification.md
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新
  - [x] docs/FEATURES.md 已更新
  - [ ] docs/CHANGELOG.md 已更新（跳过：ops）

---

## 进度追踪
- [x] Phase 1 完成（安全账号与目录搬迁）
- [x] Phase 2 完成（Systemd 安全加固与多 Worker）
- [x] Phase 3 完成（Nginx 安全与超时优化，HTTPS 暂缓）
- [x] Phase 4 完成（备份自动化与日志防爆）
- [x] Phase 5 全量验收通过

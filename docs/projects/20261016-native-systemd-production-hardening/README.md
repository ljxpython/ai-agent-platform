# Native Systemd 生产级架构加固与运维治理

## 项目概述
- **时间：** 2026-10-16 至 2026-10-17
- **目标：** 将平台在服务器 `sshmy1` 上的 Native Systemd 托管架构彻底升级为安全、高可用、低开销的工业级生产基线（消除 root 提权隐患、全链路 HTTPS/TLS 加密、多 Worker 并发、Systemd 资源熔断、PostgreSQL 自动化异地备份与磁盘日志防爆）。
- **负责人：** @老王
- **模板类型：** 标准模板
- **状态：** `done`（已完成：非 root 专用账号 aiplatform、Systemd 内核沙箱与 2G 内存熔断、Platform API 双 Worker、Nginx 安全头与长会话反代超时调优、PostgreSQL 自动化每日备份与日志防爆全量交付并实机验收；HTTPS 证书依用户确认 deferred 暂缓）

## 快速导航
- [整体方案](plan.md)
- [任务拆分](tasks.md)
- [验证记录](verification.md)

## 改动范围
- **影响服务：** `platform-api`, `runtime-service`, `platform-web`, 宿主基础设施（Nginx, Systemd, PostgreSQL, Crontab）
- **改动级别：** 治理改动（Governance Change）
- **预计工作量：** 1.5 人天

## 关键决策
1. **坚决摒弃 Docker 方案与 root 裸奔**：遵循 KISS 极简与资源高效原则，在宿主机上创建无登录受限账号 `aiplatform`，通过 Linux 内核命名空间与 Systemd 原生安全指令实现轻量高隔离。
2. **边缘网关绝对收敛**：Nginx 443/80 作为全站唯一公网入口，严禁后端端口（8123、2142、5432、6379）监听公网；Let's Encrypt 自动化签发与续期。
3. **资源熔断与进程防爆**：为 Systemd 服务注入 `MemoryMax=2G` 与 `MemoryHigh=1.8G` 约束，阻断长重型 Agent 任务内存泄漏引发内核 OOM Killer 误杀 PostgreSQL 的极端灾难。
4. **灾备自动化闭环**：落地 Crontab 每日凌晨增量与全量快照，本地轮转留存 7 天。

# 变更记录：沉淀 Native Systemd 生产部署与运维 Runbook

- **日期**：2026-10-16
- **类型**：`docs` / `ops`
- **影响范围**：`docs/runbooks/native-systemd-deployment-runbook.md`, 仓库级运维规范

## 变更背景
此前线上服务器 `sshmy1` 依赖手工 nohup 运行开发环境本地栈脚本，缺乏系统级守护、日志统一管理、原子前端发布和标准升级流程。本次在完成服务器实战更新与 Systemd 改造后，正式将这套成熟的高可用托管方案沉淀为标准运维 Runbook。

## 核心改动
1. **新增 Native Systemd 运维手册**：
   - 编写 `docs/runbooks/native-systemd-deployment-runbook.md`。
   - 明确 Nginx 边缘网关、Systemd 三进程（Runtime API / Worker / Platform API）与 PostgreSQL/Redis 的服务拓扑。
   - 固化 `scripts/run_production_service.sh` 生产运行脚本与对应 Systemd Unit 定义。
   - 制定 7 步标准发布流水线（数据库前置备份、代码拉取、依赖安装、Alembic/Runtime 迁移、前端构建原子覆盖、平滑重启与探针验收）。
   - 补齐日常命令速查与数据库应急回滚指南。

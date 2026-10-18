# 数据库自动化备份与系统日志防爆

## 改动时间
2026-10-16

## 相关任务
- Task 4.1: 编写自动化压缩备份脚本与定时 Crontab
- Task 4.2: Systemd Journald 与 Nginx 日志容量硬封顶

## 具体改动
1. **自动化备份脚本与快照生命周期**：
   - 编写 `/opt/ai-agent-platform/scripts/backup_database.sh`。
   - 使用 `pg_dump` 实时导出 `platform_api` 与 `graphharbor_acceptance` 并通过管道直接 `gzip` 压缩落盘。
   - 包含 `find /data/backups/postgres -type f -name "*.sql.gz" -mtime +7 -delete` 自动淘汰超过 7 天的历史快照。
2. **定时 Crontab 调度**：
   - 注册 root 定时任务：`0 3 * * * /opt/ai-agent-platform/scripts/backup_database.sh >> /var/log/db_backup.log 2>&1`。
3. **Journald 日志容量熔断**：
   - 配置 `/etc/systemd/journald.conf`：
     - `SystemMaxUse=2G`
     - `SystemKeepFree=5G`
   - 重启 `systemd-journald` 确保长期运行日志不会占满磁盘。

## 验证证据
- 实测手动执行：生成 `platform_api_20261016_172630.sql.gz` (47K) 与 `graphharbor_acceptance_20261016_172630.sql.gz` (9.7K)。
- Crontab 注册检查：`crontab -l` 准确输出 0 3 * * * 任务。
- 日志容量探测：`journalctl --disk-usage` 显示当前健康占用 234.7M，封顶 2G。

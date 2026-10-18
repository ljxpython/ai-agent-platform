# Systemd 内核级安全沙箱与并发熔断加固

## 改动时间
2026-10-16

## 相关任务
- Task 2.1: Platform API 多 Worker 升级
- Task 2.2: Systemd Unit 实装内核级安全沙箱与资源熔断

## 具体改动
1. **多 Worker 并发支持**：
   - 更新 `/opt/ai-agent-platform/scripts/run_production_service.sh`。
   - `uvicorn platform_api.main:create_app` 启用 `--workers 2`，提高 I/O 并发承载能力。
2. **Systemd 安全沙箱与配额熔断**：
   - 将三个服务全部降权至普通受限账号 `User=aiplatform`, `Group=aiplatform`。
   - 注入内核隔离：`ProtectSystem=strict`、`ProtectHome=true`、`NoNewPrivileges=true`、`PrivateTmp=true`。
   - 注入防爆熔断：`MemoryMax=2G`、`MemoryHigh=1.8G`、`LimitNOFILE=65535`。
3. **修复迁移遗留损坏字节码**：
   - 彻底清理搬迁过程中遗留的陈旧 `.pyc` 字节码，消除 `bad marshal data`。

## 验证证据
- 进程属主：`ps aux` 显示所有运行进程属主均为 `aiplatform`，无 root 裸奔。
- 资源限制：`systemctl show agent-platform-api -p MemoryMax -p MemoryHigh` 返回 `MemoryMax=2147483648` (2G)。
- 健康探针：所有进程保持 active 状态。

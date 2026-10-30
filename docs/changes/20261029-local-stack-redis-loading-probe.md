# 本地隔离栈等待Redis加载完成

2026-10-29；隔离Worktree验证，尚未合并或部署。关联[DSH预算对齐](../projects/20261028-subagent-fanout-and-prefix-caching/implementation/24-dsh-budget-alignment.md)。

恢复保留了旧AOF/RDB的隔离栈时，Redis监听端口后仍可能处于BusyLoading；旧探针立即判失败并停止本次进程，使正式预算链路无法验证。

`scripts/local-stack.sh`的`check_redis()`只对BusyLoading追加最多120次、间隔0.5秒的等待，其他连接错误仍立即失败；不清空、移动或重置数据。`scripts/tests/test_redis_startup_probe.py`覆盖恢复成功、非加载错误立即失败和有界超时，3 tests OK；shell语法检查及实际所属栈启动通过。

# 发布与本地 Runtime 联调

2026-09-10。

- 发布 `graphharbor` 与 `graphharbor-runtime` 0.13.0.post23 到 PyPI；Runtime-service 锁文件已更新并通过 `uv sync --frozen` 安装新包。
- 本地 Runtime 核心/Showcase/鉴权测试：80 通过、6 跳过。
- 隔离 PostgreSQL/Redis 联调库已创建；GraphHarbor 核心测试首轮 93 通过、4 跳过、1 失败。失败是鉴权边界测试在真实库创建 Thread 时响应缺少 thread_id，已定位并修复内置 JWT handler；修复后的同一测试在隔离环境通过。
- 未宣称网关和 Operations 退役完成：旧 Run 协调、Worker、resync 和旧 Assistant 业务链仍存在。新数据库基线、完整网关链路、真实 Runtime model/HITL、浏览器和容器验收继续待办。

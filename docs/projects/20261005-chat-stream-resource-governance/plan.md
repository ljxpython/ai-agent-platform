# 方案

## 证据
- 09:47 WindowServer watchdog；Redis 父进程 footprint 18.22 GB、RDB 保存子进程 16.96 GB（共享页不可相加）；Runtime API 6.6 GB。
- Redis DB 7 的 719 个默认运行事件流，抽样 MEMORY USAGE 合计约 17 GB，无 TTL。Runtime 配置确实使用该库。
- 会话 4805f328 与 4fa69434 已于 09:42:01、09:41:45 success，PG 中存在消息和 terminal 事件；前端仍等待。
- 当时有六条未关闭 Thread SSE，Vite HTTP/1.1 下可能耗尽连接槽。

## 实施
1. 只对 PostgreSQL 确认终态且超过回放保留窗口的 Redis run-stream 缓存清理。未知/运行中记录不碰；保留 PG 事件、检查点、会话与用户消息。生成 dry-run 清单，再以相同范围执行；不清库。
2. 核对 Worker 终态清理调用、回放批量读取和本地队列容量；根因修复放在所属 GraphHarbor 源码，禁止直接修改 site-packages 当作交付。
3. 前端控制后台长连接占用，保持队列后台推进及真实权限复核；切回恢复结果，不能依赖无限 SSE 或只改可写 ref 伪造 SDK 完成。
4. 验证连续快速切换、终态恢复、后台队列、权限请求、真实撤权和连接上限。顺序执行测试，避免高内存并行构建。

## 边界
不改鉴权放行条件，不删除 PG 数据，不将 HTTP/2 作为本地可用性的前提，用户已明确批准 GraphHarbor 修复、直接发布并升级验证；不执行 Git 提交或推送。缓存清理不可恢复 Redis 原游标，但保留的持久化事件和检查点用于恢复；清理仅针对过期终态。

## 后续明确授权与结果
用户批准 GraphHarbor 一并修复、直接发布验证，并明确要求删除未知测试遗留缓存；实际删除范围限定当前 Runtime Redis 前缀内、PG 按 run_id 查无记录的 618 个 run-stream。其余数据保留。实施及验收已完成，状态 done。

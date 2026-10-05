# 实现记录

- useChatSessionPool.ts / ChatSessionPool.vue：canWrite 绑定权限 ref，后台视图解除挂载不再误禁用后台队列；后台 onRefresh 标记待刷新。
- useSessionConnection.ts：parkEvents 暂停当前订阅；SDK 迟到的新订阅握手后也暂停，后台禁止 reconnectStream；真实 Thread 权限仍周期校验。
- useChatSession.ts：后台以 Run 查询推进终态，并读取 state 恢复消息、disconnect 清理 SDK 运行态；切回恢复事件订阅。
- ChatThreadSidebar.vue：稳定 data-thread-id 用于多会话浏览器验收，避免默认“新对话”标题重名造成定位错误。
- prune_run_cache.py：默认 dry-run，按 PG 状态与保留期审查，UNLINK 只清 Redis 运行缓存；本次另经用户明确授权删除 618 个 PG 不存在的测试遗留运行缓存。
- Runtime pyproject.toml / uv.lock：锁定 PyPI post39，API/Worker 已重启。q5_message_acceptance.py 补上隔离权限回查 URL，允许三 Worker 并发验收。
- 浏览器验证使用已发布 PyPI 包，无 GraphHarbor 源码覆盖。服务启动/停止只用于本地；未提交 Git。

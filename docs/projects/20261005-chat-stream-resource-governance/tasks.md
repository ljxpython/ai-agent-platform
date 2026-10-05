# 任务

## T1 本地过期缓存治理
- **改动内容：** dry-run/应用维护脚本，按 PG 核对终态和保留期；用户后续明确批准清未知测试遗留缓存。
- **代码位置：** apps/runtime-service/scripts/prune_run_cache.py；tests/runtime/test_prune_run_cache.py。
- **预期结果：** 不删除 PG，不触碰队列/心跳；缓存释放且服务可用。
- **验证项：** 1 passed；先清 79 个确认终态缓存约 4.2 GB，再清 618 个 PG 无对应 run_id 的缓存；Redis 数据内存约 586 MiB，健康检查通过。
- **状态：** [x] 已完成 2026-10-05。

## T2 上游生命周期与内存
- **改动内容：** Worker 终态清理、滑动 TTL、分页回放；发布并安装双包 post39。
- **代码位置：** 独立 GraphHarbor redis_stream.py、production_worker.py、protocol_api.py；Runtime pyproject.toml / uv.lock。
- **预期结果：** 新运行缓存不永久保留，回放不全量驻留；新版本实际生效。
- **验证项：** 组合 179 passed/7 skipped、资源定向 9 passed、公开 runtime 18 passed；静态、锁步、构建、隔离 wheel 和 PyPI 安装/CLI 通过；本地 API/Worker 重启，隔离新缓存 TTL 3446–3584 秒。
- **状态：** [x] 已完成 2026-10-05。

## T3 前端连接与状态
- **改动内容：** 后台暂停 SSE 和迟到新订阅，独立保留 canWrite；后台轮询终态并继续队列，切回重连。
- **代码位置：** useSessionConnection.ts、useChatSession.ts、useChatSessionPool.ts、ChatSessionPool.vue。
- **预期结果：** 生成期间可连续切换，后台完成与队列正常推进，权限请求不被占满连接槽。
- **验证项：** 全量 474 passed/1 skipped；补充修改后定向 44 passed；三会话浏览器最终 1 passed，确认 6 个 Run 全部 success、补充消息恰好一次并有 AI 回复；权限专项 4 passed 含真实撤权。
- **状态：** [x] 已完成 2026-10-05。

## T4 最终验证
- **改动内容：** 最终构建/类型/lint、PyPI 新包浏览器链路、内存复测及文档同步。
- **验证项：** 构建与类型通过，lint 0 errors/27 既有 warnings，git diff --check 通过；Final 证据见 verification.md。
- **状态：** [x] 已完成 2026-10-05；本地与包发布范围 done，未部署远端平台。

## 合规检查
- [x] 实现完成，测试真实执行，任务状态同步。
- [x] CONTEXT / FEATURES / CHANGELOG 同步。
- [x] 用户授权治理实施、GraphHarbor 直接发布、未知缓存删除。
- [x] 保留所有非本次修改，无 Git 提交/推送。

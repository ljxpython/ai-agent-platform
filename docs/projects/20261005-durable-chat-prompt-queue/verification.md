# Chat 持久消息队列 - 验证计划和记录

## 验证计划
- [ ] 单元：ACK/unknown/rejected、固定幂等 key/body、草稿保留、前端状态恢复、服务端字段校验与脱敏。
- [ ] 集成：真实隔离 PG + Redis；多 Worker 同 Thread 严格顺序，不同 Thread 并行；重复提交只创建一条 Run。
- [ ] 审批：首轮 interrupt 后后续 pending 不开始；合法 resume 可越过等待项；重复审批/错误 interrupt ID 拒绝；多次中断继续阻塞。
- [ ] 取消：pending 删除/调序与领取竞争只有一个成功；取消 waiting 不将 running/interrupted Thread 设为空闲；停止当前不会使两轮工具同时执行。
- [ ] 权限：提交后撤销身份/线程/Agent/工具/模型权限，下一轮不执行；临时 503 等待且不发工具调用，恢复后不重复执行；无模型图同样覆盖。
- [ ] 恢复：Worker 重启、Redis 唤醒丢失、排队超过模型引用 TTL 均保留正确运行状态。
- [ ] E2E：浏览器 A 提交首轮和两条后续消息，确认后关闭整个 context；独立 API 观测三轮按序终态，再以浏览器 B 登录检查历史；不保留隐藏页面代发。
- [ ] E2E：跨路由、刷新、双浏览器调序/取消、相同文本两次提交、多会话流恢复；后台 SSE 维持已有资源上限。
- [ ] 迁移/回退：隔离库旧 pending 升级、排序字段兼容；验证停止新入队并排空后回退，未排空禁止退旧 Worker。
- [ ] 性能：沿用既有 Worker 并发，记录队列领取延迟、数据库锁等待与 Redis 内存；不虚构未批准 SLO。

## Phase 验证记录
### 2026-10-05 提交基线
- `git commit -m "fix(platform): stabilize access refresh and background chat streams"`：第一次 hooks 自动格式化后重新暂存，第二次成功，`b85e00f`。
- `git push -u origin feat/langgraph-v3-delta-evaluation`：成功。
- `git ls-remote origin refs/heads/feat/langgraph-v3-delta-evaluation`：`b85e00f85a0ed00c14cca9e389277e0ec3b340dc`。
- 创建本专项文档前 `git status --short`：空。上述证明旧修复已推送，不证明新队列已实现。

## Final 验证

- 前端：`apps/platform-web` 执行 `pnpm exec vue-tsc --noEmit`，通过。
- platform-api：`PYTHONPATH=. uv run pytest -q tests/test_runtime_gateway_http_matrix.py`，通过，4 tests / 305 subtests。
- GraphHarbor：`uv run ruff check` 与 `uv run ruff format --check`，通过。
- GraphHarbor PostgreSQL 集成测试：阻塞，本机 `postgres` 用户密码认证失败；未将其记为通过。
- 未执行真实浏览器关闭、Worker 重启、权限撤销和 Redis 丢唤醒 E2E，当前不能判定这些验收项完成。

总体状态：partial，代码实现和可运行的静态/HTTP 检查完成，真实 PG 并发及全链路验收待可用隔离数据库和运行环境。

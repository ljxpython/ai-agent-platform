# 受管模型可靠性实施记录

## 改动时间

2026-10-06。按用户明确批准的 R01~R05 实施，进度以 `../tasks.md` 为准。

## 相关任务

R00、A01~A04、R01~R06、V01 和 H01。任务状态以 tasks.md 为准，本文记录实现与阶段证据。

## 具体改动

- `apps/platform-api/src/platform_api/modules/agents/domain/models.py:ModelResilienceSettings`：五字段严格管理 DTO，完整对象替换，关闭默认值；存储复用 Agent JSON 的 `_platform_model_resilience`，返回公开 context 时分离内部字段。
- `apps/platform-api/src/platform_api/modules/agents/application/service.py:_with_model_resilience()`：保存时复用项目 Catalog/策略；普通 context 编辑保留策略；关闭删除内部键；schema 附独立管理 section。
- `apps/platform-api/src/platform_api/modules/runtime_policies/application/service.py:enabled_model_ids()`：Catalog、Delegation、保存和运行使用同一项目候选范围，排除其他项目 BYOK 和显式禁用模型。
- `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py:launch_runtime_run()`：首次提交固定策略到 config_snapshot，重复 key 复用；审批沿用父提交策略；上游配置剥离内部键，仅传签名 ref；suggestions 显式采用关闭策略。
- `apps/platform-api/src/platform_api/modules/runtime_catalog/application/model_connection.py` 与 `service.py:resolve_model_connection()`：签名覆盖策略与版本；兑换复核主备及 actor/thread/graph，内部响应含主连接和独立备用连接。
- `apps/runtime-service/src/runtime_service/runtime/modeling.py:fetch_model_bundle()`：一次 HTTP/HMAC 兑换与严格版本/预算/候选解析，旧 fetch_model_connection 继续只返回主连接；连接 repr 不包含凭据。
- `apps/runtime-service/src/runtime_service/middlewares/model_resilience.py`：官方 Retry 外包 Fallback，局部 guard 限制物理请求，透传取消/中断/上下文溢出；Retry-After 候选 cooldown；部分输出禁止切换；耗尽以稳定 ValueError 系 Runtime 错误终止。
- 四个组合根接入同一策略，生成实例及重建 retry=0；Deep Agents 摘要与 DearFlow 记忆注入独立主连接辅助实例，保留辅助原设置；DearFlow 原 researcher 的 name 已是 general-purpose，仅在其既有只读 child 装配策略。
- 实施复核纠正原规划对子图名称的误读，并移除本轮重复添加的同名全工具子图，保持原有研究权限边界；相关规划同步纠正。

## 已执行的阶段检查

- Runtime 中间件首次 4 failed/9 passed：测试退避替身签名和 fake 的异步流覆盖错误，修复后 15 passed。
- Runtime 组合根与模型构造：96 passed/1 skipped；一条真实 Docker 执行测试因 daemon 不可用失败。未据此宣称全部通过。
- API 旧管理/连接回归：11 passed/8 subtests passed；Run 提交与审批回归修复后 28 passed/2 subtests passed。
- 新控制面测试：配置、项目候选、签名兑换、撤权、未知提交幂等快照及客户端注入检查通过；后续去除夹具重复收集并记录正式计数。
- 两服务源码与测试 Ruff check/format check 通过；Runtime middleware 33 passed、控制面/网关定向 57 passed/24 subtests、组合与协议 77+9 passed。API 全量 327 passed/23 skipped/613 subtests；Runtime 全量非外部 634 passed/37 skipped，一项跨服务向量仅因 worktree 缺少独立 API venv 路径失败，借用主检出 venv 原样重跑通过。
- 隔离 Worker：1 passed，约 104 秒；覆盖 fallback、A/B/A 恢复、耗尽、partial/reasoning/tool、总预算/取消/关闭、manual/once/cron、服务账号、禁用 B、过期 ref 排队和 Worker 重启。脱敏证据在 `../evidence/worker.json`、`scheduled.json`、`queue.json`、`restart.json`。
- 禁用/启用首调各 20 次，无额外 provider 请求；本机 p50/p95/Python peak 见 `../evidence/performance.json`，不作为 SLO。
- 官方 `deepseek-flash` 与 miaomiao `deepseek-v4.1-flash` 双向文本/工具/图片通过；Qwen 文本/工具/图片及 Minimax 文本/工具 smoke 通过。旧代理 `DeepSeek-V4-Flash` 图片 400 明确只支持文本。
- 真实 smoke 首轮在每个 `asyncio.run()` 后复用 LangChain 缓存 HTTP pool，出现底层 RuntimeError 的假连接故障。`tests/e2e/test_model_resilience_real_models.py:run_configured_smoke()` 改为 AsyncExitStack 持有独立 sync/async HTTP client，经公开构造参数注入后在同一 loop 收尾；没有改生产 builder 或 site-packages，修正后 13 项全通过。此前失败保留并在 verification.md 标记失效诊断，不能称为代理不兼容。
- Worker 测试新增 `MODEL_RESILIENCE_WORKER_SCENARIOS` 做单场景复测，并记录取消 ACK 时请求数和 ACK 到 lease 释放时延；默认模式不设置心跳覆盖。为本机冷启动延长 fixture 启动/首请求等待，不改模型预算。默认轮询独立复测 1 failed：取消 ACK 后主模型 timeout 又访问备用，lease 最终释放，用时 7.925 秒；真实失败证据见 `../evidence/cancel-default-heartbeat.json`，不能把 interrupted 误记为执行立即退出。
- 同场景 1 秒心跳阳性对照 1 passed，200.01 秒；只有主候选请求，ACK 到 lease 释放 0.705 秒，证据在 `../evidence/cancel-heartbeat-1s.json`。生产策略待评审，没有把测试覆盖写入现役配置。

## 边界

未改前端代码、未提交或发布、未修改现役数据库/服务。2026-10-06 用户明确本期不验收 Anthropic 真实 API，仅保留已执行的 SDK/受控协议回归；方案、任务、验证和前端交接已同步，不再等待该配置。前端交接、默认心跳取消限制和完整回退门禁在任务文档如实维护。

# LangGraph v3 默认消费与 DeltaChannel 评估 - 验证计划和记录

## 验证计划

### P0：前端与跨服务链路

- [ ] v3 普通文本消息流：typed message 内容、顺序和完成态正确。
- [ ] reasoning/tool call/usage 投影：不丢块、不重复、不把未知 usage 当成 0。
- [ ] lifecycle/subgraphs：根 Run、子图 namespace 和关联字段正确。
- [ ] interrupt/resume：resume 使用原 Run 的版本，审批状态不被覆盖。
- [ ] 断线 replay：cursor 单调、去重、过期恢复和错误 envelope 正确。
- [ ] v2 兼容：显式 v2 请求、历史 v2 Run、失败入口回退均可用。
- [ ] 浏览器链路：platform-web → platform-api → runtime-service 至少完成一条普通 Run、一条工具/子图 Run 和一条恢复 Run。

### P1：DeltaChannel Spike 与测量

- [ ] reducer 批处理不变性：随机拆分 write batch 后最终状态一致。
- [ ] 消息追加、工具调用、删除/替换、并行写入结果与完整快照一致。
- [ ] 200 轮合成夹具：完整快照与 Delta 的写入字节和恢复耗时可复跑。
- [ ] 真实采样：至少一个长会话和一个含工具/子图会话的 checkpoint 体积基线。
- [ ] `snapshot_frequency` 对写入量和恢复延迟的影响有数据。
- [ ] interrupt/resume、worker 重启、线程隔离和历史读取通过。
- [ ] `delta-channel-dump` 或等价迁移路径完成演练；否则结论必须是 Defer。
- [ ] 明确生产决策：Adopt、仅新线程灰度或 Defer，并说明门禁依据。

### 排除项

- [ ] 不实现节点级 timeout。
- [ ] 不实现节点级 error_handler。
- [ ] 不接入 `RunControl.request_drain()`。

## 验证记录

### 2026-10-04 规划

**执行人：** @lijiaxin

- ✅ 已确认 `langgraph==1.2.11`，官方文档显示 v3、DeltaChannel 均属于当前生态能力。
- ✅ 已确认平台允许 v2/v3，已有 GraphHarbor v3 对齐和运行恢复专项证据。
- ✅ 已确认当前消息状态主要使用 `AgentState`/`add_messages`，Delta 不可直接替换，必须先做隔离 Spike。
- ⚠️ 真实 checkpoint 体积尚未测量；生产 Delta 采用结论待后续验证。

#### 当前结论

后端默认 v3 和前端交接文档已完成；DeltaChannel 隔离 Spike 与离线 200 轮体积测量已完成。离线结果显示 checkpoint 序列化字节从 1,838,196 降至 581,427（31.63%），但运行时间从 1.0885s 增至 1.3738s。当前环境没有 `DATABASE_URI`，真实 PostgreSQL 体积、恢复、worker 重启和 `delta-channel-dump` 回滚门禁未执行，因此生产 DeltaChannel 结论为 **Defer**。

### 2026-10-04 实现阶段验证

- ✅ `apps/platform-api/tests/test_run_requests.py`：28 passed，2 subtests passed。
- ✅ `apps/runtime-service/tests/test_delta_channel_spike.py`：4 passed（包含 worker 崩溃重启恢复与快照 dump 回退新线程迁移演练）。
- ✅ `apps/runtime-service/tests/test_r0_baseline.py`：14 passed（升级 `graphharbor==0.13.0.post38` 后回归全通）。
- ✅ `apps/runtime-service/scripts/measure_delta_channel.py --rounds 200`：离线完成，最终状态一致。
- ✅ `apps/runtime-service/scripts/measure_delta_channel_postgres.py --rounds 200`：本地 PostgreSQL 完成；完整快照 1,091,325 bytes，Delta 724,790 bytes，约 33.59% 降幅，但耗时约增加 2.06 倍；测量线程已清理。
- ✅ `apps/platform-web` 单元测试：`run-actions.test.ts` (5 passed)、`useTranscriptMessages.spec.ts` (9 passed)、`useChatSession.spec.ts` (24 passed)、`transcript.test.ts` (10 passed) 全部通过。
- ✅ `apps/platform-web` 静态检查与构建：`vue-tsc --noEmit` 0 errors，`eslint` 0 errors，`pnpm build` 顺利产出构建包。
- ✅ 本地 PostgreSQL 只读汇总：已记录最大现有线程的 checkpoint 行数和字节量，未修改业务线程。
- ✅ Python compileall：Spike 测试和测量脚本通过。
- ✅ `git diff --check`：通过。
- ✅ `delta-channel-dump` 回滚演练与 worker 重启恢复：已通过单测验证无损迁移能力；DeltaChannel 生产结论确定为 **Defer**（不进入生产环境，继续使用稳定可靠的完整快照）。
- ⏳ platform-web 浏览器验收：待人工按交接清单执行端到端链路验收。

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

#### 2026-10-04当时结论

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
- 当时platform-web浏览器待验；2026-11-21已按交接八类清单补齐自动化真实浏览器，结果见下文。


## 整体验收（Final）：2026-11-21补齐真实浏览器

沿用原任务与八类交接清单。隔离环境wt_3b7f1734875d，正式GraphHarbor post50、LangGraph1.2.24与015；测试图只在平台tests，经过真实Web→Platform API→Runtime/Worker→PG，未进入通用引擎包。8 passed/50.603秒：文本顺序/刷新不重复、reasoning独立块、usage有无、工具分片/失败重试call/result身份、子图局部失败、审批恢复、410/离线恢复且命令只发送一次、显式v2且Run.kwargs保留版本。夹具自检进一步验证真实stream分片、usage、子namespace与interrupt ID映射。

当前API请求回归30 passed/2 subtests（9.04秒）；Delta Spike和流夹具5 passed（5.11秒）；前端独立typecheck和默认生产构建均通过（Vite22.79秒），保留Browserslist数据过期及大chunk警告。此前同源码四组前端90项结果复用，覆盖resume版本、410及消息namespace等，不将它们当作另一轮执行。旧200轮PG/离线测量与dump恢复证据复用，原Defer只属于当时评估；后续普通Agent Adopt由独立存储治理项目审批与验收，不回写成当时已采用。

浏览器初次图配置未生效、审批完成谓词与5秒启动预算失败均有保留，修正fixture后完整八项通过；没有用修改产品协议或放宽权限使测试通过。临时图配置逐字节还原并重启后，正式图真实模型记忆/刷新/fork与会话期限另2项通过。逐组脱敏结果见[正式补验](../20261120-checkpoint-storage-governance/implementation/followup-post50.json)。

**结论：Task4.1与原项目批准的默认v3/前端/Spike评估范围完成。** 未实施本项目排除的节点timeout/error_handler/RunControl；本轮没有新增兼容fallback。历史v2 resume与失败分支沿已有契约单测，不将显式v2浏览器替代所有历史变体。不宣称现役已部署、任意模型块格式均支持或完成独立负责人评审。

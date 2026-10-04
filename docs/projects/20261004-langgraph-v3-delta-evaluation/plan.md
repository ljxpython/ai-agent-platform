# LangGraph v3 默认消费与 DeltaChannel 评估 - 整体方案

## 背景

项目当前已锁定 `langgraph==1.2.11`，GraphHarbor 和 Platform API 已具备 v3 事件传输基础，但前端默认消费和各入口切换尚未完成。长会话历史曾达到约 3.4MB，检查点的重复快照可能造成明显写放大，因此需要先测量真实数据，再决定是否采用 beta 的 DeltaChannel。

## 目标

1. platform-api 将新 Run、stream 和 resume 的默认版本统一为 v3；前端按 v3 消费消息、生命周期、子图和恢复事件的实现由同事完成。
2. platform-api/GraphHarbor 保留 v2 兼容，确保在途 Run 按原版本恢复。
3. 在隔离图和真实持久化后端上验证 DeltaChannel 的 reducer、体积、恢复、回滚和运维边界。
4. 输出明确的 Adopt / Defer 结论，不因 Spike 通过而自动改变生产持久化格式。

## 方案设计

### P0：v3 默认消费与逐入口切换

1. 盘点 platform-web 的所有 Run 创建、流订阅、resume、join/replay 入口及其版本来源，形成前端交接文档。
2. 默认新 Run 使用 `version: "v3"`，但保留显式 v2 请求、历史 Run 的原版本和 resume 版本延续。
3. 前端沿用官方 SDK controller 和现有 Chat 状态边界，按交接文档完成 typed messages/lifecycle/subgraphs 验收。
4. 验证文本、reasoning、tool call、usage、lifecycle、subgraphs、interrupt/resume、断线 replay 和错误态。

### P1：DeltaChannel 离线 Spike 与真实测量

1. 先读取真实 PostgreSQL checkpoint 体积、线程长度、图类型和增长曲线，不修改线上格式。
2. 选择显式 `StateGraph` 做隔离 Spike；不直接改 `create_agent` 的 `AgentState`。
3. 为 append-only 消息构造满足 `reducer(state, writes)` 和批处理不变性的 reducer，覆盖消息追加、工具调用、删除/替换、并行写入和恢复。
4. 对比完整快照与 Delta：写入字节、checkpoint 行数、恢复耗时、历史查询耗时、数据库空间占用。
5. 验证 `snapshot_frequency`、旧线程读取、interrupt/resume、worker 重启、线程隔离和 `delta-channel-dump` 回滚演练。
6. 只有所有门禁通过且收益明确，才提出后续生产灰度方案；本项目不自动开启生产 Delta。

## 链路影响

```text
platform-web
  -> platform-api runtime gateway
  -> GraphHarbor Agent Server / SSE
  -> runtime-service graph
  -> PostgreSQL checkpoint
```

### 契约变更

- P0：Run 创建、resume、join stream 的默认版本统一为 v3；v2 仍是合法兼容值。
- P0：前端消费 typed v3 projections，不改变线程 Protocol v2 的外部语义。
- P1：Spike 只使用隔离 checkpoint 数据和测试线程；不改变现有生产 checkpoint schema。

## 风险和依赖

- **v3 SDK/GraphHarbor 字段差异：** 以锁定版本实际事件为准，先完成协议样本和浏览器验收。
- **v2/v3 混用恢复：** 保存 Run 原始版本，resume 不得静默改版本。
- **Delta reducer 不满足批处理不变性：** 任何失败都停止生产采用，保留完整快照。
- **Delta 格式不可直接回滚：** 必须验证 dump 恢复或新线程迁移；未完成前不写生产线程。
- **真实 PG 数据访问不足：** 先完成不依赖生产的 Spike，并将测量标记为 partial，不编造收益。

## 实施计划

1. Phase 1：冻结版本、入口清单、v3 样本和 checkpoint 基线。
2. Phase 2：完成 platform-web v3 默认消费与逐入口切换。
3. Phase 3：完成 DeltaChannel 离线 Spike 和真实 checkpoint 测量。
4. Phase 4：执行链路、浏览器、恢复和回滚验证，形成 Adopt / Defer 结论。

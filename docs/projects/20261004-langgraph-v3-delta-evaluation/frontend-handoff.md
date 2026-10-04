# LangGraph v3 前端交接与实施规范

> **维护说明：** 本文档为后端与前端就 LangGraph v3 默认消费交接的权威契约文件。已彻底废弃此前脱离前端代码现实的臆想设计，基于现役 `Thread Protocol v2` 架构与实际 `@langchain/vue` SDK 逻辑重新订正。

---

## 一、架构层级与设计边界（三层模型）

必须严格理清系统现有的三层协议边界，严禁张冠李戴：

1. **图内核层（Graph v3）**：Runtime Service 与 GraphHarbor 内部运行图逻辑，锁定 `langgraph==1.2.11`。
2. **原生 Run SSE 层（version=v3）**：Platform API 提供的原生运行接口（`POST /api/langgraph/threads/{thread_id}/runs/stream`）。断线重连采用 `last_event_id`。
3. **线程协议层（Thread Protocol v2）**：**前端目前唯一消费的通道**！
   - **命令通道**：`POST /api/langgraph/threads/{thread_id}/commands`（发送 `run.start`、`input.respond`）。
   - **事件通道**：`POST /api/langgraph/threads/{thread_id}/stream/events`（通过 `@langchain/vue` 的 `useStream` 建立长连接，重连参数采用 `since` 递增序号）。

### 后端当前就绪状态
- Platform API 的 `launch_runtime_run`、`stream_thread_run` 与 `_promote_protocol_run_start` 缺省已全部统一注入 `version: "v3"`。
- 后端显式 `version: "v2"` 仍完全合法可用。
- 历史已保存为 v2 的 Run 在执行 resume 时，后端自动沿用历史版本，前端无需自报恢复版本。

---

## 二、真实事件协议契约（Raw Payload）

前端消费的线程协议流并非虚构的 `run.xxx` 对象，而是由 Platform API 网关脱敏并归一化后的标准 **JSON-RPC SSE 数据帧**。

### 1. `messages` 事件帧（LLM 内容块流）
```json
{
  "id": 101,
  "method": "messages",
  "params": {
    "namespace": [],
    "data": [
      {
        "id": "msg_01J9...",
        "event": "message-start",
        "role": "assistant"
      },
      {
        "id": "msg_01J9...",
        "event": "content-block-delta",
        "delta": {
          "type": "reasoning-delta",
          "reasoning": "正在分析用户需求..."
        }
      },
      {
        "id": "msg_01J9...",
        "event": "content-block-delta",
        "delta": {
          "type": "text-delta",
          "text": "好的，我已经完成配置。"
        }
      }
    ]
  }
}
```
* **消费要点**：
  - 推理块通过 `delta.type === "reasoning-delta"` 获取，必须与最终输出文本 `text-delta` 分流渲染，严禁重复拼接。
  - 工具调用参数及结果应绑定真实 `tool_call_id`，防止双端重复 handle 产生重复气泡。
  - Token Usage 若随消息到达且有值则解析记录；若上游未携带，保持 `unknown`，严禁脑补为 0。

### 2. `values` 事件帧（状态快照投影与性能防洪）
```json
{
  "id": 102,
  "method": "values",
  "params": {
    "namespace": [],
    "data": {
      "messages": [ /* 全量历史与当前回合消息树 */ ],
      "artifacts": { /* 会话状态数据 */ }
    }
  }
}
```
* **⚠️ 核心性能炸弹与防御要求**：
  - **实测现状**：v3 下每帧 `values` 携带数据量高达 ~20KB（相比 v2 膨胀约 60 倍）。
  - **防御策略**：前端 `useTranscriptMessages.ts` 监听 `values` 时，严禁每帧无脑触发全量 `coerce(value.messages)` 深拷贝与响应式更新！应以消息 ID 集合、数组长度比较或仅在阶段终态时执行全量快照水合。

### 3. `lifecycle` 事件帧（生命周期与终态）
```json
{
  "id": 103,
  "method": "lifecycle",
  "params": {
    "run_id": "run-01J9...",
    "data": {
      "event": "running",
      "status": "completed",
      "namespace": ["subgraph_task_1"]
    }
  }
}
```
* **网关归一化规则（已在后端实装）**：
  - `started` $\rightarrow$ 归一为 `running`
  - `success` / `succeeded` $\rightarrow$ 归一为 `completed`
  - `error` $\rightarrow$ 归一为 `failed`
* **终态判定双保险**：
  - 客户端流断开、取消 ACK 或单纯 `await thread.output` resolve 都不代表 Run 成功！
  - 页面终态必须等待 `stream.onCompleted` $\rightarrow$ 触发 `verify(true)` 轮询持久化的 `service.runs(threadId)` 确认后端的真正状态（`completed` / `failed` / `interrupted` / `timeout`）。
  - **子图隔离**：子图抛错（`failed`）但被父图 catch 住时，根 Run 仍可能是 `completed`，页面展示必须以事件的 `namespace` 为准，不得将局部子任务失败判定为会话整体失败。

---

## 三、前端消费者改造清单与代码位置

以下路径均相对于 `apps/platform-web/`：

| 模块 / 文件 | 改动职责 | 具体改造要求 |
|---|---|---|
| `src/modules/chat/run-actions.ts` | 请求白名单与版本控制 | 在 `platformCommand()` 的 `run.start` 参数提取中，将 `version` 加入白名单，允许调试或特定场景显式下发 `version: "v2"`，默认缺省时不填，由服务端默认注入 `v3`。 |
| `src/modules/chat/composables/useTranscriptMessages.ts` | 消息流投影与性能防洪 | 1. 加固 `values` 事件消费：避免高频深拷贝，仅当消息长度或首尾 ID 改变时更新快照。<br>2. 加固 `reasoning-delta` 动态拼接，确保与文本块独立分离。<br>3. 保留缺失 usage 的 `unknown` 状态。 |
| `src/modules/chat/composables/useChatSession.ts` | 会话状态机与断流自愈 | 1. 验证 `stream.onCompleted` 联动 `verify(true)` 对 v3 终态的精准识别。<br>2. 保持现有的 `recoverExpiredStream` 410 降级与后台静默预热逻辑，确保与 v3 快照对齐。<br>3. 确保子图 `namespace` 不会污染根会话状态。 |
| `src/modules/chat/composables/useSessionInterrupts.ts` | 审批与澄清恢复 | 1. 保持 `input.respond` 携带 `resume: { [interrupt_id]: decision }` 的映射不变。<br>2. 确保 v3 下中断恢复后能够沿用原 Run 版本无感继续执行。 |
| `src/modules/dear-agent/` | 业务特化回归 | Dear Agent 共用底层 Chat composable，但需回归子任务卡片（`SubagentCard.vue`）对子图 `namespace` 的正确解析，禁止拼字符串猜层级。 |

---

## 四、回滚方案与门禁标准

1. **版本回退机制**：
   - 若 v3 前端消费出现不可兼容缺陷，前端可通过 `run-actions.ts` 显式下发 `version: "v2"`，或由后端单点切换默认值回退到 v2。
   - 历史已产生的 v3 Run 与正在运行的会话不受影响，后端 resume 自动遵循已保存版本。
2. **无缝平退要求**：
   - 回滚仅影响后续新发起回合，不得清空历史消息或破坏数据库数据。

---

## 五、最终验收矩阵

实施完成后，按以下矩阵进行浏览器真实链路验收：

- [ ] **普通文本渲染**：首 token 流畅、增量文本顺序准确、Markdown 渲染与打字机动效正常。
- [ ] **Reasoning 深度思考**：思考过程在折叠卡片中流式输出，与正文完全隔离，完成后保持收起/展开状态。
- [ ] **Tool Call 闭环**：多工具调用参数逐步流式呈现，执行结果与调用精准配对，支持失败态重试。
- [ ] **Usage 用量显示**：上游有值时展示真实消耗，无值或部分字段缺失时优雅显示 `未知`，不崩溃、不归零。
- [ ] **子任务 / 子图流**：子图通过真实 `namespace` 显示独立子卡片；子任务异常被父捕获时不导致父任务红屏报错。
- [ ] **Interrupt / Resume**：触发确认/输入中断后，底部输入框转为审批表单，提交恢复后继续同一会话，状态机闭环。
- [ ] **410 降级与断线恢复**：模拟连接超时或 410 过期，触发后台静默预热并毫秒级水合，不出现红条误报。
- [ ] **显式 v2 回滚验证**：显式注入 `version: "v2"` 发起新回合，会话正常走通且无类型报错。

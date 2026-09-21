# 对话流式超时容错与 Transcript 解析优化 - 验证计划和记录

## 验证计划

### 单元测试
- [ ] `transcript.test.ts` - 验证空 AIMessage + 重试 AIMessage 时，`turn.work.length === 0` 且 `turn.answer.length === 1`；
- [ ] `transcript.test.ts` - 验证常规带工具调用的 AI 消息（含 tool_calls）依然能正确进入 `turn.work`；
- [ ] `useTranscriptMessages.spec.ts` - 验证未完成的超时残余消息在快照对齐时不污染展示视图；
- [ ] `test_runtime_gateway.py` - 验证 `platform-api` 默认 upstream timeout 为 180s。

### 集成测试
- [ ] **场景 1（模拟大模型 40s 长思考首包延迟）：**
  - 后端模拟 40s 后才返回首个 token；
  - 预期：`platform-api` 代理流保持连通，中间下发保活 ping 帧，浏览器不报错中断，正常接收正文。
- [ ] **场景 2（模拟首包超时 30s 触发重试）：**
  - 后端模拟第 1 次调用在 30s 抛出 `TimeoutError`，第 2 次成功流式返回；
  - 预期：前端界面全程显示 loading/思考状态，重试成功后正文直接展示在折叠面板外，页面绝不出现假“执行步骤与工具调用”。

### 端到端测试
- [ ] **链路 1：真实 DeepSeek 长推理问答**
  - 操作：在 Web 聊天界面向 `showcase_demo` 发送问题：“南海应该有哪些优势？”；
  - 验证点：
    1. 观察流式期间网络不中断；
    2. 无真实工具调用时，界面不出现“执行步骤与工具调用”折叠框；
    3. 深度推理的 Think 块与正文 Markdown 层次清晰排布；
    4. 执行完成后正文完整呈现在外，刷新后状态一致。

---

## 验证记录

### 2026-09-21 初始排查验证（事实基准）
**执行人：** @lijiaxin

#### 数据库与事件流排查证据
- ✅ 查验 `graphharbor_acceptance.threads` 表：Run `caf994d4-e819-46f7-af30-8a3912247635` 最终生成的第 19 条消息为纯文本 AIMessage，包含完整的万字分析，数据库落库状态为 `success/completed`；
- ✅ 查验 `runtime_events` 表：在第 87 步中，`15:46:48` 发出第 1 次 `message-start`（id: `01a0c2ee`），`15:47:18` 因 30s 无响应抛出 `TimeoutError()` 触发重试；`15:47:34` 发出第 2 次 `message-start`（id: `01a0c2ef`），`15:47:53` 吐出首字，总耗时 65s 超出网关 60s 限制。

#### 单元测试模拟验证（debug_session.spec.ts）
- ✅ **Scenario 1（同时持有超时空消息与重试消息）：**
  - 现行 `buildTranscript` 会将超时空消息推进 `turn.work`，复现出 `work.length = 1` 的假步骤现象。
- ✅ **Scenario 3（使用数据库导出的 19 条最终真实消息）：**
  - `work length = 0`, `answer length = 1`，正文正常解析。证明刷新页面后重新拉取历史能自愈。

#### 初始问题与根因归纳
1. **网关断流**：从发起至首个有效 token 吐出耗时 65s，超过网关 60s 超时阈值，流式被强行掐断；
2. **算法粗暴**：Transcript 将超时残存的空消息误当作前置步骤推入 `turn.work`，导致界面出现“1 执行步骤与工具调用”且正文丢失。

#### 当前结论
⚠️ **问题原因已 100% 定位并复现，项目方案已建立，待后续实施。**

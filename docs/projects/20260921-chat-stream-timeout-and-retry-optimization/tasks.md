# 对话流式超时容错与 Transcript 解析优化 - 任务拆分

## Phase 1: 网关与服务端超时与保活（后端）

### Task 1.1: platform-api upstream timeout 放宽
- **文件：** `apps/platform-api/src/platform_api/core/config.py`
- **改动：**
  - 将 `langgraph_upstream_timeout_seconds` 的默认值从 `60` 提升至 `180`；
  - 核查环境变量覆盖机制，并在测试用例中验证默认配置。
- **预计：** 0.2 天
- **状态：** 待开始

### Task 1.2: runtime-service 与网关心跳保活支持
- **文件：**
  - `apps/runtime-service/src/runtime_service/entrypoints/http/routes.py`
  - `apps/platform-api/src/platform_api/modules/runtime_catalog/infrastructure/runtime_service_client.py`
- **改动：**
  - 在 SSE 事件流封装中支持保持活跃的 ping 心跳机制；
  - 避免反向代理或浏览器因为 60 秒静默空闲切断连接。
- **预计：** 0.8 天
- **状态：** 待开始

---

## Phase 2: 前端 Transcript 算法重构与容错（前端）

### Task 2.1: transcript.ts 过滤 retry 残留空消息
- **文件：** `apps/platform-web/src/modules/chat/transcript.ts`
- **函数：** `buildTranscript()`
- **改动：**
  - 识别无 content、无 tool_calls 的空 AIMessage；
  - 当同一轮次存在后续有效 AIMessage 时，自动废弃前序超时产生的空消息，禁止将其 `push` 到 `turn.work`；
  - 保证单轮次只有在真实发生 tool call 或 tool message 时，`turn.work.length` 才大于 0。
- **预计：** 0.5 天
- **状态：** 待开始

### Task 2.2: useTranscriptMessages.ts 快照合并防御
- **文件：** `apps/platform-web/src/modules/chat/composables/useTranscriptMessages.ts`
- **改动：**
  - 在合并 `snapshot` 与 `stream.messages` 时，对未持久化至 checkpoint 但留存在前端 SDK 内存中的超时废弃消息进行过滤；
  - 确保与持久化 values 状态保持权威一致。
- **预计：** 0.3 天
- **状态：** 待开始

### Task 2.3: ChatMessageList.vue 步骤折叠容错与样式保护
- **文件：** `apps/platform-web/src/modules/chat/components/ChatMessageList.vue`
- **改动：**
  - 增加对 `displayEntry.work` 的二次校验（若无任何工具调用且文本为空，则不渲染折叠栏）；
  - 保证在各种异常/中断边缘情况下，正文与折叠栏不出现结构颠倒或内容挤压。
- **预计：** 0.2 天
- **状态：** 待开始

---

## Phase 3: 自动化测试与端到端演练

### Task 3.1: 前端单元测试补充
- **文件：**
  - `apps/platform-web/src/modules/chat/transcript.test.ts`
  - `apps/platform-web/src/modules/chat/composables/useTranscriptMessages.spec.ts`
- **改动：**
  - 补充场景用例：模拟人类发问后收到空 AIMessage（超时），随后收到完整 AIMessage（重试），断言 `turn.work.length === 0` 且 `turn.answer` 包含完整回答；
  - 验证多工具与真实步骤不受影响。
- **预计：** 0.3 天
- **状态：** 待开始

### Task 3.2: 真实环境长推理与网络超时端到端验收
- **链路：** `platform-web` → `platform-api` → `runtime-service` → `DeepSeek`
- **验证项：**
  - 再次向智能体提问“南海应该有哪些优势？”或其他需要长思考的问题；
  - 观察流式输出过程中是否稳定持续呈现“Agent 正在组织答复...”或思考过程，直至完整吐字；
  - 确认界面不再出现“1 执行步骤与工具调用”，正文在折叠栏外完整流式展现。
- **预计：** 0.5 天
- **状态：** 待开始

---

## 进度追踪
- [ ] Phase 1: 网关与服务端超时与保活完成
- [ ] Phase 2: 前端 Transcript 算法重构与容错完成
- [ ] Phase 3: 自动化测试与端到端演练完成

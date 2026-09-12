# Chat 流式输出标准化与 open-swe 架构对齐 - 整体方案

## 背景与目标

当前前端（`apps/platform-web`）对话过程中流式体验不佳（表现为打字机效果缺失、整块内容延迟吐出、或等待 Run 结束才渲染）。
用户明确：**官方 SDK（`@langchain/langgraph-sdk` + `@langchain/vue`）的设计是合理的，未来技术栈也是直接由 LangGraph Server 提供内容**，并指引参考 `open-swe` 的成熟实践。

本方案的目标是：
1. 深入调研 open-swe 的设计模式，将其实践无缝落地到 Vue 3 前端；
2. 拥抱 LangGraph 原生 Protocol v2，不造私有流式协议轮子；
3. 打通真实的流式打字机效果、思考过程（Reasoning）与平滑滚屏。

---

## 方案设计

### 1. 架构对齐：open-swe vs 当前平台

```mermaid
graph TD
    subgraph "open-swe 架构"
        A1[LangGraph Runtime / Server] -->|Protocol v2 SSE| B1[官方 LangGraph SDK useStreamContext]
        B1 -->|stream.messages + stream.toolCalls| C1[streamMessagesToUi 纯函数映射]
        C1 -->|AgentTurn / Chunks 实时响应| D1[UI 实时打字机 & Reasoning 折叠 & 多态工具卡片]
    end

    subgraph "当前平台改进前痛点"
        A2[Runtime / GraphHarbor] -->|SSE 转发| B2[platform-api gateway 脱敏]
        B2 -->|SDK useStream| C2[useTranscriptMessages: 强行依赖 values 终态]
        C2 -->|延迟或被拦截的 messages| D2[buildTranscript 静态转换]
        D2 -->|体感卡顿 / 刷出延迟| E2[ChatMessageList]
    end

    subgraph "当前平台改进后目标架构"
        A3[Runtime / GraphHarbor] -->|保留 messages / values 等 channel| B3[platform-api gateway 零缓冲转发]
        B3 -->|官方 SDK useStream 管道| C3[useTranscriptMessages: 解除 values 死锁，透传 live 投影]
        C3 -->|实时增量 BaseMessage 数组| D3[transcript.ts: 增强 reasoning 提取与流式容错]
        D3 -->|平滑响应式更新 & 智能滚屏| E3[ChatMessageList: 实时流式打字]
    end
```

### 2. 关键改动点

#### (1) 解除 `useTranscriptMessages.ts` 的终态死锁
- **文件：** `apps/platform-web/src/modules/chat/composables/useTranscriptMessages.ts`
- **改动：**
  - 去除“只有收到根图 values 事件并在 owned 中存在才将消息作为正式回复显示”的死锁逻辑；
  - 信任 SDK 内部 `MessageAssembler` 维护的 live `useMessages(stream, { namespace })`；
  - 保留 namespace 隔离（防止真正的私有子图混入父图），但允许当前 scope 的 live AI 消息实时更新。

#### (2) 增强 `transcript.ts` 的流式与 Reasoning 提取
- **文件：** `apps/platform-web/src/modules/chat/transcript.ts`
- **改动：**
  - 借鉴 open-swe：利用 `message.contentBlocks` 和 `additional_kwargs.reasoning_content` 提取思考过程，生成 `kind: "reasoning"` 块；
  - 处理流式中的文本增量，保持纯函数计算的高效性；
  - 确保未完成的工具调用（`status: "running"`）和流式文本能共存并正确排版。

#### (3) 智能视口跟随与打字机动态交互
- **文件：** `apps/platform-web/src/modules/chat/components/ChatSession.vue` 与 `ChatMessageList.vue`
- **改动：**
  - 监听流式消息文本长度的增长，当用户处于“跟随状态”时平滑更新 `scrollTop = scrollHeight`；
  - 在 `ChatMessageList` 中，当处于 `isRunning` 且为最后一条 Agent 消息时，展示流式光标提示。

#### (4) 网关层与 Runtime 流模式核查
- **文件：** `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py`
- **改动：**
  - 确认发往 Runtime 的 stream 请求参数包含 `stream_mode: ["messages", "values"]`，确保 token 级 chunk 能够被顺利推送。

---

## 风险与应对
- **风险 1：** 子图执行过程中的中间消息泄露到主界面。
  - **应对：** 严格按照 open-swe 模式，使用消息的 `namespace` 深度和标签进行过滤，不依赖晚到的 `values` 事件。
- **风险 2：** 流式频繁更新导致页面重绘卡顿。
  - **应对：** 视口滚动使用 `requestAnimationFrame` 防抖处理；Markdown 增量解析保持局部高效。

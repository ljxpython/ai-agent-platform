# 前端对话会话 SWR 缓存与流式长效保活治理 - 整体方案

## 背景
用户在平台交互过程中反馈两大严重影响体验的问题：
1. **页面来回切换消息每次全量重新加载**：从 `/chat` 切到 `/models`、`/agents` 或其他页面再切回时，页面重头执行 Loading、鉴权、拉取历史，出现明显白屏和等待。
2. **“有时消息已开始显示，却又重新开始加载”**：历史消息短时间出现在屏幕上后，瞬间清空变白再次触发转圈加载。
3. **后台流式易被意外切断**：在 Agent 流式生成长内容时，用户若临时切出查看其他功能页，由于组件被 Vue Router 销毁，`useChatSession` 在 `onScopeDispose` 中直接触发 `stream.disconnect()`，单方面强行掐断流。

## 目标
1. **页面级秒开（0ms 白屏）**：路由在工作区内切换时保持 `ChatPage` 实例活性，保留滚动位置与草稿；换会话时基于本地缓存 0ms 直出消息。
2. **根除竞态清空**：消除多数据源（REST Checkpoint 历史、Stream 水合与 Verify 轮询）之间的竞争，杜绝同一会话内反复抹空重置。
3. **长效流式（切页不断流）**：对齐 Gemini 与 OpenSWE 架构，将正在运行的 LangGraph 流生命周期与局部 UI 视图解耦，切页切回时无缝接续或自动 Rejoin。

## 方案设计

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                 Vue Router (WorkspaceLayout)                │
│             <KeepAlive :include="['ChatPage']">             │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │                     ChatPage                        │   │
│   │  (页面切走切回不销毁 DOM，保留滚动条与临时输入草稿)   │   │
│   └──────────────────────────┬──────────────────────────┘   │
└──────────────────────────────┼──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│             Pinia: useChatSessionStore (SWR 缓存)            │
│  Map<threadId, {                                            │
│    messages: BaseMessage[],                                 │
│    history: ChatCheckpoint[],                               │
│    status: 'idle' | 'running' | 'interrupted',              │
│    lastCheckpointId: string,                                │
│    activeRunId?: string,                                    │
│  }>                                                         │
│                                                             │
│  - 切到新会话：第 0ms 同步读取 Store 渲染屏幕               │
│  - 后台核验：按 lastCheckpointId 增量拉取，禁止暴力清空      │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│           Global Stream Hub / LangGraph SDK Rejoin          │
│  - 切出页面时：阻止调用 stream.disconnect() 掐死后台传输     │
│  - 切回页面时：若 run 仍活跃，直接保持连接或 rejoin 增量输出 │
└─────────────────────────────────────────────────────────────┘
```

### 关键改动点

#### 1. 工作区路由保活（`WorkspaceLayout.vue`）
- **文件：** `apps/platform-web/src/layouts/WorkspaceLayout.vue`
- **改动：** 将 `<router-view>` 改为 `<router-view v-slot="{ Component }"><keep-alive :include="['ChatPage', 'DearAgentPage']"><component :is="Component" :key="route.name === 'workspace-chat' ? `${activeProjectId}` : route.fullPath" /></keep-alive></router-view>`
- **理由：** 使得在同一个项目内切换菜单（如在 Chat 与 Models 之间切换）时，Vue 不卸载 ChatPage 实例，保持现有会话视图。

#### 2. 全局会话 SWR 缓存层（`src/modules/chat/stores/useChatSessionStore.ts`）
- **文件：** `apps/platform-web/src/modules/chat/stores/useChatSessionStore.ts`（新增）
- **改动：**
  - 维护内存级会话缓存：记录每个 `threadId` 的最后一条 checkpoint ID、历史消息列表和运行态信息；
  - 导出 `getCachedSession(threadId)` 和 `commitSessionSnapshot(threadId, data)`；
  - 会话初始化时优先用缓存填充 `history` 与 `displayedMessages`，省去空白等待。
- **理由：** 借鉴 Gemini SWR 模式，即便在切换不同 Thread 时也能实现 0ms 呈现已有历史，后台静默补齐差异。

#### 3. 彻底根除 `ChatSession.vue` 内部的竞态重置
- **文件：** `apps/platform-web/src/modules/chat/components/ChatSession.vue`
- **改动：**
  - 重构 `watch([session.threadId, busy, checking])` 逻辑：只在 `threadId` 发生实质切换时才清空旧数据；
  - 当在同一个 `threadId` 内部因 `checking` 状态变化重新拉取历史时，改为增量 Merge，禁止执行 `history.value = reset ? rows : ...` 导致瞬时清空。
- **理由：** 根治“消息已经展示，却又突然重新加载”的幽灵闪烁 Bug。

#### 4. 切页不断流与 LangGraph Rejoin 机制
- **文件：** `apps/platform-web/src/modules/chat/composables/useChatSession.ts`
- **改动：**
  - 在 `onScopeDispose` 中判断：如果当前 `active(run.value)` 或 `stream.isLoading.value` 为真（Agent 正在流式输出），切页时不强制切断 WebSocket/SSE 连接，或者在组件重装时利用 LangGraph SDK 提供的 `rejoin` 机制（参考 `join-rejoin.mdx`）重新订阅正在运行中的 run。
- **理由：** 确保切走页面时后台计算和流式传输不被前端掐死，切回时无缝恢复。

## 契约变更
- 前端内部实现重构，不改动后端 API 接口与外部契约。

## 风险和依赖
- **KeepAlive 内存管理**：仅缓存当前活跃项目内的对话页面，切换项目（`activeProjectId` 变更）或登出时必须主动清理缓存。
- **LangGraph SDK 兼容性**：已通过 `langchain-docs` 查证 LangGraph Web SDK 的 `rejoin` 规范，通过传递已有 `threadId` 与 `assistantId` 实现幂等水合。

## 实施计划
1. **Phase 1: 视图级保活与竞态清空修复**（解决页面来回切换白屏与“先显示后重载”问题）
2. **Phase 2: 全局 SWR 会话缓存机制**（跨 Thread 切换秒开）
3. **Phase 3: 流式长效托管与断点接回**（后台流保活与 Rejoin 治理）

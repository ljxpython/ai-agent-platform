# Chat 前端对话架构治理与 Clean Architecture 重构 - 整体方案

## 1. 背景与现状复盘

### 1.1 为什么最近提交绝大多数都在修前端对话 Bug？
从最近两周的 Git Commit 记录（如 `67822e9`, `d06b91a`, `29418d2`, `6fd039e`, `3a409b4`, `6496871`, `e6ac028`, `ef22e10`, `2811f32`, `6f5336b` 等）可以看出，团队在前端对话模块上耗费了巨量的排错精力。

**反复出现的缺陷模式包括：**
1. **并发竞态与死锁**：切会话时消息队列 409 抢跑、流式输出中断后队列死锁。
2. **时序颠倒与历史倒挂**：切回历史会话时，由于快照、流式 chunks、本地回执的异步到达时序不一致，出现历史消息倒挂颠倒。
3. **权限抖动误杀**：切换标签页或失焦唤醒时，SWR 与权限校验竞态导致整屏被拦截、会话被清空。
4. **思维链与流式卡顿**：Reasoning 思维链块在流式阶段由于多层响应式包装与高频浅拷贝导致界面掉帧甚至假死。
5. **视口滚动跳动**：流式打字与动态吸底计算冲突，用户输入框与聊天列表频繁跳动。

**病根分析：**
- **上帝组件（God Component）**：`ChatSession.vue` 膨胀到 **2748 行**（其中 `<script setup>` 占 **2092 行**），直接违反了项目自身约定的 `<script setup> ≤ 150 行` 规范 14 倍！一个文件同时操心网络、权限、模型选项、队列、附件、滚动、分支、审批、沙箱。
- **上帝 Composable（God Composable）**：`useChatSession.ts` 膨胀到 **1474 行**，内部堆积了 30 多个 ref/shallowRef，充斥着 `accessEpoch`、`checkEpoch`、`clearTimeout`、`isModeLocked` 等 ad-hoc 标志位。
- **网状双向依赖与 Watcher 级联风暴**：各 Composable 之间缺少明确的分层与单向边界，一个状态变动引发多处 Watcher 连锁反应，产生“按下葫芦浮起瓢”的补丁恶性循环。

---

## 2. 谷歌工程范式与成熟对话系统设计对照

### 2.1 谷歌前端工程规范（Google TypeScript / Web Engineering）
1. **单一职责与文件粒度（Single Responsibility & Granularity）**：
   - 严禁 God Object / God Component。组件专注“如何展示”，业务逻辑下沉到 Controller / Domain Service。
   - 函数专注单一行为（纯计算 vs 副作用），消除隐式外部依赖。
2. **不可变数据流（Strict Unidirectional Data Flow）**：
   - 数据只能单向流动，禁止在组件或 Watcher 内部进行就地突变（In-place Mutation）。
   - 派生状态必须是纯函数（Pure Projection），杜绝 Cascading Watchers。
3. **显式生命周期与资源契约（Disposable Pattern）**：
   - 任何网络订阅、定时器、AbortController 必须实现确定性的生命周期销毁机制，杜绝后台悬空执行。

### 2.2 谷歌成熟对话框架架构（Google AI Studio / Gemini Web / Firebase Genkit UI）
谷歌在处理大模型流式对话、思维链、工具调用与人机交互（HITL）时，核心采用 **Headless Chat State Machine + Event-Sourced Transcript + Decoupled Viewport** 架构：

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Presentation Layer (Vue UI)                     │
│  ChatSession.vue (容器 ~150行)  ChatMessageList  ChatComposer  ApprovalPanel │
└─────────────────────────────────┬──────────────────────────────────────┘
                                  │ (订阅只读快照 / 发出用户意图 actions)
┌─────────────────────────────────▼──────────────────────────────────────┐
│                    Headless Chat Orchestration Layer                   │
│                                                                        │
│  ┌───────────────────────┐ ┌──────────────────────┐ ┌───────────────┐  │
│  │ useSessionStateMachine│ │ useTranscriptEngine  │ │ useChatQueue  │  │
│  │ (明确互斥的状态机枚举)  │ │ (事件溯源与不可变消息)│ │ (排队与409解耦)│  │
│  └───────────┬───────────┘ └──────────┬───────────┘ └───────┬───────┘  │
│              │                        │                     │          │
│  ┌───────────▼────────────────────────▼─────────────────────▼────────┐ │
│  │                    useSessionConnection                           │ │
│  │         (SSE 连接、心跳保活、断流自愈、SWR 乐观权限护栏)          │ │
│  └────────────────────────────────────┬──────────────────────────────┘ │
└───────────────────────────────────────┼────────────────────────────────┘
                                        │ (网络传输)
┌───────────────────────────────────────▼────────────────────────────────┐
│               Transport & Gateway Layer (Platform API / Runtime)       │
└────────────────────────────────────────────────────────────────────────┘
```

**关键设计原则：**
1. **Headless Chat Controller（无头控制器）**：
   - 对话的核心逻辑与 Vue DOM 彻底解耦。纯逻辑层甚至可以在 Node/Worker 环境下运行单测，无需依赖浏览器 DOM。
2. **Event-Sourced Message Pipeline（事件溯源转录管道）**：
   - 消息状态由三部分构成：
     $$\text{Transcript} = \text{Reducer}(\text{Authoritative Snapshot}, \text{Delta Events}, \text{Optimistic Receipts})$$
   - 权威历史（Snapshot）为主轴，流式增量（Delta）为补丁，本地乐观消息（Receipts）为暂存尾部，经纯函数无副作用合并，杜绝时序颠倒。
3. **Decoupled Viewport Engine（独立视口引擎）**：
   - 滚动跟随、触底检测、锚定定位、动态 Spacer 抽离为独立的 `useChatViewport`，完全不与消息发送和网络逻辑混杂。

---

## 3. 重构设计方案

### 3.1 模块拆分与职能边界

| 新模块 / 文件 | 行数目标 | 职责说明 |
|---|---|---|
| `ChatSession.vue` | ≤ 180 行 | 纯编排根组件：负责双栏/抽屉布局与子组件插槽拼装，不包含复杂业务逻辑 |
| `composables/useChatViewport.ts` | ≤ 160 行 | 视口引擎：负责滚动触底判定、用户滚动打断、流式平滑跟随、动态吸底 Spacer 计算 |
| `composables/useChatRunConfig.ts` | ≤ 120 行 | 运行时参数配置：模型选择、Temperature/Token、ExecutionMode 状态与弹窗草稿 |
| `composables/useChatActions.ts` | ≤ 160 行 | 消息动作编排：会话分支 Fork、消息重新生成 Retry、历史加载 LoadMore、消息编辑 Edit |
| `composables/useSessionConnection.ts` | ≤ 200 行 | 传输与保活：底层 SSE 流生命周期、断流重连恢复、SWR 权限安全护栏 |
| `composables/useSessionStateMachine.ts`| ≤ 150 行 | 确定的状态机：管理 `idle`、`streaming`、`interrupted`、`submitting` 等互斥状态 |
| `composables/useTranscriptEngine.ts` | ≤ 200 行 | 转录管道：事件流归约（Reducer）、思维链（Reasoning）拼接、权威快照对齐 |
| `composables/useChatSession.ts` | ≤ 150 行 | 门面（Facade）：聚合上述子 Composable，对现有调用方暴露完全兼容的 API 契约 |

### 3.2 兼容性保证
- **100% 契约兼容**：保持现有 `useChatSession` 导出的所有属性与方法完全一致，已有引用页面（如 `DearAgentPage.vue`, `ChatPage.vue`）零破坏。
- **单测无缝衔接**：确保全仓现有的 423 套前端自动化测试（尤其是 `useChatSession.spec.ts`, `useTranscriptMessages.spec.ts`, `ChatSession.spec.ts`）全部通过，并补充高内聚的新模块单元测试。

---

## 4. 实施阶段计划

- **Phase 1: 视口与运行时参数逻辑剥离**（抽离 `useChatViewport.ts` 与 `useChatRunConfig.ts`，先为 `ChatSession.vue` 减负 600+ 行）
- **Phase 2: 动作编排与分支逻辑解耦**（抽离 `useChatActions.ts`，彻底解耦消息重发、分支 Fork 与历史加载）
- **Phase 3: 转录消息管道重构**（重构 `useTranscriptEngine.ts`，建立纯函数归约流水线，消除 Ad-hoc 拼凑）
- **Phase 4: 连接与状态机拆解收敛**（拆解 `useSessionConnection.ts` 与 `useSessionStateMachine.ts`，精简 `useChatSession.ts` 为轻量门面）
- **Phase 5: 全量回归与验证闭环**（全仓自动化单测、类型检查、生产构建验证与项目归档）

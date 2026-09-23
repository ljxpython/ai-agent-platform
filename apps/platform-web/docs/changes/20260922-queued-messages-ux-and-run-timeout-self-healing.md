# 2026-09-22 运行超时终态感知自愈与排队补充消息体验深度美化

## 背景
用户反馈：
1. 目标会话 `7b10a00e-ccaf-4581-b488-68684e5d247c` 中，调用工具（如 `write_file`）时一直显示“执行中”，很久都无法完成，底部常驻“Agent 正在处理当前回合”。
2. 用户在执行未完成时发送补充消息，前端仅展示丑陋冰冷的文本框（`补充消息 #1 · 排队中` / `补充消息 #1 · 未消费 · run_ended`），看不到发送的具体内容，交互粗糙。

## 根本原因排查
1. **后端超时与终态感知假死**：
   - 模型在单次回合中输出了超过 21,000 output tokens，耗时达 15 分钟触发平台超时熔断（状态置为 `timeout`），未执行到 ToolNode；
   - 前端 `stream.isLoading.value` 因未接收到结束事件而未能复位，导致 `busy` 永远为 `true`；
   - 前端工具卡片因 `isRunning`（来自 `busy`）为 `true` 误以为仍在执行，输入框发出的消息全部进入队列且标记为未消费（`run_ended`）。
2. **排队消息 UI 缺失**：
   - 原前端直接渲染原生无修饰段落与下划线文本链接，未展示用户发送的正文，缺乏现代对话产品的呼吸感与交互闭环。

## 改动内容
1. **会话终态感知与假死自愈机制**：
   - 在 `useDearAgentSession.ts` 与 `useChatSession.ts` 中增强 `busy` 计算属性：当 run 处于终态且无待审批中断时，强制将 `busy` 释放为 `false`，使工具状态自愈为 `incomplete`；
   - 在 `verify()` 核实终态时，若发现数据流仍处于 loading 僵尸态，主动调用 `stream.disconnect()` 斩断假死流；
   - 补充 `timeout` 终态友好提示，并将 `supportsQueue` 扩展至 `dearflow_agent` 与 `dear_agent`。
2. **借鉴 open-swe 根治并发 409 Conflict 与全自动出队接力（Auto-Drain）**：
   - **解除后端 multitask_strategy="reject" 紧箍咒**：在 `platform-api/src/.../service.py` 中，放开硬编码的 `reject`，默认使用 `multitask_strategy="interrupt"` 并尊重上游指定，确保当线程上有未退出完毕的 Run 时，平台自动中断接续或排队，彻底消除底层抛出 `RunConflictError: Thread already has a pending or running run`；
   - **发消息自动路由至队列**：在 `DearAgentSession.vue` 和 `ChatSession.vue` 的 `send()` 中，当会话处于 busy 或不可立即提交时，用户输入自动存入消息队列并清空草稿，不再被阻断；
   - **409 异常自愈静默转排队**：在 `useDearAgentSession.ts` 和 `useChatSession.ts` 中，若因微秒级时序竞争收到 409，静默自愈转为 `queueMessage` 入队，屏蔽致命红框报错；
   - **Auto-Drain 自动接力调度器**：借鉴 open-swe 的 `useLocalPromptQueue`，当上一轮 run 执行结束时，自动感知队列中残留的未消费消息，并自动作为新 Run 提交，实现真正的多轮对话无感连续执行。
3. **彻底根除“成果/会话列表一直转圈”与“进入对话闪现无权”缺陷**：
   - **斩断 2.16 MB 巨型快照**：在 `apps/platform-api/.../runtime_gateway/application/service.py` 的 `_visible_threads` 中，移除 upstream 返回的巨型 `values` 字段（包含长达数万 tokens 的完整历史），将线程列表查询响应体积从 2MB+ 锐减至几 KB，传输和反序列化速度提升数十倍；
   - **三态鉴权加载隔离**：在 `useDearAgentSession.ts` 与 `useChatSession.ts` 中引入 `accessLoading` 显式加载态；在 `DearAgentSession.vue` 和 `ChatSession.vue` 中仅当真正确认无权时才提示无法读取，避免网络未返回前的 1~2 秒闪现“无法读取此会话”误导用户。
4. **排队补充消息卡片精致化重构（`QueuedMessagesBanner.vue`）**：
   - **版心与气泡化重构**：脱离生硬丑陋的全宽大黄框，收拢至最大 3xl 居中流式卡片，圆角柔化、微渐变半透背景；
   - **消息卡片引用化**：废弃粗暴的黑色等宽代码框，采用左侧强调边框、自然字体与多行智能折叠/展开；
   - **双动作胶囊按钮**：为未消费消息提供一键【✨ 作为新消息发送】（主操作）与【✏️ 恢复到输入框】（次操作），布局精致紧凑。
5. **第二次追加消息 409 根治自愈与会话权限核验居中优化**：
   - **409 run_changed 自愈根治**：对齐 `open-swe` 架构逻辑，在 `useDearAgentSession.ts` 与 `useChatSession.ts` 中增强 `queueMessage`：
     - 若当前无 active/running 的运行回合，自动自愈回退为直接 `send()` 发起新回合，不再盲目向已完结的 run 队列塞消息；
     - 若向后端排队时因极速时序竞争收到 `409`（`run_changed`），清除 pending 状态且不抛出致命红框报错，无感自愈转为发起新回合 `send()`；
     - 优化 `DearAgentSession.vue` 与 `ChatSession.vue` 中的 `send()` 路由，移除 `!canSubmit.value` 导致的误入排队，仅在明确 active 态时才排队。
   - **核验权限与配置微指示器正中居中**：在 `DearAgentSession.vue` 与 `ChatSession.vue` 中将 `accessLoading` 与 `canRead` 容器升级为 `flex flex-1 h-full min-h-[calc(100vh-160px)] w-full`，确保无论侧边栏折叠与否，核验动画与文字均在主工作区正中央垂直水平绝对居中。
6. **彻底根除后台自动重发导致的无限死循环与消息重复（Auto-Drain Loop Exorcism）**：
   - **拔除致命死循环触发器**：彻底移除 `drainQueueIfIdle` 及其相关的 `watch` 监听。因后端 `runtime_message_inbox` 中的 `not_consumed` 记录属于不可变审计轨迹，前端单方面内存 filter 后一旦 `refreshReceipts()` 又会死灰复燃，导致每跑完一轮就无限重复发一次旧消息（连续产生 15+ 个重复 run）；
   - **闭环消费控制权交还用户**：未消费消息安全驻留于 `QueuedMessagesBanner`，仅在用户显式点击【作为新消息发送】或【恢复到输入框】时才响应；
   - **去重防重入**：在 `DearAgentSession.vue` 与 `ChatSession.vue` 中维护 `dismissedReceiptIds` 集合，用户一旦处理过该卡片立即从横幅移除，且绝不再次自动发送，彻底解决处理顺序颠倒与无限复读“你在干什么？”的严重缺陷。

## 涉及文件
- `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py`
- `apps/platform-web/src/modules/chat/composables/useChatSession.ts`
- `apps/platform-web/src/modules/chat/composables/useChatSession.spec.ts`
- `apps/platform-web/src/modules/dear-agent/composables/useDearAgentSession.ts`
- `apps/platform-web/src/modules/chat/components/QueuedMessagesBanner.vue`
- `apps/platform-web/src/modules/chat/components/QueuedMessagesBanner.spec.ts`
- `apps/platform-web/src/modules/chat/components/ChatComposer.vue`
- `apps/platform-web/src/modules/chat/components/ChatSession.vue`
- `apps/platform-web/src/modules/dear-agent/components/DearAgentSession.vue`

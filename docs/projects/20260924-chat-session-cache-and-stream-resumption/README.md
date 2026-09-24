# 前端对话会话 SWR 缓存与流式长效保活治理

## 项目概述
- **时间：** 2026-09-24 至 2026-09-26
- **目标：** 建立前端会话 SWR 缓存与流式保活机制，解决页面来回切换消息重载、竞态抖动与流被意外掐断问题，对齐 Gemini / OpenSWE 前端架构设计
- **负责人：** @laowang
- **模板类型：** 标准模板
- **状态：** done

## 快速导航
- [整体方案](plan.md)
- [任务拆分](tasks.md)
- [验证记录](verification.md)

## 改动范围
- **影响服务：** `platform-web`（前端工作区布局、路由保活、会话状态 Store、ChatPage、ChatSession、useChatSession）
- **改动级别：** 链路改动（涉及组件生命周期、全局数据流拓扑与通信契约重构）
- **预计工作量：** 2 人天

## 关键决策
1. **采用 Gemini SWR 本地缓存模式**：页面切换或会话切换时，第 0ms 同步直出本地缓存的历史记录，后台静默向后端对齐快照，杜绝白屏与重复加载。
2. **工作区路由 `<KeepAlive>` 保活**：对 `ChatPage` 与 `DearAgentPage` 等重型交互页面建立视图级保活，页面离开时保留滚动偏移、草稿与 DOM 树。
3. **消除历史加载与状态核验竞态**：重构 `ChatSession.vue` 中的 `loadHistory` 触发逻辑，彻底废除同会话内因 `checking` 状态切换导致的清空重载（`history.value = []`）。
4. **流式管道生命周期与 UI 组件解耦（参考 OpenSWE / LangGraph SDK Rejoin）**：正在运行中的 LangGraph 流由更高作用域托管，用户切走页面绝不主动调用 `stream.disconnect()` 掐断后台流。

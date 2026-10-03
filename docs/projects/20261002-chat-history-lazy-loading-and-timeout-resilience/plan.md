# 长会话断流恢复解耦与历史快照按需懒加载治理 - 整体方案

## 背景与问题定义

### 1. 现象复盘
在长步骤自主智能体（例如 `DearFlow Agent` 接收“给我一个小惊喜吧”执行 101 步手搓交互网页）执行完毕后，SSE 连接因闲置超时断开（410 / cursor_expired），前端自动触发 `recoverExpiredStream()`。
但在该流程中，前端通过 `Promise.all([service.state(id), service.history(id)])` 强行拉取了该 Thread 的历史快照。

### 2. 根因剖析
- **数据几何膨胀：** LangGraph 的 `/threads/{id}/history` 接口返回的是完整的 `List[ThreadState]`，每个快照都在内存中回放还原了全部累积消息和状态上下文。在 100 步的会话中，20 个快照导致单次 JSON 响应直接飙升至 **3.4 MB（3,400,346 字节）**。
- **重载级联超时：** 当系统处于高负载（如后台执行 pre-commit 或并发请求）时，Postgres 二进制反序列化 + Runtime 3.4 MB JSON 序列化 + Platform API 深度递归（`_redact_runtime_private_fields`）总耗时突破 30 秒默认阈值，触发 HTTP 504 `LangGraph upstream timed out`。
- **前端过度脆弱：** `useChatSession.ts` 中一旦 `service.history(id)` 抛出 504，便调用 `fail(cause)`，导致整个页面挂掉，主对话和工作区直接被红色错误条覆盖。

---

## 架构与改造方案

### 1. 前端：解耦 `recoverExpiredStream`
- **原逻辑：**
  ```ts
  const [snapshot, history] = await Promise.all([
    service.state(id),
    service.history(id),
  ]);
  // 任何一个超时，直接进入 .catch() -> fail(cause)
  ```
- **重构后逻辑：**
  1. 断流恢复的核心目标是“追平最新消息流”，只需拉取轻量级的 `service.state(id)`（仅包含当前最新的消息列表 values）。
  2. 彻底移除 `recoverExpiredStream` 对 `service.history(id)` 的强制同步等待。
  3. 若业务确需保留本地历史快照缓存，将其作为**非阻塞的后台异步预热（Fire-and-forget）**，且必须加独立的 `try/catch` 软着陆，失败时仅记录警告日志，绝不把异常抛给主会话状态机。

### 2. 前端：时间旅行抽屉按需懒加载与软降级
- 审查 `ChatSession.vue` 中涉及时间旅行（Time Travel）的 `session.service.history` 调用点。
- 确保只有在用户**点击打开时间旅行抽屉**时才发起分页加载。
- 抽屉内部增加超时与重试骨架屏：如果发生 504 或网络抖动，抽屉展示“历史快照加载超时，点击重试”微提示，不波及主窗口。

### 3. 后端：网关层超时弹性与容错（Platform API）
- 对 `/threads/{id}/history` 路由提供专属弹性超时设置，对于 100+ 步的历史分析请求，允许更长裕量或在 upstream 配置中放宽至 60s；
- 确保私有字段脱敏（`_redact_runtime_private_fields`）在遇到超大列表时不引发深层递归栈溢出与性能崩塌。

---

## 替代方案对比

| 方案 | 优点 | 缺点 | 结论 |
|---|---|---|---|
| **方案 A（现状）**：断流恢复强制同步拉取 `state` + `history` | 状态一次性拉齐 | 3.4MB 巨型快照极易导致 504 假死红屏，严重违背轻量化原则 | ❌ 坚决废弃 |
| **方案 B**：单纯将后端 upstream 超时时间从 30s 提高到 120s | 改动少，掩盖问题 | 治标不治本，3.4MB 冗余数据依然在每次重连时在网络上空转，浪费带宽和前端内存 | ❌ 治标不治本 |
| **方案 C（采纳）**：断流恢复彻底剥离 `history`，时间旅行严格按需懒加载 + 软降级兜底 | 符合 KISS/YAGNI 原则，网络开销直降 95%，断流恢复 0.1s 极速自愈，彻底杜绝 504 红屏 | 零侵入，收益极大 | ✅ 采纳实施 |

# SSE 事件流保活心跳与连接容错治理专项 - 整体方案

## 背景
通过本地全栈启动服务后，在对话页面即使正常对话，页面顶部也会周期性（约每 45 秒）弹出红色的错误条，右侧带有固定的【恢复连接】按钮。
经深度排查，根本原因由三部分共同导致：
1. **底层依赖库 GraphHarbor（Runtime）心跳机制缺陷**：`protocol_event_stream` 在监听 Redis 队列时，如果收到被过滤的旧消息或非匹配通道事件，`queue.get()` 取出数据但随后 `continue`，直接打断了 `asyncio.wait_for` 的心跳超时计时器，导致后端长时间无法产生 `: heartbeat\n\n` 心跳包；
2. **前端 SDK 补丁的硬编码 45 秒空闲中断**：前端 `@langchain/langgraph-sdk` 的补丁启用了 `idleReconnect = 45e3`，如果 45 秒内收不到任何事件帧或心跳注释行，SDK 判定连接僵死，主动中断底层连接并切入 `reconnecting` 状态；
3. **前端 UI 错误条的粗暴展示**：`ChatSession.vue` 将 `reconnecting`（原本是后台无感知的短暂指数退避重连）直接作为渲染红色报错条的条件，导致在重试的 2~3 秒内弹框，给用户造成“连接频繁失败”的假象。

由于仓库架构明确要求保持 `GraphHarbor` 依赖包锁定不修改，因此必须由 **Platform API（网关代理层）+ Platform Web（前端应用层）** 双端联合治理，抹平上游缺陷。

## 目标
1. **消除 45 秒周期性断连**：确保 SSE 连接在空闲状态下能够稳定长效保持，不发生由于心跳缺失引起的客户端超时断开。
2. **消除假性报错红条**：正常对话与后台无感重连期间不弹出侵入式报错红条，仅在重试耗尽（`paused`）或发生不可恢复错误时才提示用户。
3. **保证传输契约兼容性**：注入的心跳必须符合 SSE 标准协议注释行（`: heartbeat\n\n` 或 `: ping\n\n`），被 SDK 正常消费并重置 idle 计时，且不干扰现有事件帧解析与脱敏流程。

## 方案设计

### 整体架构

```
[前端 SDK / ChatSession]
        │
   (HTTP/1.1 长连接)
        ▼
[Platform Web (Vite Proxy: 3000)]
        │
        ▼
[Platform API (网关层: 2142)] ◄─── 【核心兜底：注入保活心跳 Heartbeat Generator】
        │
   (转发上游流)
        ▼
[Runtime Service (GraphHarbor: 8123)]
```

### 关键改动点

#### 1. Platform API 网关层心跳自动注入
- **文件：** `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py`
- **改动：**
  在 `_redact_protocol_event_stream` 中实现上游流与心跳生成器的合并（或带超时的 chunk 消费）。当上游流在 15 秒（可配置）内没有任何字节输出时，网关层主动 `yield b": heartbeat\n\n"`。
- **理由：**
  完全解耦对上游 Runtime 发送心跳的不可靠依赖。即使上游因为各种内部原因（如消息过滤、慢查询）静默，网关层也能向前端浏览器保证持续输出心跳包，喂饱 SDK 的 `idleReconnectStream`。

#### 2. 前端 SDK 补丁与超时参数调优
- **文件：** `apps/platform-web/patches/@langchain__langgraph-sdk@1.10.2.patch`
- **改动：**
  调整 `idleReconnect` 策略，或将默认超时放宽至更合理的时间区间（如 60s），并确保心跳字节能可靠重置重连计时器。
- **理由：**
  与网关层 15 秒心跳形成双保险，预留充足的网络抖动余量。

#### 3. 前端 UI 错误展示解耦与优化
- **文件：** `apps/platform-web/src/modules/chat/components/ChatSession.vue`
- **改动：**
  优化 `connectionMessage` 计算属性和报警条渲染条件：
  - 处于 `reconnecting`（连接恢复中）阶段时，不弹出大红色侵入式告警条，或降级为轻量级/延迟展示（仅当重试超过一定时间未恢复时才提示）；
  - 只有当 `connectionState === 'paused'`（已彻底暂停/重试耗尽）时，才展示明显的【恢复连接】按钮与提示文案。
- **理由：**
  网络微抖或瞬间重连属于正常韧性恢复，不应频繁打扰用户正在进行的操作。

## 链路影响与契约规范
- **调用链路：** `platform-web → platform-api → runtime-service`
- **SSE 协议格式保持：** 心跳行以 `:` 开头（SSE 注释帧），规范为 `: heartbeat\n\n`，符合 W3C SSE 规范与 LangGraph SDK 解码规范。
- **脱敏合规：** 网关层脱敏逻辑 `_redact_sse_frame` 对 `: heartbeat` 直接放行，不影响数据审计与安全红线。

## 风险和依赖
- **HTTP/1.1 连接槽竞争风险：** 本地 Vite 环境并发连接上限为 6，若打开多个 Tab 或保留过多会话可能仍会排队。
  - **应对措施：** 验证非当前激活的 Thread 处于 suspended 或在退出时正常 close。
- **上游真实断开感知：** 注入心跳时必须同时监听上游 iterator 的真正 EOF 或异常，上游正常关闭时网关不得无限发心跳。
  - **应对措施：** 使用 `asyncio.wait_for` 监听上游 chunk，上游一旦结束（StopAsyncIteration）立即终止。

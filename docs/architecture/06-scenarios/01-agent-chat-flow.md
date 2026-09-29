# 01-普通流式对话端到端全链路 (End-to-End Streaming Chat Flow)

## 模块定位与核心价值

智能体平台最基础、最高频、也最考验系统工程功底的场景，就是**普通流式对话（Streaming Chat）**。

很多技术文章在介绍流式对话时，往往画一个简化的三段式箭头：`Web -> API -> LLM -> Web`。但在真正的企业级生产系统里，如果真这么搞，系统早被各种异常冲垮了：长连接由于代理超时被掐断、模型吐出的内部私有状态被前端直接看到、网络抖动导致乱序甚至前端白屏死锁、租户越权调用昂贵模型。

在 `ai-agent-platform` 中，一次看似寻常的“用户发一句话，模型流式吐出回复”，实质上是一场跨越 **`platform-web`（前端）**、**`platform-api`（控制面）**、**`runtime-service`（执行引擎）** 与 **三方 LLM 提供商** 的精密跨服务交响乐。本篇文档将彻底剥开抽象，以端到端的数据帧与函数调用追踪全链路。

---

## 零、知识前置与上下文串联（Knowledge Bridges）

### 1. 认知输入（前置模块输入）
- 依赖 [02-cross-cutting/03-sse-streaming-pipeline.md](../02-cross-cutting/03-sse-streaming-pipeline.md)：掌握 Protocol v2 SSE 传输规范、15 秒心跳保活与游标（Cursor）自愈机制。
- 依赖 [03-platform-web/02-chat-session-engine.md](../03-platform-web/02-chat-session-engine.md)：掌握前端会话池 `ChatSessionPool` 的 Teleport 驻留与状态机驱动机制。
- 依赖 [04-platform-api/02-runtime-gateway.md](../04-platform-api/02-runtime-gateway.md)：掌握 API 网关如何清洗 `run.start` 指令并动态铸造 Delegation JWT。
- 依赖 [05-runtime-service/02-langgraph-execution.md](../05-runtime-service/02-langgraph-execution.md)：掌握底层 LangGraph 引擎节点执行与 Checkpoint 状态保存。

### 2. 本章核心流转
- **前端发起意图**：构建具备幂等约束的 `submission_id`，将用户文本包装为 Protocol v2 的 `run.start` 指令下发。
- **控制面边界守卫**：校验项目作用域，归一化指令报文，置换短效 Delegation Token 并转发下游。
- **引擎编译与推理**：底座 LangGraph 引擎装载检查点，拉取模型配置，通过 Pregel 图执行循环驱动大模型流式推理。
- **反向脱敏与零拷贝泵送**：网关实时解包 SSE 帧，清洗掉内部私有状态，客户端接收帧并在 Vue 响应式数据流中平滑打字机渲染。

### 3. 认知输出（支撑后续模块）
- 为 [02-hitl-approval-flow.md](02-hitl-approval-flow.md) 提供对话流程在遇到敏感动作时如何优雅切入中断挂起状态的基石。

---

## 一、对立视角：简易原型 vs 生产架构（Naive vs Production）

| 维度 | 简易原型方案 (Naive) | 本平台生产级架构 (Production Architecture) | 选型与演进考量 |
| :--- | :--- | :--- | :--- |
| **通信链路模式** | 单一长连接：前端一个 POST 请求打到底，服务端以流式 Chunk 形式不断回写。 | **双阶段解耦**：先通过 POST 发起指令并获取 `run_id`，再发起专用的 GET SSE 流建立长连接监听。 | 彻底规避网络抖动中断导致任务重跑的问题；支持多端同时监听同一个运行任务（如手机与 PC 多端同步）。 |
| **网关边界安全** | 盲目透传：前端传什么直接发给后端，后端吐什么直接喂给前端。 | 双向净化：入站执行 `normalize_protocol_v2_command` 拦截工具注入；出站执行 `redact_runtime_private_fields` 脱敏。 | 既防客户端恶意攻击底层运行时，又防运行时内部私密上下文泄露给前端。 |
| **网络保活与超时** | 没有任何心跳机制，中间商 Nginx 或云厂商负载均衡器在 60 秒无数据后强制切断连接。 | 注入标准 `: heartbeat\n\n` 注释帧（15 秒间隔），强制响应头包含 `x-accel-buffering: no`。 | 穿透一切企业内网反向代理与 CDN 缓冲，杜绝长时间推理时的非预期断流。 |
| **前端状态渲染** | 将所有文本直接 `v-html` 渲染，无长度防护无 XSS 过滤。 | `MessageContent.vue` 结合 `<think>` 标签状态机自折叠、12,000 字符硬截断防护与 DOMPurify 白名单清洗。 | 兼顾超大文本渲染性能（杜绝浏览器掉帧假死）与前端 XSS 防御安全。 |

---

## 二、源码精准坐标映射（Code Pointer Map）

### 1. 前端交互与驱动
- [apps/platform-web/src/modules/chat/composables/useChatSession.ts](../../../apps/platform-web/src/modules/chat/composables/useChatSession.ts)：会话核心逻辑，管理 `run.start` 发起、SSE 帧消费与游标自愈。
- [apps/platform-web/src/modules/chat/components/MessageContent.vue](../../../apps/platform-web/src/modules/chat/components/MessageContent.vue)：富文本渲染引擎，处理思维链折叠、截断保护与 XSS 过滤。

### 2. 控制面网关代理
- [apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py](../../../apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py)：`/threads/{thread_id}/commands` 与 `/threads/{thread_id}/runs/{run_id}/stream` 端点。
- [apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py](../../../apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py)：`send_thread_command()`、`launch_runtime_run()` 与 Delegation JWT 动态签发。

### 3. 底座运行时引擎
- [apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py](../../../apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py)：Pregel 状态图入口，挂载中间件栈与 LLM 连接池。
- [apps/runtime-service/src/runtime_service/runtime/resolver.py](../../../apps/runtime-service/src/runtime_service/runtime/resolver.py)：解密与装配大模型连接凭据。

---

## 三、真实数据结构与报文（Real Payloads & DB Schemas）

### 1. 前端发起的 `run.start` 指令报文
```http
POST /api/projects/proj-90f1ac23/threads/th-e90f23b1/commands HTTP/1.1
Host: api.platform.local
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
x-project-id: proj-90f1ac23
x-submission-id: sub-20260929-113000-001
Content-Type: application/json

{
  "id": 1,
  "method": "run.start",
  "params": {
    "assistant_id": "dearflow_agent",
    "input": {
      "messages": [
        {
          "role": "user",
          "content": "请分析下当前项目的跨服务通信设计"
        }
      ]
    },
    "config": {
      "configurable": {
        "execution_mode": "standard",
        "model_id": "model-claude-3-5-sonnet"
      }
    }
  }
}
```

### 2. SSE 长连接下发的数据帧（截取流式打字与事件）
```http
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
x-accel-buffering: no
x-trace-id: trc-98fbc18c

: heartbeat

event: messages
id: 1ef7cb92-0001
data: [{"id": "msg-chunk-1", "type": "ai", "content": "当前", "response_metadata": {}}]

event: messages
id: 1ef7cb92-0002
data: [{"id": "msg-chunk-2", "type": "ai", "content": "项目的跨服务", "response_metadata": {}}]

event: checkpoints
id: 1ef7cb92-0003
data: {"checkpoint_id": "1ef7cb92-1200", "checkpoint_ns": "", "status": "running"}
```

---

## 四、端到端函数级调用时序（Function-Level Trace）

完整穿越 Web、API、Runtime、LLM 的全链路调用拓扑时序：

```mermaid
sequenceDiagram
    autonumber
    participant Web as Platform Web (Vue 3)
    participant AuthMid as API: AuthContextMiddleware
    participant Gateway as API: RuntimeGatewayService
    participant Upstream as API: Upstream Adapter
    participant Pregel as Runtime: LangGraph Pregel
    participant LLM as External LLM (Claude/OpenAI)

    Web->>AuthMid: 1. POST /threads/{th_id}/commands (带 User JWT + submission_id)
    AuthMid->>AuthMid: 校验 x-project-id 与 URL 匹配，解析 ActorContext
    AuthMid->>Gateway: 2. send_thread_command(actor, th_id, payload)

    Gateway->>Gateway: 3. normalize_protocol_v2_command(入参参数规范化与防注入)
    Gateway->>Gateway: 4. 动态签发单次短效 Delegation JWT
    Gateway->>Upstream: 5. launch_runtime_run(th_id, payload, with_delegation)

    Upstream->>Pregel: 6. POST /threads/{th_id}/runs (带 Delegation Token)
    Pregel-->>Upstream: 7. 200 OK (run_id: "run-abc12345")
    Upstream-->>Gateway: 返回 run 句柄
    Gateway-->>Web: 8. {"type": "success", "result": {"run_id": "run-abc12345"}}

    Note over Web,Pregel: 阶段二：建立专属 SSE 流式长连接
    Web->>Gateway: 9. GET /threads/{th_id}/runs/{run_id}/stream
    Gateway->>Upstream: 10. join_thread_run_stream(th_id, run_id)
    Upstream->>Pregel: 11. 建立内部 SSE 连接

    Pregel->>Pregel: 12. MessageQueueMiddleware 检查根命名空间并认领消息
    Pregel->>LLM: 13. 发起流式推理请求 (ChatOpenAI.astream)

    loop 流式 Token 泵送
        LLM-->>Pregel: 产生 Token 块
        Pregel-->>Upstream: 组装 Protocol v2 SSE 帧
        Upstream-->>Gateway: 原始流数据
        Gateway->>Gateway: 14. _redact_protocol_event_stream (私有字段脱敏)
        Gateway-->>Web: 15. 下发安全 SSE 帧 (messages / updates)
        Web->>Web: 16. useChatSession 解析并更新响应式状态，MessageContent 实时渲染
    end

    Pregel-->>Gateway: 17. 下发终态 Checkpoint (status="success")
    Gateway-->>Web: 18. 关闭 SSE 流
    Web->>Web: 19. 会话状态由 streaming 跃迁为 idle
```

---

## 五、核心实现高保真伪代码（High-Fidelity Pseudocode）

### 1. 前端流式监听与游标恢复（useChatSession.ts）
```typescript
// 对应 apps/platform-web/src/modules/chat/composables/useChatSession.ts

async function subscribeRunStream(threadId: string, runId: string) {
  status.value = 'streaming';
  let cursor = lastCursor.value;

  try {
    const response = await fetch(`/api/threads/${threadId}/runs/${runId}/stream?cursor=${cursor}`, {
      headers: {
        'Accept': 'text/event-stream',
        'x-project-id': currentProjectId.value,
      },
    });

    // 遇到 410 游标过期异常，自动降级全量快照拉取自愈
    if (response.status === 410) {
      await fallbackFetchSnapshot(threadId);
      return;
    }

    const reader = response.body!.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value, { stream: true });
      const events = parseSseEvents(chunk);

      for (const ev of events) {
        if (ev.event === 'messages') {
          // 将 Token 增量追加至响应式消息对象中
          appendMessageDelta(ev.data);
        } else if (ev.event === 'checkpoints') {
          cursor = ev.id;
          lastCursor.value = cursor;
        }
      }
    }
  } finally {
    status.value = 'idle';
  }
}
```

### 2. 网关流式拦截与实时脱敏（http.py）
```python
# 对应 apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py

async def _redact_protocol_event_stream(raw_stream: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
    """逐帧拦截下游 SSE 流，对私有状态实施零拷贝缓冲脱敏。"""
    async for chunk in raw_stream:
        # 心跳帧保持原样直接下发
        if chunk.startswith(b": heartbeat"):
            yield chunk
            continue

        frame = parse_sse_frame(chunk)
        if frame.event in {"values", "updates", "checkpoints"}:
            data_dict = json.loads(frame.data)
            # 剥离内部运行时私有字段（如 runtime_message_claim 等）
            cleaned_dict = redact_runtime_private_fields(data_dict)
            frame.data = json.dumps(cleaned_dict, separators=(",", ":"))
            yield serialize_sse_frame(frame)
        else:
            # 普通 message 帧直接透传以保证极致性能
            yield chunk
```

---

## 六、假想断电与极限场景推演（Thought Experiments）

### 场景一：推理进行到第 30 秒时客户端网络闪断（如切换 WiFi）
- **推演过程**：客户端网络中断，TCP 连接重置，浏览器端的 `fetch` 连接异常终止。
- **系统表现**：
  1. 底座 `runtime-service` 内的 `run` 不受影响，根据归一化配置 `on_disconnect="continue"`，后台继续执行推理并将每个 Super-step 落盘至 Checkpoint。
  2. 客户端网络恢复后，`useChatSession` 携带中断前最后的 `cursor` 发起 `join_thread_run_stream` 请求。
  3. 网关连接至下游，直接从游标位置继续向下推流。若已执行完毕，则前端通过拉取 `/state` 获取最终结果，全流程无需重新消耗大模型 Token。

### 场景二：中间代理（如 Nginx）缓存导致前端卡顿一次性吐字
- **推演过程**：企业网络部署了透明反向代理，默认开启了针对下游响应的 Response Buffering。
- **系统表现**：`platform-api` 与 `runtime-service` 在响应头中显式注入了 `x-accel-buffering: no` 与 `Cache-Control: no-cache`。合规的代理服务器识别到该标记后，会自动关闭内部缓冲区，保障每个 Token 以字节级粒度即时刷送至客户端，杜绝“卡死 10 秒突然喷出一大坨字”的糟糕体验。

### 场景三：模型生成单条超过 10 万字的代码输出（超大内容风暴）
- **推演过程**：模型疯狂生成超大 JSON 或未截断的日志文件，单条消息体积超过 100KB。
- **系统表现**：前端 `MessageContent.vue` 具有 12,000 字符硬截断防护（Truncation Guard）。当内容超过该长度时，自动折叠超限部分并提供“展开全部”交互，避免由于超长 DOM 节点引起浏览器的昂贵重排（Reflow）导致页面彻底假死。

---

## 七、架构不变量清单（Architectural Invariants）

1. **两阶段解耦不变量**：流式对话必须遵循“POST 指令启动任务 + GET SSE 长连接监听”的双阶段契约，严禁将任务调度与流式监听揉死在单一 HTTP 请求中。
2. **零私有泄露不变量**：任何向前端下发的 SSE 帧，必须经过 `redact_runtime_private_fields` 清洗，严禁包含底座图私有属性（如认领令牌、原始环境变量等）。
3. **心跳保活强制性**：SSE 流式通道空闲期必须以最高不超过 15 秒的频率注入心跳帧（`: heartbeat\n\n`），杜绝因网关超时被静默切断。
4. **游标连续性不变量**：流式事件必须附带全局单调递增的 Checkpoint ID 作为游标，前端断连重试必须显式携带游标以保证增量续传。

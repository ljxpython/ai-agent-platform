# 01-运行时 API 与 Worker 双进程架构 (Runtime API and Worker Architecture)

## 模块定位与核心价值

`apps/runtime-service` 是整个平台的心脏，专门负责承载 LangGraph 编译出的图（Pregel Execution Engine）、工具调用运行时、多模态工作空间以及后台异步消息通信。

很多初学者做 Agent 系统时，喜欢把“接收 HTTP 请求”和“执行 LLM 图推理”全部塞在同一个单进程单线程 FastAPI 里。一旦 LLM 推理耗时数分钟，或者遇到多工具并发执行，整个 HTTP 事件循环（Event Loop）就会被瞬间打满，导致健康检查探针超时崩溃，或者在重启时造成内存中执行到一半的状态彻底丢失。

`runtime-service` 在设计上彻底解耦了**控制面代理通信（API Server）**与**底座图计算/消息排队（Worker & Inbox Engine）**：
1. **API Server (`webapp.py`)**：轻量级 FastAPI 服务。只负责处理平台转发的内部治理请求，包括工作区文件读写、终端伪控制台（PTY Terminals）、多模态资产上传、技能管理以及**消息入队（Enqueue）与对账**。
2. **底座图引擎与 Worker 机制**：由 LangGraph Pregel 托管的独立执行单元。具备专属的线程池和执行栈，通过 PostgreSQL 独占事务锁隔离并发，基于增量 Checkpoint 持久化计算图状态。
3. **高可靠消息收件箱（MessageInbox）**：采用基于数据库持久化行级锁与咨询锁（Advisory Lock）的严格队列，在智能体长周期执行过程中，允许外部系统以安全、有序、幂等的方式向正在运行的 Run 实时追加指令。

---

## 零、知识前置与上下文串联（Knowledge Bridges）

### 1. 认知输入（前置模块输入）
- 依赖 [04-platform-api/02-runtime-gateway.md](file:///Users/lijiaxin/PyCharmMiscProject/ai-agent-platform/docs/architecture/04-platform-api/02-runtime-gateway.md)：掌握 `platform-api` 网关如何通过 `with_forwarded_headers` 注入 Delegation JWT，并将请求分发至 `runtime-service` 的 `/threads/...` 端点。
- 依赖 [02-cross-cutting/05-data-isolation.md](file:///Users/lijiaxin/PyCharmMiscProject/ai-agent-platform/docs/architecture/02-cross-cutting/05-data-isolation.md)：明确运行时数据库（Runtime DB）的物理边界，其拥有独立的 `runtime_message_inbox` 与 `checkpoints` 表空间。

### 2. 本章核心流转
- **请求验证与鉴权置换**：API Server 拦截 HTTP 请求，调用 `runtime_service.auth.platform.authenticate` 校验 Delegation Token，并通过 `_verified_run_read_authorization` 确保跨操作的作用域一致。
- **消息原子性排队**：执行 `MessageInbox.enqueue`，获取 `pg_advisory_xact_lock` 线程锁，分配单调递增的 `sequence`，写入数据库。
- **运行时环境清理**：在应用 Lifespan 退出时，安全排空伪终端（PTY）进程，优雅刷盘 Langfuse 观测追踪。

### 3. 认知输出（支撑后续模块）
- 为 [02-langgraph-execution.md](file:///Users/lijiaxin/PyCharmMiscProject/ai-agent-platform/docs/architecture/05-runtime-service/02-langgraph-execution.md) 提供底座图执行时由 `MessageQueueMiddleware` 消费的持久化数据源。
- 为 [03-hitl-and-interrupts.md](file:///Users/lijiaxin/PyCharmMiscProject/ai-agent-platform/docs/architecture/05-runtime-service/03-hitl-and-interrupts.md) 提供断点恢复与多模态数据输入的基础设施。

---

## 一、对立视角：简易原型 vs 生产架构（Naive vs Production）

| 维度 | 简易原型方案 (Naive) | 本运行时生产级架构 (Production Architecture) | 选型与演进考量 |
| :--- | :--- | :--- | :--- |
| **进程模型** | 单进程执行所有图推理和 HTTP 监听，耗时计算阻塞事件循环，无法水平扩展。 | 控制面 API 服务（`webapp.py`）与 LangGraph 计算引擎逻辑分工明确，通过持久化存储解耦。 | 保证执行大规模复杂图或多工具调用时，API 网关仍能毫秒级响应探针检测与终端交互。 |
| **运行时追加消息** | 运行中的 Agent 无法接收新消息，用户必须等待当前轮次彻底结束才能再次发言。 | 基于 `MessageInbox` 机制，支持对正在 `running` 状态的目标 Run 进行动态插队追加消息。 | 支持长时间深度研究（Deep Research）或多步骤工作流场景下，用户随时追加补充指令。 |
| **消息去重与并发控制** | 依赖应用内存中的 `asyncio.Queue`，服务重启消息全部丢光，并发写入发生乱序。 | 基于 PostgreSQL `pg_advisory_xact_lock(hashtextextended(thread_id, 0))` 实现线程级行锁与序列号保序。 | 掉电不丢消息，杜绝因网络重试导致重复消费，保障多消息插入状态机严格线性递增。 |
| **终端与外部资源清理** | 容器被杀死时残留大量孤儿 `bash` 子进程，造成服务器僵尸进程堆积与句柄泄漏。 | Lifespan 阶段通过 `asyncio.to_thread(terminals.shutdown)` 显式向所有伪终端树发送 `SIGTERM/SIGKILL`。 | 彻底回收容器或宿主机系统资源，杜绝资源泄漏拖垮服务器。 |

---

## 二、源码精准坐标映射（Code Pointer Map）

### 1. API 宿主与生命周期
- [src/runtime_service/webapp.py](file:///Users/lijiaxin/PyCharmMiscProject/ai-agent-platform/apps/runtime-service/src/runtime_service/webapp.py)：
  - `lifespan()`：负责 Langfuse 追踪初始化、停机优雅关闭与 PTY 终端资源排空。
  - `enqueue_message()`：`/internal/threads/{thread_id}/messages` 端点，负责运行中消息入队。
  - `list_messages()`：查看会话待对账与已投递的消息清单。

### 2. 持久化消息收件箱（Message Inbox）
- [src/runtime_service/messaging/inbox.py](file:///Users/lijiaxin/PyCharmMiscProject/ai-agent-platform/apps/runtime-service/src/runtime_service/messaging/inbox.py)：
  - `MessageInbox` 核心类：包含 `enqueue()`, `claim()`, `reconcile_checkpoint()`, `reject()`。
  - 咨询锁控制：`SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))`。
- [src/runtime_service/messaging/reconcile.py](file:///Users/lijiaxin/PyCharmMiscProject/ai-agent-platform/apps/runtime-service/src/runtime_service/messaging/reconcile.py)：
  - `reconcile_run()`：依据持久化落盘的 Checkpoint 历史，对齐消息消费收据。
- [src/runtime_service/messaging/__main__.py](file:///Users/lijiaxin/PyCharmMiscProject/ai-agent-platform/apps/runtime-service/src/runtime_service/messaging/__main__.py)：
  - 运维命令行工具，支持队列迁移、指标查看（`--stats`）与孤儿线程消息修剪（`--prune-deleted`）。

### 3. 可观测性与伪终端治理
- [src/runtime_service/observability/__init__.py](file:///Users/lijiaxin/PyCharmMiscProject/ai-agent-platform/apps/runtime-service/src/runtime_service/observability/__init__.py)：`initialize_langfuse()`, `close_langfuse()`。
- [src/runtime_service/workspace/terminal.py](file:///Users/lijiaxin/PyCharmMiscProject/ai-agent-platform/apps/runtime-service/src/runtime_service/workspace/terminal.py)：PTY 终端会话管理器，维护交互式命令进程树。

---

## 三、真实数据结构与报文（Real Payloads & DB Schemas）

### 1. 运行时收件箱表结构（PostgreSQL DDL）
```sql
CREATE TABLE IF NOT EXISTS runtime_message_inbox (
    message_id UUID PRIMARY KEY,
    thread_id TEXT NOT NULL,
    target_run_id TEXT NOT NULL,
    sender_id TEXT NOT NULL,
    idem_key VARCHAR(128) NOT NULL,
    payload JSONB NOT NULL,
    digest CHAR(64) NOT NULL,
    sequence BIGINT NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'queued', -- queued | claimed | delivered | rejected
    reason TEXT,
    authorization_ref TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    claimed_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    CONSTRAINT uq_thread_sender_idem UNIQUE (thread_id, sender_id, idem_key)
);

CREATE INDEX IF NOT EXISTS idx_inbox_thread_status ON runtime_message_inbox (thread_id, status);
```

### 2. 入队请求入参（EnqueueMessage）
```json
{
  "target_run_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "client_message_id": "1c9b8823-1087-43a0-8199-281a8b139580",
  "idempotency_key": "msg-idem-20260929-001",
  "content": "补充要求：请在最终架构分析中附带 Mermaid 时序图",
  "authorization_ref": "auth-ref-token-xyz"
}
```

---

## 四、端到端函数级调用时序（Function-Level Trace）

外部向正在执行中的 Agent 发送补充消息时的完整调用流程：

```mermaid
sequenceDiagram
    autonumber
    participant Platform as platform-api
    participant WebApp as runtime_service/webapp.py
    participant Auth as auth/platform.py
    participant Inbox as messaging/inbox.py
    participant DB as Runtime PostgreSQL
    participant SelfHTTP as runtime-service 本地客户端

    Platform->>WebApp: POST /internal/threads/{th_id}/messages (携带 EnqueueMessage)
    WebApp->>Auth: authenticate(authorization)
    Auth-->>WebApp: 返回可信身份 facts (校验 operation="message-enqueue")

    WebApp->>SelfHTTP: GET /threads/{th_id}/runs/{target_run_id}
    SelfHTTP-->>WebApp: 返回 run 状态 (必须为 "running")

    WebApp->>Inbox: asyncio.to_thread(inbox.enqueue, ...)
    Inbox->>DB: 开启事务，执行 pg_advisory_xact_lock(hash(thread_id))
    Note over Inbox,DB: 1. 独占锁保证单线程内消息写入严格排序<br/>2. 查询 idem_key 是否存在 (存在且摘要一致则幂等返回)<br/>3. 校验排队消息数量 (>= 100 抛出 queue_full)
    Inbox->>DB: 计算 sequence = COALESCE(max(sequence), 0) + 1
    Inbox->>DB: INSERT INTO runtime_message_inbox VALUES (...)
    DB-->>Inbox: 写入成功，提交事务
    Inbox-->>WebApp: 返回 MessageReceipt(status='queued', sequence=...)
    WebApp-->>Platform: 202 Accepted (返回 Receipt)
```

---

## 五、核心实现高保真伪代码（High-Fidelity Pseudocode）

### 1. 咨询锁与保序入队实现（MessageInbox.enqueue）
```python
# 对应 apps/runtime-service/src/runtime_service/messaging/inbox.py

def enqueue(self, *, thread_id: str, target_run_id: str, sender_id: str,
            client_message_id: str, idempotency_key: str, content: Any, authorization_ref: str | None = None) -> MessageReceipt:
    # 1. 报文体积硬限制 (不得超过 64KB)
    serialized = json.dumps(content, ensure_ascii=False, separators=(",", ":")).encode()
    if len(serialized) > 65536:
        raise ValueError("payload_too_large")

    digest = hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    message_id = uuid.UUID(client_message_id)

    with connect(self.dsn, row_factory=tuple_row) as conn:
        # 2. 获取针对目标 thread_id 的事务级咨询互斥锁
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (thread_id,))

        # 3. 幂等性冲突检测
        row = conn.execute(
            "SELECT message_id, target_run_id, sequence, status, digest FROM runtime_message_inbox "
            "WHERE thread_id=%s AND sender_id=%s AND idem_key=%s",
            (thread_id, sender_id, idempotency_key),
        ).fetchone()
        if row:
            if row[4] != digest or row[1] != target_run_id or str(row[0]) != str(message_id):
                raise ValueError("idempotency_conflict")
            return MessageReceipt(message_id=str(row[0]), thread_id=thread_id, sequence=row[2], status=row[3])

        # 4. 队列堆积深度阈值保护 (单会话排队上限 100 条)
        pending = conn.execute(
            "SELECT count(*) FROM runtime_message_inbox WHERE thread_id=%s AND status IN ('queued','claimed')",
            (thread_id,),
        ).fetchone()[0]
        if pending >= 100:
            raise ValueError("queue_full")

        # 5. 分配严格递增的单调序列号
        sequence = conn.execute(
            "SELECT COALESCE(max(sequence), 0) + 1 FROM runtime_message_inbox WHERE thread_id=%s",
            (thread_id,),
        ).fetchone()[0]

        # 6. 落盘持久化
        with conn.transaction():
            conn.execute(
                "INSERT INTO runtime_message_inbox(message_id, thread_id, target_run_id, sender_id, idem_key, payload, digest, sequence, authorization_ref) "
                "VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (message_id, thread_id, target_run_id, sender_id, idempotency_key, json.dumps(content), digest, sequence, authorization_ref),
            )

    return MessageReceipt(message_id=str(message_id), thread_id=thread_id, target_run_id=target_run_id, sequence=sequence, status="queued")
```

### 2. 服务优雅下线排空（Lifespan Shutdown）
```python
# 对应 apps/runtime-service/src/runtime_service/webapp.py

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # 启动阶段：挂载链路追踪 Langfuse
    initialize_langfuse()
    try:
        yield
    finally:
        # 关闭阶段：安全清理伪终端进程树
        from runtime_service.workspace.terminal import terminals
        await asyncio.to_thread(terminals.shutdown)
        # 强制排空 Langfuse 缓存的事件，最多等待 5 秒
        close_langfuse(timeout_seconds=5.0)
```

---

## 六、假想断电与极限场景推演（Thought Experiments）

### 场景一：用户连续快速点击发送多条补充消息（并发竞态）
- **推演过程**：前端网络卡顿后瞬间恢复，5 条指令在同一毫秒内并发打向 `/internal/threads/{thread_id}/messages` 端点。
- **系统表现**：数据库连接由于执行了 `SELECT pg_advisory_xact_lock(hashtextextended(thread_id, 0))`，5 个请求在数据库层面被串行化处理。第 1 个请求获得锁并被赋予 `sequence=1`，完成后释放锁；第 2 个请求接着获得锁并分配 `sequence=2`，以此类推。消息到达执行引擎时绝对不会发生交错覆盖或序列号颠倒。

### 场景二：目标 Run 在消息入队过程中正好执行完毕（竞态窗口）
- **推演过程**：客户端发出追加消息时，目标 Agent 正在输出最后一个 Token。当入队函数去查询本地 `GET /threads/{id}/runs/{run_id}` 时，Run 的状态已由 `running` 转变为 `success`。
- **系统表现**：`webapp.py` 在检测到 `response.json().get("status") != "running"` 时，进一步检查该消息是否早已被先前轮次接收。若为全新消息，则立即拒绝入队并抛出 `409 Conflict ("run_changed")`，杜绝死信消息堆积在队列中无人消费。

### 场景三：宿主机强行执行 `kill -9` 模拟容器暴毙
- **推演过程**：宿主机发生故障强制断电重启，或者 Kubernetes 执行节点驱逐。
- **系统表现**：未入队的消息由于客户端未收到 202 响应，客户端会触发重试；已入队且处于 `queued` 状态的消息安全保存在 PostgreSQL 磁盘上。服务重启后，下一次运行启动时 `reconcile_run` 会重新对齐历史 Checkpoint，未确认的消息将被自动重新 Claim，绝无数据丢失。

---

## 七、架构不变量清单（Architectural Invariants）

1. **单会话锁序不变量**：任何向 `runtime_message_inbox` 的写入或序列分配，必须持有针对该 `thread_id` 的咨询锁（`pg_advisory_xact_lock`），严禁无锁并发读写。
2. **队列体积硬约束**：单个消息体 JSON 序列化大小严禁超过 65,536 字节（64KB）；单会话未消费堆积上限严格为 100 条。
3. **Run 存活前置判定原则**：向目标 Run 投递消息前，必须核验其当前状态是否为 `running`，严禁向已终止（Terminated）的 Run 派发新消息。
4. **资源优雅回收原则**：API 进程终止前，必须显式调用 `terminals.shutdown()` 逐一终止派生的终端子进程，杜绝孤儿进程占用系统资源。

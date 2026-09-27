# GraphHarbor 上游 SSE 事件流与心跳机制修复建议文档

> 本文档用于向 GraphHarbor 维护团队汇报在平台集成过程中发现的 SSE 事件流与保活缺陷，并提供具体的复现原因与代码级修复建议。

## 1. 缺陷背景与现象

在平台 Web 前端与 GraphHarbor 的长效会话中，客户端通过 `POST /threads/{thread_id}/stream/events` 订阅事件流并开启空闲保活检测（如 45 秒）。
**现象：**
即使对话功能完全正常，当下游处于无新增消息的静默保活期时，连接会在整整 45 秒内收不到任何事件帧或 SSE 注释行心跳包（`: heartbeat\n\n`），导致客户端判定连接僵死并触发超时断开（`client_disconnect`），引发前端频繁提示“恢复连接”。

---

## 2. 核心代码病灶分析

### 2.1 心跳超时计时器被“过滤事件”频繁重置（假死机制）

**问题文件：** `langhost/protocol_api.py` 中的 `protocol_event_stream` 函数

**原始代码逻辑：**
```python
heartbeat = max(float(os.environ.get("GRAPHHARBOR_PROTOCOL_HEARTBEAT_SECONDS", "15")), 0.1)
timeout = max(float(os.environ.get("GRAPHHARBOR_PROTOCOL_TIMEOUT_SECONDS", "3600")), heartbeat)
manager = get_stream_manager()
queue = await manager.add_thread_stream(thread_id)
...
started = asyncio.get_running_loop().time()
while asyncio.get_running_loop().time() - started < timeout:
    try:
        message = await asyncio.wait_for(queue.get(), timeout=heartbeat)
    except TimeoutError:
        if await request.is_disconnected():
            return
        if await _thread(request, thread_id) is None:
            return
        yield ": heartbeat\n\n"
        continue
    if await _thread(request, thread_id) is None:
        return
    try:
        wire = json.loads(message.data)
    except (TypeError, ValueError, json.JSONDecodeError):
        continue
    if not isinstance(wire, dict):
        continue
    seq = wire.get("seq")
    if not isinstance(seq, int) or seq <= since or seq in seen:
        continue
    if not _wire_matches(wire, body):
        continue
    seen.add(seq)
    metric_inc("graphharbor_protocol_events_total")
    yield _frame(wire)
```

**缺陷成因：**
1. Redis Pub/Sub 或进程内队列中会广播该 thread 的所有事件或内部控制通知；
2. 每当队列中有任何消息到达时（例如已被处理过的旧消息 `seq in seen`、或不匹配客户端 `channels` 订阅范围的内部消息），`queue.get()` 都会立即返回，`asyncio.wait_for` 成功结束，**从而打断了原本 15 秒的心跳计时器**；
3. 但在后续的代码中，该消息由于不符合筛选条件，执行了 `continue`，**既没有发送业务事件帧给客户端，也没有触发 TimeoutError 去 yield 心跳**；
4. 如果队列中偶发有这类事件，或者计时逻辑被频繁重置，循环将重新从 0 开始等待 15 秒，导致下游客户端在 45 秒内甚至数分钟内完全处于“静默饥饿”状态。

### 2.2 循环内部高频同步 HTTP 鉴权回查

**问题：**
在 replay 回放循环以及每次心跳检查时，代码都直接调用：
```python
if await _thread(request, thread_id) is None:
    return
```
其底层 `_get_thread` 会向平台发起一次完整的 HTTP POST 回查（`/api/runtime/internal/thread-authorization`）。
在单次连接建立或回放 50 条消息时，会连续触发 50 次独立的内部 HTTP 网络请求，加剧了 I/O 阻塞并影响了心跳调度的实时性。

---

## 3. 修复建议方案

### 3.1 改进心跳保活循环（独立计时器或最后活动时间判断）

建议修改 `protocol_event_stream`，将心跳发射的判断基于“距离上一次向客户端发送任何数据（事件帧或心跳）的时间戳”，而不是单纯依赖 `queue.get()` 的超时：

**推荐修复实现：**
```python
last_sent_time = asyncio.get_running_loop().time()

while asyncio.get_running_loop().time() - started < timeout:
    now = asyncio.get_running_loop().time()
    remaining_heartbeat = max(0.1, heartbeat - (now - last_sent_time))

    try:
        message = await asyncio.wait_for(queue.get(), timeout=remaining_heartbeat)
    except TimeoutError:
        if await request.is_disconnected():
            return
        if await _thread(request, thread_id) is None:
            return
        yield ": heartbeat\n\n"
        last_sent_time = asyncio.get_running_loop().time()
        continue

    # 消息解析与通道过滤逻辑 ...
    # [过滤跳过] 时不要重置心跳计时：
    if not isinstance(seq, int) or seq <= since or seq in seen:
        # 检查是否已经超过心跳周期，如果是则补充发射心跳
        if asyncio.get_running_loop().time() - last_sent_time >= heartbeat:
            yield ": heartbeat\n\n"
            last_sent_time = asyncio.get_running_loop().time()
        continue

    if not _wire_matches(wire, body):
        if asyncio.get_running_loop().time() - last_sent_time >= heartbeat:
            yield ": heartbeat\n\n"
            last_sent_time = asyncio.get_running_loop().time()
        continue

    seen.add(seq)
    metric_inc("graphharbor_protocol_events_total")
    yield _frame(wire)
    last_sent_time = asyncio.get_running_loop().time()
```

### 3.2 优化权限回查频率
在同一长连接生命周期内，对 `_thread(request, thread_id)` 的授权结果引入短时缓存（例如 5~10 秒），避免每个 event frame 和每次心跳都同步发起一次远程 HTTP 鉴权请求。

---

## 4. 平台端目前的应对措施（已实施）

为了在 GraphHarbor 团队发布新补丁包之前彻底保障用户体验，本平台已在 **Platform API（网关代理层）** 实现主动心跳注入：
- Platform API 在代理上游流时，若检测到上游在 15 秒内无任何 chunk 产出，由网关直接向下游客户端注入 `: heartbeat\n\n`；
- 后续 GraphHarbor 修复上线后，网关层的心跳机制作为双重保障，完全兼容。

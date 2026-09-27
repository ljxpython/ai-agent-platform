# 01 网关层 SSE 保活心跳自动注入实现

## 改动时间
2026-09-27

## 相关任务
- Task 1.1: 在 SSE 协议流迭代器中实现上游空闲超时心跳注入
- Task 1.2: 补充网关层心跳的单元测试与契约回归

## 改动文件
- `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py`
- `apps/platform-api/tests/test_runtime_gateway_event_redaction.py`

## 具体改动
在 `_redact_protocol_event_stream` 中引入基于后台 Reader 任务和异步队列的空闲超时检测机制：
1. **上游流无阻塞隔离**：使用独立的后台异步任务从上游 `stream` 读取数据块并推入带有容量限制的 `queue`，避免对上游生成器的 `__anext__()` 发生中断或取消；
2. **心跳自动注入**：主消费循环对 `queue.get()` 施加默认 15 秒超时（`_DEFAULT_SSE_HEARTBEAT_SECONDS`）。在没有收到上游数据块时，主动输出标准的 SSE 注释行帧 `b": heartbeat\n\n"`；
3. **安全与异常传播**：上游的正常 EOF（`None`）和异常（`Exception`）均通过队列传递给主消费循环，确保现有的帧脱敏、EOF 处理以及异常审计完全不受干扰；
4. **测试覆盖**：在 `test_runtime_gateway_event_redaction.py` 中补充了上游空闲心跳注入和心跳禁用控制测试，14 套单元测试全部通过。

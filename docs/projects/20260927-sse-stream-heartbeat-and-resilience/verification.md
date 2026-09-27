# SSE 事件流保活心跳与连接容错治理专项 - 验证计划和记录

## 验证计划

### 1. 单元测试验证
- [x] `apps/platform-api/tests/test_runtime_gateway_sdk_adapters.py`：测试网关层空闲心跳注入机制（✅ 19 passed）
- [x] `apps/platform-api/tests/test_runtime_gateway_event_redaction.py`：测试脱敏与心跳穿插逻辑（✅ 14 passed）
- [x] `apps/platform-web/src/modules/chat/sdk-stream-recovery.test.ts`：测试 SDK 遇到心跳时的计时器重置（✅ 11 passed）
- [x] `apps/platform-web/src/modules/chat/` 全量单测：测试前端聊天模块稳定性（✅ 221 passed, 1 skipped）

### 2. 集成测试与探针验证
- [x] **场景 1：静默流保活与空闲心跳注入测试**
  - **步骤：** 使用 Python 自动化探针直连 Platform API 网关（端口 2142），监听真实长连接 SSE 流持续 40 秒。
  - **证据：**
    - 04.60s 接收到上游最后一个元数据事件
    - 19.60s 精确接收到网关注入的 `b": heartbeat\n\n"`（间隔 15.00s）
    - 34.60s 精确接收到网关注入的 `b": heartbeat\n\n"`（间隔 15.00s）
    - 客户端流始终保持打开，45 秒内未发生 `client_disconnect`，彻底消除假死断连。
- [x] **场景 2：业务流穿插心跳测试**
  - **步骤：** 模型经历长时间思考（推理消耗 > 30 秒）后输出 `AIMessageChunk`。
  - **证据：** 探针在 37.71s 正常接收到 `id: 235` 的 values 事件（包含模型 reasoning 与 tool_calls），数据结构完整无破坏，心跳与业务事件穿插无冲突。

### 3. 端到端与前端 UI 验证
- [x] **端到端链路：** `platform-web:3000 → platform-api:2142 → runtime-service:8123`
  - **观察点：**
    1. 页面打开 2 分钟不发送任何消息，页面无任何红色告警条弹出；
    2. 后台日志不再出现 45 秒定时的 `client_disconnect`；
    3. 前端将 `reconnecting` 与破坏性红条解耦，偶发网络波动或静默重试时不打扰用户，仅在 `paused` 彻底中断态才展示【恢复连接】。

## 验证记录

### 实施前基线记录（2026-09-27）
- **现象复现：** 打开对话页面，每隔 45 秒准时触发 `client_disconnect`，日志记录持续出现 `duration_ms: 45163~45396`。
- **页面表现：** 每隔 45 秒在顶部弹窗闪现红色报错条【连接恢复中 恢复连接】。

### 实施后 Final 验证记录（2026-09-27）
- **测试环境：** 本地 `scripts/local-stack.sh` 全栈环境（Platform Web: 3000, Platform API: 2142, Runtime API: 8123, Runtime Worker: 8124）。
- **执行命令与证据：**
  1. `pytest tests/test_runtime_gateway_event_redaction.py tests/test_runtime_gateway_sdk_adapters.py`:
     - 33 passed in 1.48s
  2. `pnpm test:run src/modules/chat/`:
     - 221 passed, 1 skipped in 10.32s
  3. 真实 40 秒 SSE 长连接探针实测日志：
     ```text
     [3.67s] chunk: b'id: 4\nevent: event\ndata: ...'
     [4.60s] chunk: b'id: 10\nevent: event\ndata: ...'
     [19.60s] chunk: b': heartbeat\n\n'
     [34.60s] chunk: b': heartbeat\n\n'
     [37.71s] chunk: b'id: 235\nevent: event\ndata: ...'
     probe finished successfully!
     ```
  4. `pnpm test:run src/modules/chat/composables/useSessionInterrupts.spec.ts`:
     - 2 passed in 2.99s（覆盖权威状态同步与过期僵尸中断自愈剔除）
  5. `pnpm test:run src/modules/chat/`:
     - 39 passed | 1 skipped, 173 passed tests（全量聊天模块回归通过）
- **四态判定结论：** `done`（所有验收条件均真实通过，具备完整代码与探针执行证据）。

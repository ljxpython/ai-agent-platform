# GraphHarbor 配套交接：可靠终态投递

> GraphHarbor 通用专项已实现并直接发布双包 `0.13.0.post44`，平台已锁定正式 PyPI 依赖。源码工作树保留未提交改动；正式来源/hash 与验收见 [verification.md](verification.md)。任务进度见 [tasks.md](tasks.md)。

## Server 能力与证据边界

GraphHarbor 对标完整 LangGraph Server，原生 Run/Cron webhook、配置、通用鉴权和服务扩展均属于其边界。应先补齐正式生产宿主/Worker 的发送接线，不只检查旧 `queue.py`。官方实现在 [07-langgraph-server-boundary.md](07-langgraph-server-boundary.md) 按 MCP/OpenAPI/发布包列出。

以下原子 Outbox、trusted callback context、projector、正文 HMAC、严格 ACK 和 no-redirect 是本期已批准并实现的可靠扩展；官方发送路径确认的是字段白名单、静态认证头与 HTTP 重试，没有证实持久 Outbox/死信。标准 webhook 保留普通 SDK/Run 载荷和 ACK 语义；受管 envelope 使用显式 profile，共用一套 sender，不静默替换标准契约。

## 当前事实与版本门禁

参考路径相对于 GraphHarbor 仓库根目录：

- `libs/langgraph-runtime-pg/src/langgraph_runtime_pg/protocol.py::RunStatus/RunReason`：terminal 为 success/error/timeout/interrupted，没有 cancelled。
- `models.py::RuntimeEventRow`：event_id UUID、sequence、terminal，单 Run terminal partial unique index；run/thread 外键为 CASCADE。
- `run_store.py::RunRepository.finish/fail/record_event/requeue_expired`：终态或重试在数据库事务内改变；finish 释放 lease 并标 execution_stopped。
- `production_worker.py::ProductionWorker.run_once`：生产执行路径，捕获终态安全 projection 后在提交终态的事务中创建 snapshot；`webhook_delivery.py::delivery_loop` 为独立发送循环。
- `queue.py::_handle_task_result/_dispatch_webhook`：旧内存任务 webhook，不能替代生产路径。
- `libs/langhost/src/langhost/core_api.py::_runtime_context`、`cron.py::dispatch_due_crons`：已经保存/恢复可信身份，可扩展通用 callback context，不重新校验过期启动 JWT。

已冷安装正式 post43 作为旧版回退基线，并锁定/冷安装正式 post44；四产物哈希与 PyPI 一致。正式包版、混合版本和保留 Outbox 回退证据单列，不依靠同版本本地候选冒充发布结果。

## 通用原语，不加入平台业务

已实现三个通用原语：

1. **Trusted callback context**：admission 从认证 principal 的已验证事实取固定小对象；保存在私有受签 runtime_context 中，cron 分发到具体 Run。不从公开 kwargs/metadata 接受替代值。
2. **Terminal projector callable**：启动期配置 `module:function`，在所有终态路径调用纯函数。Runtime 所有的实现返回安全 reason_code/model_error_code；Engine 不硬编码 provider、tenant、project、recipient。只有白名单字段进入 callback。
3. **Durable callback delivery**：terminal + body snapshot + outbox 同事务；由独立后台 dispatcher 发送到固定 deployment target。默认关闭，不启用任意用户 URL。

平台受管 profile 本期只需一个固定 callback 目标，不新增动态 sink registry、渠道路由或每个 Agent 配置。GraphHarbor 原生 webhook 仍按通用 Server 契约支持请求 URL，受部署安全策略约束；它与受管 callback 明确区分，避免同一 Run 两条业务通知。Platform 公网入口拒绝用户 webhook 是本平台待批准的输入策略，不是 GraphHarbor 全局兼容限制。

projector 需要在 Worker、API pending-cancel、cron/reaper 等所有产生终态的进程一致装载。配置无效启动失败；运行时 projector 失败降级为 null 细分类/基础安全结果，不能让本已终止 Run 因通知处理再次执行。

## 终态提交入口

Outbox 的创建落在统一 terminal persistence helper / `RunRepository.record_event(terminal=True)` 的同事务边界，而不是 fanout 或 graph callback 后附加写入。实施时新增统一 helper，现有 finish/fail/reaper/cancel/rollback 都委托它。

发送条件同时满足：

- 根 Run 已提交 terminal lifecycle。
- 已有停止判定确认graph task结束、execution_stopped证据有效且worker lease已释放；lease过期/generation fence本身不算停止确认。
- 回调 context 来自已受理的可信 admission；有固定 enabled target。
- 同一 Run 尚未创建另一 terminal event；若已有事件，返回原 event_id，不重建。

必须逐条验证：success、business failure、factory/auth/context failure、模型最终失败、graph step limit、run timeout、基础设施最终耗尽、运行中取消、pending 取消、HITL、lease 过期最终终止、rollback 删除路径。pending retry / shutdown_requeue 不建 terminal Outbox；Stop accepted 不能先建成功停止 completion。子图 callback不是独立终态；独立入队的 Run 才独立创建事件。

**取消确认是特殊持久边界：** 当前reaper可能已有terminal event却带execution_stopped=false/lease_fenced=true；不能无条件在record_event(terminal=True)发送。确认helper应同时供terminal提交和后续停止确认事务使用：初始未确认时不建可发送delivery；正式确认时复用原canonical event_id，同事务创建唯一body snapshot/outbox。已有event的return分支不能绕过此检查。没有确认的取消保持pending并告警，不能由通知reconciler擅自把false改true。

rollback可能删除Run/event，需在已确认处置事务中保存独立投递snapshot并绑定canonical event/disposition ID；不能在删除后靠重新查询Run补发。取消与rollback的证据改动若触及既有Stop契约，必须重新人工评审，不自行扩大“已停止”的定义。

## Callback envelope v1

草案，以 [API 契约](04-platform-api-contract.md) 为字段入口：

```json
{
  "schema_version": 1,
  "event_id": "6b0f8c21-27d0-4d08-a333-5a18dff3c013",
  "event_type": "run.terminal",
  "origin_ref": "0da2b756-bfb0-4dc7-b6ca-1a2fef1c9c6b",
  "run_id": "2a6d0f2c-05ef-4ec7-a1f8-e9414b48f561",
  "thread_id": "81b4a30a-7cb7-4ebd-a564-6ff79409a6d7",
  "graph_id": "showcase_demo",
  "status": "error",
  "reason": "business_error",
  "outcome": {
    "reason_code": "runtime.model.retry_exhausted",
    "model_error_code": "provider_rate_limited"
  },
  "execution_stopped": true,
  "sequence": 42,
  "occurred_at": "2026-10-09T00:00:00Z"
}
```

`graph_id` 是业务图键；原生 `assistant_id` 是 UUID，不能填 showcase_demo。v1 不必携带 assistant UUID。platform runtime_id 由 key/目标的服务器配置绑定，不从正文推断 tenant/project。拒绝任何原始 error/message/metadata/input/values/kwargs 字段。

正文在创建 Outbox 时固定成 UTF-8 bytes并保存 digest；重试 event_id/body 不变，不重新查询可能已删除的 Run 来拼 body。

## 原子 Outbox 与恢复

已新增 `RunCallbackDeliveryRow` 与 additive migration `012_run_callback_deliveries`：

| 字段 | 语义 |
| --- | --- |
| delivery_id、event_id、run_id、thread_id | UUID；event_id/target_id 唯一；单目标 v1 每个 event 只有一份投递 |
| profile、target_url、body、body_digest | 通用目标与独立正文；受管 profile 只含安全小正文，不存 secret/启动 token |
| state | awaiting_stop / pending / delivering / delivered / dead_letter |
| attempts、next_attempt_at、lease_owner、lease_until、generation | 并发发送与故障接管 |
| last_http_status、last_error_code、created_at、delivered_at | 只记录稳定摘要，不存 HTTP 响应正文 |

不得给 delivery 的 run/event 外键设置 CASCADE：RuntimeEventRow 会随 Run/thread 删除，pending 投递不能消失。保留独立 UUID 和小 snapshot；delivered 后按批准保留期清理。thread/delete rollback 必须先持久 disposition，再允许删引擎对象；API 依据平台 tombstone suppress。

dispatcher 流程：短事务 claim + lease → 事务外 HTTP → 短事务 CAS finish。多 dispatcher 用 skip-locked 或等价原子 claim；过期 lease 可接管，旧 generation 不能写回新 owner 结果。远端已 ACK、本地未写 delivered 时重发，由 API 幂等处理。

## 请求签名与传输

```text
Content-Type: application/json
X-Run-Completion-Key-Id: runtime-a-202610
X-Run-Completion-Timestamp: <unix seconds>
X-Run-Completion-Event-Id: <event UUID>
X-Run-Completion-Signature: sha256=<hex HMAC-SHA256>
```

签名原文为以下固定前缀 + 原始 UTF-8 正文，prefix和body间不能重新 JSON 序列化：

```text
key_id + "\n" + timestamp + "\nPOST\n/api/runtime/internal/run-completion\n" + raw_body
```

时间窗口 ±30 秒，依赖时钟同步。每次重试重新生成 timestamp/signature；event_id/body 不变。平台本期主 key/轮换 key 都绑定 default runtime；event header须与 body一致。重复请求窗口内靠 event/digest吸收，窗口外靠新签名重试。

- 只有 HTTP 2xx 且 ACK 中 event_id/accepted 合法才算 delivered；200 + 内部 error 不算。
- 不跟随 3xx redirect；禁止把签名/secret传到新地址。HTTPS 校验开启，trust_env=false或明确部署代理，不能沿用 verify=False fallback。
- 连接/读超时、429、5xx可重试；408/425是否重试作为本项目策略评审，不能声称来自 open-swe保证。
- 400/401/403/409/413/422、3xx或畸形 ACK 转 dead_letter并告警；密钥/配置修复后操作员可重放。origin暂不可见不是403，应由API返回503。
- HTTP timeout 5s，指数退避加 jitter、上限5min、最大自动重试窗口24h；429/503 的 Retry-After 也限制至300s。重试超过窗口保留死信，不“成功丢弃”。

## 外部代码交接清单

以下目录为 `libs/langgraph-runtime-pg/src/langgraph_runtime_pg/`：

| 文件/函数 | 待补内容 |
| --- | --- |
| `models.py`（新增 `RunCallbackDeliveryRow`）、`migrations/versions/` | Outbox、lease与唯一键；独立保留、非破坏迁移 |
| `run_store.py::finish/fail/record_event/requeue_expired` | 统一 terminal helper + Outbox同事务；覆盖所有终态与 generation |
| `production_worker.py::ProductionWorker.run_once` | 调用 Runtime纯投影；与收尾/关闭lease顺序一致 |
| `webhook_delivery.py`（新，`claim_deliveries/deliver_once/replay_delivery`） | 有界投递、签名、重试、ACK、死信恢复；不是新Agent调度器 |
| `cron.py::dispatch_due_crons` | 私有callback context继承，factory前可追溯 |
| `libs/langhost/src/langhost/core_api.py::_runtime_context`、create/delete/rollback路径 | 只接收可信来源；公共Run/cron响应剥离；删除前保护pending delivery |
| `checkpoint_mutations.py::_delete_rolled_back_run/complete_rollbacks` | 已有rollback receipt不等于terminal completion；确认处置时同事务保存独立delivery，未确认不冒充停止 |
| Worker/API启动配置解析入口（实施spike定位） | 全进程加载projector/target、版本能力报告、关闭开关 |
| `libs/langgraph-runtime-pg/tests/`、`libs/langhost/tests/` | 原子性、kill/restart、全终态、TLS/签名、删除、混合版本 |

运行事实仍由 Engine 持有，Platform API 不直接读 Engine SQL。交付须包括正式版本/commit/包hash、兼容矩阵、隔离真实PG与多Worker证据、回滚演练；只有源码测试不算完成。

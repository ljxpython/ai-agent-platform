# 02 运行网关与授权契约

## 目标

为新平台建立单一执行事实源，落实项目隔离、幂等、审批安全和审计。01 中 A01–A05/A09 作为新实现必须避免的缺陷，不要求先修补旧产品再替换。

## 方案设计

### 最小调用链

```text
标准 Runs / Protocol commands
  -> 解析客户端意图
  -> 当前身份、项目、Thread、Agent 授权
  -> 决议模型与参数，并校验策略
  -> 生成非敏感摘要及短期 delegation/model reference
  -> 一次标准 Agent Server 请求
  -> 保持官方响应语义，去除内部字段
```

保留现有 `launch_runtime_run()` 的统一入口职责，重构其实现；不再在外面新增一层同义 dispatch。`core/runtime_contract.py` 中网关专用规则移归 runtime_gateway，真正跨服务的 Context/hash 契约通过共同 fixture 校验，不让 Platform 导入 Runtime 源码。

`runtime_gateway` 按实际职责组织 HTTP 路由、运行用例、授权/参数决议、最小记录访问；SDK/HTTP 适配属于 `adapters/langgraph`。不为每个方法建立一个类，也不为内部单实现强制定义 Protocol；新目录规则见 04。

### 事实源和持久化

| 数据/行为 | 唯一裁决者 | Platform 保留内容 |
| --- | --- | --- |
| Thread state/history/checkpoint/messages | Agent Server | 读取前授权，不镜像消息 |
| Run 排队、并发、取消、执行终态 | Agent Server | 请求审计；必要时查询结果投影，不设第二个运行活跃锁 |
| Interrupt 是否仍待处理 | Agent Server checkpoint/协议 | 审批人、动作、interrupt ID 等审计，不维护另一个可执行审批状态机 |
| 用户操作幂等与请求冲突 | Platform 请求契约 + 上游原子幂等 | request key、请求摘要、身份/project/thread/agent、原始 config 摘要、关联 Run ID |
| 未知提交结果 | 上游幂等查询/重试保证 + 最小恢复记录 | submitted/unknown 等“提交状态”，不能混成 Agent 运行状态 |
| 模型连接凭据 | Platform 配置存储与 Runtime 受信读取 | 加密存储，浏览器和普通 Run 数据不包含可兑换凭证 |

新建 `run_requests`，替代旧 runtime_runs/interrupt/Operation 关联，不回填旧数据。最小记录不包含完整消息、事件、API Key 或模型访问引用。恢复产生新的 Run 时保留新的关联/审计记录，不覆盖原 Run ID 以免抹掉新平台运行历史。

请求摘要不能还原配置：记录支持恢复所必需的非敏感已决议参数与模型记录 ID，重试时保持原有效配置并重新校验当前权限；凭据从受信存储重新获取。最小字段与唯一约束见 04。

### 幂等与错误收尾

1. 同一个用户动作重试使用相同 key；新动作即使内容相同也使用新 key。
2. 相同 key、不同有效请求必须冲突；摘要排除协议消息 ID、瞬时凭证等非业务变化。原参数已经决议后，重试不得因默认配置变化而偷偷换模型。
3. 标准 Runs 入口不再以内容哈希自动永久去重。没有显式 key 时为该次请求生成独立身份；需要跨网络重试去重的客户端必须传稳定 key。
4. 将有效 key 透传上游，按 tenant/project/thread 命名空间构造，避免上游更宽的唯一约束造成跨 Thread 碰撞。
5. 上游明确 4xx 拒绝与连接前失败：记录拒绝并清理本次提交占位；上游可能已接收、响应丢失：标记 unknown，通过原子幂等或已知标识确认；禁止盲目重新执行有副作用的输入。
6. API 在提交前、提交后、本地关联写入前后崩溃均有可恢复路径。不能只测试“抛 TimeoutException”。

GraphHarbor post21 已有持久化 idempotency_key 字段，但源码存在不等于本链路已具备完整保证；需验证 key scope、并发、payload 冲突、Worker 生命周期和查询能力。新网关交付以前必须验证这些保证，无需保留旧表作过渡。unknown 请求通过同 key 重试/查询恢复，不另建平台轮询 Worker；若上游缺能力，补齐通用合同后才能验收。

### 授权与审批

- 新平台内读取既有 Thread 的权限，与在该 Thread 发起新执行的权限分开；不接续重构前的 Thread/审批数据。
- Agent 必须在当前项目存在且启用；历史 metadata 不能恢复已撤销的执行权限。
- 当前 Graph/模型/工具策略必须参与实际运行决议；共享一个纯决议结果用于授权、签发和摘要，避免三处 SQL 查询得到三种策略。
- `run.start`、标准 Runs、`input.respond` 和将来任何触发器使用同一套决议规则。审批只表达批准/拒绝/编辑允许的工具输入，不顺带修改模型、工具或可信 Context。
- Resume 默认沿用原配置，重新校验当前授权；项目移除成员、禁用模型/Agent 后不得靠旧 token 自动续跑。对“禁用后允许在途任务完成”如有产品需求，必须单独定义，不默默放行。
- 对短期模型引用测试：排队超过 TTL、审批停留超过 TTL、API/Worker 重启、凭据轮换；不能仅靠延长有效期修复链路。认证材料通过受信通道续签，不能塞进浏览器可见的工具审批 response。
- 委托签发集中在一处，由网关传可信身份；受信配置读取仍校验 scope，不得借直连 upstream 绕过授权。

### 传输与协议

- 当前实际公开的 Thread create/search/count/get/delete、state/history、Run create/list/get/join/stream/cancel、commands/events 保留并测试。
- global/batch/cron/store/prune 等未使用表面保持关闭并删除无入口实现。
- 标准 SDK 已覆盖的调用继续使用 SDK；缺失的 Protocol/custom HTTP 仅保留小适配。取消重复的客户端装配和 SDK 方法全量复刻。
- REST `stream_mode` 与 Protocol event channel 是两种集合。当前默认值含 tools/events/messages-tuple，不直接沿用；按锁定 SDK/Server 的契约逐项验证。open-swe 的 `__event_streaming_v2` 属于其服务实现细节，不作为跨实现通用标准写死。
- SSE 前置完成授权与上游状态检查，连接使用有限 connect timeout；建立后使用适合长流的 read timeout。客户端离开只断订阅，显式 cancel 才请求取消 Run。
- 优先透传服务端已兼容的事件；仍必要的协议映射只保留一处。SSE 分帧和脱敏不得在 route/service 两层重复解析，必须覆盖分块 UTF-8、跨块 CRLF、多行 data、心跳和事件 ID。
- Run/Thread/state/history/SSE/error 都应用最小明确的内部字段过滤；不修改用户消息中的普通业务内容来掩盖上游凭据泄漏。

### 并发策略

首期明确使用 `reject`，采用“一段会话同一时刻一轮执行”的产品语义，同时移除平台对活跃状态的第二次裁决。`interrupt`、`enqueue` 是官方 Agent Server 能力，但当前 GraphHarbor 支持深度必须以测试证明，不能仅因参数可存入数据库就宣称支持。

暂不增加 webhook、调度器、多 upstream 路由或通用执行框架。只有明确出现浏览器之外的触发/通知需求时再增加。

## 任务拆分

- [x] G1：将 A01–A05 转为针对预期正确行为的回归测试；覆盖所有公开 Runs/commands/读面。**文件：** `tests/test_run_requests.py`、`test_runtime_gateway_event_redaction.py`、`test_runtime_gateway_runtime_contract.py`。
- [x] G2：实现新请求幂等、明确拒绝收尾、Agent 启停和 resume 授权。**范围：** 新 runtime_gateway/runtime_policies，用旧 service 仅作行为核对。
- [x] G3：统一真实网络调用、连接生命周期、短期委托签发和 SSE 过滤。**文件：** `adapters/langgraph/`、`runtime_gateway/presentation/http.py`、app bootstrap。
- [x] G4：完成上游原子幂等/并发与恢复合同测试，确认可移除的平台协调逻辑。**范围：** GraphHarbor 仅修通用协议缺口，Runtime 仅修受信接入，不混入平台业务。
- [x] G5：实现全新 run_requests 与请求审计，删除旧运行协调器、interrupt 镜像和终态回写；解除 Operations 依赖。**文件：** 新网关 models/repository、数据库初始化基线。
- [ ] G6：删除无入口方法和重复包装，更新网关标准及前端受影响 service/composable。

## 验证要求与记录

### 必须通过的场景

- [ ] 同 key 并发重试只创建一次；不同 key 相同内容创建两次；同 key 改 payload 明确冲突。
- [ ] 拒绝/超时/丢响应/缺 Run ID/API 重启不会造成无法恢复的占位或重复副作用；真实 PostgreSQL 验证竞争。
- [ ] 禁用/删除 Agent、禁用模型、撤销成员权限后，新启动与 resume 均拒绝，历史读取按独立规则执行。
- [ ] 两个独立 interrupt ID 按 ID approve/reject；重复、过期、错误 Thread/项目的审批被拒绝。
- [ ] 多个 Run 的原始 ID 与审批记录可追溯；刷新、断网重连、切换会话、cancel 后再次发送语义正确。
- [ ] 所有公开 JSON/SSE/error 中不含 API Key、delegation 和 runtime_model_ref；错误不在 HTTP 200 后伪装成功。
- [x] 模型引用过期/排队/重启路径：post26 实际等待 62 秒并轮换凭据，三进程重启恢复通过，见 11。
- [ ] 当前 Python SDK、前端 SDK、GraphHarbor post26 的合同固定；后端 SDK 已通过，前端 SDK/浏览器验收 deferred。

### 记录

G2/G3/G5 已实现并通过对应回归：幂等请求记录、标准审批统一授权、SSE 状态前置及连接释放均有测试。G4 真实延迟、轮换、取消及重启已通过；G1 全公开面矩阵已闭合，具体覆盖与真实证据见 [13 三项验收收尾](implementation/13-backend-acceptance-closeout.md)；G6 前端适配验收 deferred。不以单元测试替代真实恢复证据，也不承诺所有工具副作用 exactly-once。

## 状态

本阶段后端 done（含 G1 矩阵），前端验收 deferred。模型/Agent 字段收缩、标准审批、SSE 前置失败、真实超 TTL 排队与凭据轮换、取消重发及三进程恢复均通过，见 [11 收尾记录](implementation/11-backend-closeout.md)。不包含前端/容器验收或完整 Server 等价性；前端调整见 [05](05-frontend-handoff.md)。下方为逐轮历史。

### 最新验证要求与记录（2026-09-10）

本次以 HTTP/SDK 驱动真实后端完成 Showcase；最终独立执行报表 43.50、退出码 0。PostgreSQL 空库升降升、20 表 metadata 一致及请求记录并发唯一约束通过。post25 的原始记录保留在 [10](implementation/10-operations-run-requests.md)，post26 最新计数与覆盖见 [11](implementation/11-backend-closeout.md)，避免多处维护不一致的测试数字。前端及容器部署均 deferred，不计为失败，也不计作已验收。

### 三项最终收尾（2026-09-10）

三项收尾已完成：20 条公开网关路由矩阵、真实 PostgreSQL 备份恢复、4 路登录/列表与 2 条长 SSE 混合负载均通过。详见 [13 三项验收收尾](implementation/13-backend-acceptance-closeout.md)。本阶段后端 done；前端/浏览器、整套容器部署、完整 Server 等价性 deferred。

---
status: draft
last_verified: 2026-10-09
confidence: medium
source_project: docs/projects/20260926-delegation-jwt-contract/verification.md
note: 当前operation枚举为34项；后台元数据/日志/取消精确委托已增补；lost-ACK引擎回查及现役部署仍待完成，整体保留draft
---

# Delegation JWT Schema（draft）

> **适用服务：** platform-api（签发方）、runtime-service（校验方）
> **验证证据：** 历史 API 299 passed、Runtime 只读鉴权 46 passed；diagnostics-read 跨环境契约 5 passed / 50 subtests 保留。Contract 的 `OPERATIONS` 覆盖 32 个 operation，另有独立 cron-read/cron-write，共 34 项。2026-10-09 后台与完整 delegation 定向回归 21 passed / 63 subtests；后台三 operation 的实际授权、HMAC 和 guard 证据见 [后台专项](../projects/20261009-agent-generic-production-capabilities/verification.md)。Stop 与价格/用量既有证据分别见 [取消专项](../projects/20261007-agent-run-cancellation/verification.md)、[用量专项](../projects/20261007-agent-usage-cost-governance/05-verification-rollout.md)。
> **未完成：** Stop 正式配套发布/锁接入与部署 blocked；消息内部原生 Run 回查源码和本机测试已修复，现役链路尚未验证，见 message-run-read-delegation 专项。标准整体仍为 draft。

## JWT Header

```json
{
  "alg": "HS256",
  "typ": "JWT",
  "kid": "<runtime_delegation_kid>"
}
```

## Payload 字段

```json
{
  "sub": "<user_id 或 service-account:<UUID>>",
  "jti": "<uuid4().hex>",
  "iss": "<runtime_delegation_issuer>",
  "aud": "<runtime_delegation_audience>",
  "iat": 1727395200,
  "nbf": 1727395200,
  "exp": 1727395260,

  "type": "runtime_delegation",
  "delegation_version": 2,
  "tenant_id": "<tenant_id>",
  "project_id": "<project_id>",
  "role": "<role>",
  "permissions": ["project.runtime.read"],
  "policy_version": "<non-empty-string>",
  "credential_id": "<credential-uuid>",

  "allowed_model_ids": ["model-a"],
  "tool_overrides": {"tool_name": false},
  "tool_policy_version": "<non-empty-string>",

  "scope": {
    "tenant_id": "<必须与顶层一致>",
    "project_id": "<必须与顶层一致>",
    "assistant_id": "<string 或 null>",
    "thread_id": "<string 或 null>",
    "operation": "<34 项枚举之一>"
  },

  "context_hash": "sha256:<64位十六进制>",
  "request_id": "<32位小写十六进制>",
  "platform_trace_id": "<32位小写十六进制>"
}
```

## 字段约束

| 字段 | 约束 |
|---|---|
| `delegation_version` | 严格整数 2，布尔值也拒绝 |
| `type` | 精确等于 `runtime_delegation` |
| `sub` | 用户取 `actor.user_id`；service account 取 `service-account:<UUID>`；不接收客户端覆盖 |
| `allowed_model_ids` | 非空名称数组，唯一且排序；空数组被拒绝；无模型哨兵值 `platform:no-enabled-model` |
| `jti` | 每次签发生成，Runtime 允许缺省但平台始终生成 |
| `credential_id` | service account 签发必须携带；普通用户禁止携带 |
| `tool_overrides` | 值只能为 `false`；键符合名称规则；≤128 键；紧凑 JSON ≤4096 字节 |
| `context_hash` | 格式：`sha256:` + 64 位十六进制，总长 71 字符 |
| scope 额外键 | 只允许五个键，未知键拒绝 |
| 未知顶层 claim | Runtime 严格拒绝 |

## scope.operation 枚举（34 项）

```
read                    thread-create           thread-reconcile
run-create              thread-edit             thread-delete
run-cancel              run-delete              message-enqueue
message-read            image-upload            image-read
workspace-file-upload   workspace-file-read     workspace-fork
terminal-read           terminal-write          dear-skills-read
dear-skills-write       dear-memory-read        dear-memory-write
dear-governance-read    dear-governance-write   cron-read
cron-write              suggestions-generate    diagnostics-read
usage-read              thread-stop             thread-stop-read
run-cancellation-read
background-task-read    background-task-log-read background-task-cancel
```

**原生资源通用白名单（10 项）：**
`read` / `thread-create` / `thread-reconcile` / `thread-edit` / `thread-delete` / `run-create` / `run-cancel` / `run-delete` / `cron-read` / `cron-write`

另有 `run-cancellation-read` 的精确原生回执例外，规则如下；其余 23 项自定义 token 不能访问原生资源。`suggestions-generate` 只能访问
`/internal/threads/{thread_id}/suggestions`，不能访问原生 Thread、Run、workspace、工具或 MCP 资源。

`diagnostics-read` 必须绑定非空 Thread，且只允许
`GET /internal/threads/{thread_id}/runs/{run_id}/diagnostics`；Runtime 再核对
tenant/project/graph 与当前 Thread ACL、服务账号 credential。不能访问原生资源，
也不能代替 `read`、模型连接或其他自定义 operation。Platform 先授权读取原生 Run，
确认存在及归属后才签发；观测故障不能绕过授权。

`usage-read` 同样必须绑定非空 Thread，只允许
`GET /internal/threads/{thread_id}/runs/{run_id}/usage` 和
`GET /internal/threads/{thread_id}/usage`。Platform 先检查当前项目/Thread ACL，
Run 级再确认原生 Run 存在且属于该 Thread；Runtime 重查当前 ACL/服务账号凭据，
SQL 匹配 tenant/project/graph/Thread/Run。scope 仍只有五字段，不增加 run_id。
该委托不能访问模型连接、Workspace、MCP、原生资源、诊断或其他自定义入口；
read/diagnostics-read/run-create 也不能代替 usage-read。采集开关和数据库故障不绕过授权。

## 会话 Stop 委托（2026-10-07 用户批准）

- `thread-stop` 仅用于 `POST /internal/threads/{thread_id}/cancel`，必须绑定 Thread，沿当前项目执行权限与 Thread edit；`thread-stop-read` 仅用于同 Thread 的 stop-requests detail/list，沿当前项目读取权限与 Thread read。两者不访问原生资源或模型连接。
- Runtime 持久保存受信授权事实和 key 哈希，不保存浏览器 JWT。引擎固定取消目标之前，后台通过 HMAC 回查当前执行权限；回查不可用不提交新取消。已持久受理的引擎意图继续收敛，撤权不抹掉它。
- Runtime 对固定 `stop_id` 签发 30 秒 `run-cancel` 委托；`context_hash=sha256("runtime-cancellation/v1:" + cancellation_id)`（结果加 `sha256:` 前缀）。原生 cancel-active 入口必须核对 hash 与当前 Thread/身份授权，不能用于另一取消 ID。
- `run-cancellation-read` 只允许 `GET /threads/{thread_id}/runs/cancellations/{cancellation_id}`；原生授权事件必须为 Thread read 且标记 `cancellation_receipt=true`，Thread 与上述 hash 必须精确匹配。accepted 之后允许受信后台读取这一个回执，不持续要求操作者仍有权限；不能读取 Thread/state/Run/checkpoint，不能提交取消，也不能用于其他 ID。报告 checkpoint 取证留在 Runtime 内部，不借此 scope 扩大公开读权限。
- 服务账号保留原 `credential_id`，普通用户不能伪装服务账号。公开 POST/GET 每次仍核对当前权限，后台回执例外不授权浏览器读已撤权数据。
- `POST /api/runtime/internal/stop-authorization` 使用共享密钥，HMAC 绑定时间戳、`stop-authorization` 接口标识和规范 JSON 正文，校验 30 秒窗口；正文含 tenant/project/thread/stop/owner/credential。授权与审计使用短事务，阶段审计有持久重试且不保存正文或 JWT。

固定目标、后台撤权与报告取证均已在隔离 HTTP 链路核验；正式版本/部署门禁见 [任务与 Block](../projects/20261007-agent-run-cancellation/tasks.md)，不以候选 wheel 冷安装替代正式源验证。

## 后台任务委托（2026-10-09 用户批准）

- `background-task-read` 仅访问 `/internal/threads/{thread_id}/background-tasks` 的 list/detail；`background-task-log-read` 仅访问同任务 `/output`；`background-task-cancel` 仅 POST 同任务 `/cancel`。三者绑定非空 Thread/graph，不能互相替换，也不能兑换模型、原生 Run、MCP 或其他自定义资源。
- Platform 每次检查当前项目/Thread ACL；Runtime 重查 Thread 与工具政策，SQL 先过滤 tenant/project/graph/Thread，再处理 task_id 或分页。启动同时要求 execute/background_execute；capability 不授予权限。
- 完成交付与开始前复核使用 HMAC 内部回调，绑定 30 秒时间窗、operation、规范 JSON、原 owner/credential/scope/源 Run。完成 marker 再绑定 Context v5；服务端存最小事实和签名意图，不存浏览器 JWT。普通入口拒绝/剥离 `platform_background_completion`。
- `background-control-v1:<task_id>` 是 Runtime 持久 Stop 后的固定清理例外：仅允许原 owner/credential/scope、固定 delivery_run_id 的原生 read/run-cancel，context_hash 必须等于该 task 的 cancellation hash。允许撤权后完成已接受资源清理，不授权公开读取、创建新 Run、读取其他 Run 或改目标。由应用回执精确核对，不能仅凭 policy 字符串授权。
- post43 尚无按幂等 key 的只读 Run 回查；未知派发只对账，不二次 POST。该缺口和接续要求见 [引擎交接](../projects/20261009-agent-generic-production-capabilities/engine-handoff.md)，本补充不使 JWT 整体毕业。

## 生命周期规则

- 委托到期不自动取消已接受 Run
- 已建立 SSE 不增加持续重鉴权或定时断流
- 重连 / 审批 / 取消等新 HTTP 请求加载当前身份重新签发
- 过期 JWT 用于新 Runtime 请求按现有 401 拒绝，不自动降级匿名，不自动重放用户动作

## Runtime Context v5（2026-10-06 用户批准）

API/Runtime 使用相同 `runtime-context/v5` hash，固定字段为 `model_id/temperature/max_tokens/top_p/execution_mode/access_policy/offload_conversation`；JSON 规范化后计算 sha256。`offload_conversation` 严格布尔，省略与 false 相同，true 仅表示当前维护 Run，不关闭自动摘要。

维护使用已有 run-create 和当前 Thread comment 授权，不新增 operation；能力、空输入、最新根 checkpoint、活动 Run、待审批/澄清和持久待发状态须通过网关检查。禁止普通可编辑默认参数、cron、queued input 或 resume 开启维护。

服务端已保存的 v4 审批/定时快照先按当前授权核验，再确定性归一并签发 v5；不接收客户端指定 hash/schema 旁路。双端同步升级，关闭整理 feature flag 不回退 Context hash。实现与隔离证据见 [上下文专项](../projects/20261006-agent-context-window-governance/verification.md)；本段不使 JWT 原专项整体毕业。

## 定时任务执行身份（2026-10-05 用户批准）

- cron-read 仅用于原生 cron 读取/搜索/计数及 Runtime 内部预览/历史；cron-write 用于启停/删除等定义操作。创建或编辑执行 payload 仍需 run-create，绑定 Agent/Thread 与 context_hash。
- cron 定义不是已经接受的 Run。每次自动或手动 Run 在图/工具构造前一次聚合核验当前身份、服务账号凭据、项目、Agent、模型和 Thread，失效拒绝并留下原生 Run 与平台审计。
- 长期定义保存平台 HMAC marker 与可信 Agent Server 身份快照，不保存浏览器 JWT；GraphHarbor 为后台 Run 签名，平台授权策略留在 Platform API/Runtime。
- 回查 HMAC 绑定时间戳、接口、正文，30 秒窗口；拒绝 shape/UUID/scope 不匹配。允许后刷新当前角色、模型引用和工具策略。
- 运行中不周期核验；暂停/删除只阻止未来派发，不取消已接受 Run。无人值守遇人工审批记失败，不自动批准。
- 隔离签名/撤权/服务账号证据见 [定时专项](../projects/20261005-scheduled-agent-tasks/verification.md)。本补充不代表消息回查专项已完成。

## 错误映射

| 场景 | 公开 HTTP | 公开 code |
|---|---|---|
| 签发失败（无原文 / claim / secret） | 503 | `runtime_delegation_not_configured` |
| Runtime 401 | 502 | `runtime_delegation_rejected` |
| Runtime 403 | 403 | 保留已登记安全码或 `forbidden` |
| ACL 回查 503 | — | 按既有公共转换 |

## 共享配置（双方必须一致）

| 配置项 | platform-api 侧 | runtime-service 侧 |
|---|---|---|
| 签名密钥 | `RUNTIME_DELEGATION_SECRET` | 用于校验 |
| Issuer | `runtime_delegation_issuer` | 校验时使用 |
| Audience | `runtime_delegation_audience` | 校验时使用 |
| Kid | `runtime_delegation_kid` | 从 header 读取 |
| TTL | 60s（默认），最长 300s | — |

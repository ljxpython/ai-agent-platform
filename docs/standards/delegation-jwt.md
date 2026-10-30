---
status: draft
last_verified: 2026-10-30
confidence: medium
source_project: docs/projects/20260926-delegation-jwt-contract/verification.md
note: 当前operation枚举为38项；新增thread-touch和thread-retention精确委托；既有消息内部Run现役链路等独立门禁仍保留，整体保持draft
---

# Delegation JWT Schema（draft）

> **适用服务：** platform-api（签发方）、runtime-service（校验方）
> **验证证据：** 历史 API 299 passed、Runtime 只读鉴权 46 passed；diagnostics-read 跨环境契约 5 passed / 50 subtests 保留。Contract 的 `OPERATIONS` 覆盖包含 cron-read/cron-write、run-acceptance-read 与 F07 `title-generate`（见 [F07](../projects/20261009-agent-thread-auto-title/verification.md) 及 [接续专项](../projects/20261011-background-acceptance-closeout/verification.md)）。2026-10-09 后台与完整 delegation 定向回归 21 passed / 63 subtests；后台三 operation 的实际授权、HMAC 和 guard 证据见 [后台专项](../projects/20261009-agent-generic-production-capabilities/verification.md)。Stop 与价格/用量既有证据分别见 [取消专项](../projects/20261007-agent-run-cancellation/verification.md)、[用量专项](../projects/20261007-agent-usage-cost-governance/05-verification-rollout.md)。
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

  "callback_context": {"origin_ref": "<可选的规范 UUID>"},

  "scope": {
    "tenant_id": "<必须与顶层一致>",
    "project_id": "<必须与顶层一致>",
    "assistant_id": "<string 或 null>",
    "thread_id": "<string 或 null>",
    "operation": "<38 项枚举之一>"
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
| `callback_context` | 可选；仅一个 `origin_ref`，必须为规范小写 UUID；未知/空/额外键拒绝，不允许URL或recipient |
| scope 额外键 | 只允许五个键，未知键拒绝 |
| 未知顶层 claim | Runtime 严格拒绝 |

2026-10-11 知识MCP真实服务账号链发现Runtime遗漏既有 `credential_id` 顶层白名单/验签结果，已按上表原约束修复并保留UUID/subject核验；从受信用户重建委托时用命名参数保留credential、callback_context和run_acceptance。鉴权相关91项（14项skip）及普通用户/服务账号真实检索后撤权403/provider0见[知识专项](../projects/20261011-project-knowledge-mcp/verification.md)。未新增JWT operation/claim语义，不代表本标准原剩余门禁通过，状态仍draft。

### 可选运行完成来源（2026-10-09 用户批准）

平台在受理前持久化 origin，再为受管 Run/cron 创建与更新签发可选 `callback_context`。Runtime 验签后只把该字段放入 GraphHarbor 私有受签 context；不进入 State、Prompt、公开 kwargs/SSE。旧 token 没有该字段仍可执行，但没有受管 completion 来源；新 API 遇到旧引擎能力缺失不注入新 claim。

来源不是查询权限或回调凭据；terminal 不重新验证启动 JWT 的有效期，API 接收回调使用独立正文 HMAC，查询/feed/read 仍按当前项目/Thread ACL。无新增 webhook scope。正式 post44、双端契约与隔离 Worker 证据见 [完成通知专项](../projects/20261009-agent-production-capability-extension/verification.md)。本补充不将其他待验收的 JWT 项目自动升为 active。

## scope.operation 枚举（38 项）

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
run-cancellation-read   title-generate          run-acceptance-read
background-task-read    background-task-log-read background-task-cancel
thread-touch            thread-retention
```

**原生资源通用白名单（10 项）：**
`read` / `thread-create` / `thread-reconcile` / `thread-edit` / `thread-delete` / `run-create` / `run-cancel` / `run-delete` / `cron-read` / `cron-write`

另有 `run-cancellation-read` / `run-acceptance-read` 的精确原生回执例外，以及 `thread-touch` / `thread-retention` 的生命周期例外；除此之外的自定义 token 不能访问原生资源。`suggestions-generate` 只能访问
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

## 标题精确委托（2026-10-09 用户批准）

`title-generate` 必须绑定非空 Thread 和 Graph，tenant/project 与 principal 一致；只允许 `POST /internal/threads/{thread_id}/title/summarize`。Runtime 检查当前 comment+edit ACL、assistant 与 context hash；read/suggestions/usage 等不能代用，标题 token 不访问原生 Thread/Run/Workspace/MCP。

API 读取使用 `read`，受管模型引用沿 `thread_action=comment`，落库使用 `thread-edit`。一次非流式受管模型调用，8s 总 deadline，标题正文不进入主 Run/Graph/state/SSE 或 Agent Usage 合计。生成后再次核对 ACL、模型、auto gate、Run 和材料；数据库 CAS 比较 title/内部 seed，未知提交结果返回 `503 title_write_unconfirmed` 并要求 GET Thread 对账。

手动 AI 新授权要求 comment+edit，人工改名沿 edit。自动 gate 默认关闭；手动/自动 AI 的匹配引擎 CAS 正式发布均为独立门禁。验证边界见 [F07](../projects/20261009-agent-thread-auto-title/verification.md)，此补充不将 JWT 原专项提升为 active。

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
- 完成交付与开始前复核使用 HMAC 内部回调，绑定 30 秒时间窗、operation、规范 JSON、原 owner/credential/scope/源 Run。完成 marker 再绑定最终新执行 Context v6；源 plan_execution_id 不复用，marker/创建委托/持久快照 hash 一致。服务端存最小事实和签名意图，不存浏览器 JWT。普通入口拒绝/剥离 `platform_background_completion`。
- `background-control-v1:<task_id>` 是 Runtime 持久 Stop 后的固定清理例外：仅允许原 owner/credential/scope、固定 delivery_run_id 的原生 read/run-cancel，context_hash 必须等于该 task 的 cancellation hash。允许撤权后完成已接受资源清理，不授权公开读取、创建新 Run、读取其他 Run 或改目标。由应用回执精确核对，不能仅凭 policy 字符串授权。
- 正式 post45 已提供按固定幂等 key 的只读 Run 接受回执，B01 已解除；未知派发仍只对账，不二次 POST。版本与证据见 [引擎交接](../projects/20261009-agent-generic-production-capabilities/engine-handoff.md)，本补充不使 JWT 整体毕业。

## 固定 Run 接受回执委托

`run-acceptance-read` 仅用于服务端 `GET /threads/{thread_id}/runs/acceptance`。JWT v2 中必须有 `run_acceptance={scope_id,credential_id,operation,thread_id,key_sha256,request_digest}`，read 操作为 `read`，创建委托仍用 `scope.operation=run-create` 与 `run_acceptance.operation=create`。两个稳定 opaque hash 绑定原 tenant/project/subject 和原用户或服务账号凭据，不绑定短期 JWT jti；Thread/key SHA256/最终传输 bytes 的 SHA256 不可换目标。

- Platform 从发送前已保存的 bytes/key/digest/非 secret 授权快照重建此固定 read JWT，TTL 最长 60 秒，不重新调用模型/写权限授权，也不重建最终 body。
- Runtime 核对签名、期限、tenant/project/subject/credential、Thread 与 hash；原生授权事件必须是 Thread read 且 `run_acceptance_receipt=true`，key/digest 与 grant 完全匹配。只能读这一接受回执，不能读 state/Run/Thread、创建、取消、访问模型/MCP/Workspace。
- 接受后撤权仍允许受信固定只读对账；浏览器公开 ACL 不扩大，完成执行仍在 factory 前按当前权限和持久 Stop 拒绝。服务账号保留原 credential_id，callback_context 也可同时保留，不相互替代。
- `accepted` 仅证明创建接受；`unknown`、no_receipt/receipt_expired、GET 超时/畸形响应/旧路由 404/405 均不能判为未执行或触发新 POST。只有持久 `definitively_not_accepted` 才是拒绝事实。

## 会话保留精确委托（2026-10-30 用户批准）

`thread-touch` 必须绑定非空 Thread，只允许原生 `threads:update` 且授权值严格为 `{thread_id, touch: true}`。Platform 先按当前 Thread read ACL 校验主动查看，再签发这一用途；Runtime 绑定 tenant/project/Thread，不能凭此修改 metadata、策略或创建 Run。发送消息在当前发送权限通过后显式 touch；自动调度、后台完成续接和维护不续期。

`thread-retention` 是存量登记专用委托，固定 `sub=platform-retention-maintenance`、`role=platform_maintenance`、`permissions=[]`、`allowed_model_ids=["maintenance"]`，必须绑定 Thread。只允许以下两种原生授权值：

- `threads:read`：严格 `{thread_id, retention: true}`，仅查询保留状态。
- `threads:update`：严格 `{thread_id, policy: {mode: "idle", ttl_minutes: 43200}}`，仅登记平台的 30 天闲置策略。

Runtime 同时校验固定身份、scope 和上述 payload，返回 project metadata 过滤条件；不授予 Thread 内容、state、Run、模型、MCP 或其他资源访问权。登记器仅对缺少策略的 Thread 设置策略，保留已有策略和真实活动时间；404 不作为删除 ACL 的证据。公开客户端不得指定维护身份或覆盖平台 TTL。

双端 operation 集合已核对为 38 项且完全一致；契约回归 5 passed / 67 subtests、真实三服务跨项目/未签名回调拒绝见 [生命周期治理验证](../projects/20261030-session-and-runtime-retention-governance/verification.md)。正式 GraphHarbor 双包为 `0.13.0.post48`；本次增量不解除 JWT 原专项剩余门禁，状态保持 draft。

## 生命周期规则

- 委托到期不自动取消已接受 Run
- 已建立 SSE 不增加持续重鉴权或定时断流
- 重连 / 审批 / 取消等新 HTTP 请求加载当前身份重新签发
- 过期 JWT 用于新 Runtime 请求按现有 401 拒绝，不自动降级匿名，不自动重放用户动作

## Runtime Context v6（2026-10-09 用户批准）

API/Runtime 使用相同 `runtime-context/v6` hash，固定字段为 `model_id/temperature/max_tokens/top_p/execution_mode/access_policy/offload_conversation/plan_mode/plan_execution_id`；规范 JSON 后计算 sha256。`offload_conversation` 与 `plan_mode` 严格布尔，省略与 false 相同。前者仅表示当前维护 Run，不关闭自动摘要；后者在新 Run 增加规划限制，不改变四档执行模式或原工具 HITL。

`plan_execution_id` 仅由 API 从项目、Thread 和持久请求身份生成，保存到 RunRequests。原生计划审批、后续工具审批和澄清恢复使用原执行链快照；恢复 Run ID 可以变化。客户端输入/config/state/metadata 不得设置执行 ID、`runtime_plan`、`agent_plan` 或 bootstrap 标记；公开出口移除私有绑定。计划审批沿已有 run-create，无新增 operation，须核验人类、Thread approve ACL、当前 interrupt 与 plan ID/revision/hash。

维护使用已有 run-create 和当前 Thread comment 授权，不新增 operation；能力、空输入、最新根 checkpoint、活动 Run、待审批/澄清和持久待发状态须通过网关检查。禁止普通可编辑默认参数、cron、queued input 或 resume 开启维护。

服务端已保存的 v4/v5 审批/定时快照先按当前授权核验，再归一并签发 v6；旧恢复缺执行 ID 时由服务端建立 legacy 执行链，不接受外部旧 hash/token 或旧计划批准。cron 禁止 `plan_mode=true`。API/Runtime 必须成对升级；关闭 capability 不回退 hash，也不能卸载规划门禁后执行含计划 Thread。实现与隔离证据见 [计划专项](../projects/20261008-agent-plan-mode-governance/verification.md)；本段不使 JWT 原专项整体毕业。

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

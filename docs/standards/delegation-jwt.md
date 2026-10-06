---
status: draft
last_verified: 2026-10-06
confidence: medium
source_project: docs/projects/20260926-delegation-jwt-contract/verification.md
note: 当前 operation 枚举为 26 项（原有 25 项 + suggestions-generate）；新增 suggestions 隔离已完成本机定向验证，cron 隔离链路独立覆盖；消息内部 Run 回查仍待 message-run-read-delegation 部署后补验
---

# Delegation JWT Schema（draft）

> **适用服务：** platform-api（签发方）、runtime-service（校验方）
> **验证证据：** 历史 API 299 passed、Runtime 只读鉴权 46 passed；本次 suggestions 定向测试与改动文件 Ruff 通过。Contract 测试中的 `OPERATIONS` 覆盖 24 个通用/自定义 operation（含 `suggestions-generate`），`cron-read`/`cron-write` 由独立隔离测试覆盖。
> **未完成：** 消息内部原生 Run 回查源码和本机测试已修复，现役链路尚未验证，见 message-run-read-delegation 专项。标准整体仍为 draft。

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
    "operation": "<26 项枚举之一>"
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

## scope.operation 枚举（26 项）

```
read                    thread-create           thread-reconcile
run-create              thread-edit             thread-delete
run-cancel              run-delete              message-enqueue
message-read            image-upload            image-read
workspace-file-upload   workspace-file-read     workspace-fork
terminal-read           terminal-write          dear-skills-read
dear-skills-write       dear-memory-read        dear-memory-write
dear-governance-read    dear-governance-write   cron-read
cron-write              suggestions-generate
```

**原生资源白名单（仅 10 项可访问原生资源）：**
`read` / `thread-create` / `thread-reconcile` / `thread-edit` / `thread-delete` / `run-create` / `run-cancel` / `run-delete` / `cron-read` / `cron-write`

其余 16 项自定义 token，不能访问原生资源。`suggestions-generate` 只能访问
`/internal/threads/{thread_id}/suggestions`，不能访问原生 Thread、Run、workspace、工具或 MCP 资源。

## 生命周期规则

- 委托到期不自动取消已接受 Run
- 已建立 SSE 不增加持续重鉴权或定时断流
- 重连 / 审批 / 取消等新 HTTP 请求加载当前身份重新签发
- 过期 JWT 用于新 Runtime 请求按现有 401 拒绝，不自动降级匿名，不自动重放用户动作

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
